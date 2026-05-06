"""
performance_comparison.py
Benchmark AODV, DSR, and DSDV across four mobility/topology scenarios.

Metrics collected per simulation run:
  PDR           – fraction of data packets successfully delivered
  Ctrl Overhead – total control transmissions / delivered data packets
  Latency       – mean end-to-end delivery time (seconds)
  Path Length   – mean hop count of delivered packets

Scenarios:
  1. Static       – nodes fixed, tx_range widened so initial positions connect
  2. Low Mobility – gentle random-waypoint movement
  3. High Mobility – fast random-waypoint movement
  4. Sparse       – same speed as Low but smaller tx_range (less connectivity)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from pywisim import EventLoop, Node, WirelessNetwork
from mobility import MobilityManager


# ─── Shared metrics collector ────────────────────────────────────────────────

class Metrics:
    def __init__(self):
        self.ctrl   = 0          # total control transmissions (broadcasts + unicasts)
        self.sent   = 0          # data packets initiated by source
        self.recvd  = 0          # data packets delivered to destination
        self._t0    = {}         # seq_id -> send timestamp
        self._seq   = 0
        self.latencies = []      # end-to-end delivery times (s)
        self.hops      = []      # per-packet hop counts at delivery

    def record_send(self, t):
        self._seq += 1
        self._t0[self._seq] = t
        self.sent += 1
        return self._seq

    def record_recv(self, seq, t, hop_count):
        self.recvd += 1
        if seq in self._t0:
            self.latencies.append(t - self._t0[seq])
        if hop_count is not None:
            self.hops.append(hop_count)

    @property
    def pdr(self):
        return self.recvd / max(self.sent, 1)

    @property
    def ctrl_overhead(self):
        return self.ctrl / max(self.recvd, 1)

    @property
    def avg_latency(self):
        return float(np.mean(self.latencies)) if self.latencies else float('nan')

    @property
    def avg_hops(self):
        return float(np.mean(self.hops)) if self.hops else float('nan')


# ─── AODV instrumented ──────────────────────────────────────────────────────
# DATA = ('DATA', seq_id, dest_nid, hop_count)

class AODVNode(Node):
    def __init__(self, nid, m, **_):
        super().__init__(nid)
        self.m    = m
        self.seq  = 0
        self.routes   = {}     # dest -> (next_hop, dest_seq, hops)
        self.seen     = set()  # (orig, dest, seq, rid)
        self._buf     = {}     # dest -> [seq_id, ...]

    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'RREQ':
            _, orig, dest, seq, rid, hops = msg
            key = (orig, dest, seq, rid)
            if key in self.seen:
                return
            self.seen.add(key)
            hops += 1
            self._update(orig, sender, seq, hops)
            if dest == self.nid:
                self.seq = max(self.seq, seq) + 1
                self._send_rrep(dest, orig)
            elif dest in self.routes:
                self._send_rrep(dest, orig)
            else:
                self.m.ctrl += 1
                self.broadcast(('RREQ', orig, dest, seq, rid, hops))

        elif kind == 'RREP':
            _, dest, dseq, orig, hops = msg
            hops += 1
            self._update(dest, sender, dseq, hops)
            if orig == self.nid:
                self._flush(dest)
            elif orig in self.routes:
                self.m.ctrl += 1
                self.unicast(self.routes[orig][0], ('RREP', dest, dseq, orig, hops))

        elif kind == 'DATA':
            _, sid, dest, hops = msg
            if dest == self.nid:
                self.m.record_recv(sid, self.net.loop.time, hops)
            elif dest in self.routes:
                self.unicast(self.routes[dest][0], msg)

    def _update(self, dest, via, seq, hops):
        c = self.routes.get(dest)
        if not c or seq > c[1] or (seq == c[1] and hops < c[2]):
            self.routes[dest] = (via, seq, hops)

    def _send_rrep(self, dest, orig):
        if orig in self.routes:
            self.m.ctrl += 1
            self.unicast(self.routes[orig][0], ('RREP', dest, self.seq, orig, 0))

    def _flush(self, dest):
        if dest not in self.routes:
            return
        hops = self.routes[dest][2]
        for sid in self._buf.pop(dest, []):
            self.unicast(self.routes[dest][0], ('DATA', sid, dest, hops))

    def send_data(self, dest):
        if dest in self.routes:
            hops = self.routes[dest][2]
            sid = self.m.record_send(self.net.loop.time)
            self.unicast(self.routes[dest][0], ('DATA', sid, dest, hops))
        else:
            sid = self.m.record_send(self.net.loop.time)
            self._buf.setdefault(dest, []).append(sid)
            self._discover(dest)

    def _discover(self, dest):
        self.seq += 1
        self.seen.add((self.nid, dest, self.seq, self.seq))
        self.m.ctrl += 1
        self.broadcast(('RREQ', self.nid, dest, self.seq, self.seq, 0))


# ─── DSR instrumented ───────────────────────────────────────────────────────
# DATA = ('DATA', seq_id, dest_nid, hop_count, path)

class DSRNode(Node):
    def __init__(self, nid, m, **_):
        super().__init__(nid)
        self.m           = m
        self.route_cache = {}   # dest -> [self.nid, ..., dest]
        self.seen        = set()
        self._buf        = {}   # dest -> [seq_id, ...]
        self._rid        = 0

    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'RREQ':
            _, orig, dest, rid, path = msg
            key = (orig, dest, rid)
            if key in self.seen:
                return
            self.seen.add(key)
            new_path = path + [self.nid]
            if dest == self.nid:
                if len(new_path) > 1:
                    self.m.ctrl += 1
                    self.unicast(new_path[-2], ('RREP', orig, dest, new_path))
            elif self.nid not in path:
                if dest in self.route_cache:
                    cached = self.route_cache[dest]
                    full_path = new_path + cached[1:]
                    if len(full_path) > 1:
                        self.m.ctrl += 1
                        self.unicast(full_path[-2], ('RREP', orig, dest, full_path))
                else:
                    self.m.ctrl += 1
                    self.broadcast(('RREQ', orig, dest, rid, new_path))

        elif kind == 'RREP':
            _, orig, dest, path = msg
            try:
                idx = path.index(self.nid)
            except ValueError:
                return
            seg = path[idx:]
            cur = self.route_cache.get(dest)
            if not cur or len(seg) < len(cur):
                self.route_cache[dest] = seg
            if self.nid == orig:
                self._flush(dest)
            elif idx > 0:
                self.m.ctrl += 1
                self.unicast(path[idx - 1], ('RREP', orig, dest, path))

        elif kind == 'DATA':
            _, sid, dest, hops, path = msg
            if self.nid == dest:
                self.m.record_recv(sid, self.net.loop.time, hops)
            else:
                try:
                    idx = path.index(self.nid)
                    if idx + 1 < len(path):
                        self.unicast(path[idx + 1], msg)
                except ValueError:
                    pass  # stale path entry

    def _flush(self, dest):
        if dest not in self.route_cache:
            return
        path = self.route_cache[dest]
        hops = len(path) - 1
        for sid in self._buf.pop(dest, []):
            if len(path) > 1:
                self.unicast(path[1], ('DATA', sid, dest, hops, path))

    def send_data(self, dest):
        if dest in self.route_cache:
            path = self.route_cache[dest]
            hops = len(path) - 1
            sid  = self.m.record_send(self.net.loop.time)
            if len(path) > 1:
                self.unicast(path[1], ('DATA', sid, dest, hops, path))
        else:
            sid = self.m.record_send(self.net.loop.time)
            self._buf.setdefault(dest, []).append(sid)
            self._discover(dest)

    def _discover(self, dest):
        self._rid += 1
        self.seen.add((self.nid, dest, self._rid))
        self.m.ctrl += 1
        self.broadcast(('RREQ', self.nid, dest, self._rid, [self.nid]))


# ─── DSDV instrumented ──────────────────────────────────────────────────────
# DATA = ('DATA', seq_id, dest_nid, hop_count)

class DSDVNode(Node):
    _TRIGGER_DELAY = 0.2

    def __init__(self, nid, m, bc_interval=5.0):
        super().__init__(nid)
        self.m           = m
        self.seq         = 0
        self.routes      = {nid: (nid, 0, 0)}  # dest -> (next, metric, seq_num)
        self._bc_interval   = bc_interval
        self._pending_bc    = False

    def start_updates(self):
        # small initial delay so the event loop is running before first broadcast
        self.schedule(0.3, self._initial_bc)
        self.schedule(self._bc_interval, self._periodic)

    def _initial_bc(self):
        self.seq += 2
        self.routes[self.nid] = (self.nid, 0, self.seq)
        self._do_bc()

    def _periodic(self):
        self.seq += 2
        self.routes[self.nid] = (self.nid, 0, self.seq)
        self._do_bc()
        self.schedule(self._bc_interval, self._periodic)

    def _do_bc(self):
        self.m.ctrl += 1
        self.broadcast(('TABLE', self.nid, list(self.routes.items())))

    def _schedule_triggered(self):
        if not self._pending_bc:
            self._pending_bc = True
            self.schedule(self._TRIGGER_DELAY, self._triggered)

    def _triggered(self):
        self._pending_bc = False
        self._do_bc()

    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'TABLE':
            _, _adv, table = msg
            changed = False
            for dest, (_via, metric, seq) in table:
                if dest == self.nid:
                    continue
                nm  = metric + 1
                cur = self.routes.get(dest)
                if cur is None or seq > cur[2] or (seq == cur[2] and nm < cur[1]):
                    self.routes[dest] = (sender, nm, seq)
                    changed = True
            if changed:
                self._schedule_triggered()

        elif kind == 'DATA':
            _, sid, dest, hops = msg
            if dest == self.nid:
                self.m.record_recv(sid, self.net.loop.time, hops)
            elif dest in self.routes:
                self.unicast(self.routes[dest][0], msg)

    def send_data(self, dest):
        if dest in self.routes:
            r   = self.routes[dest]
            sid = self.m.record_send(self.net.loop.time)
            self.unicast(r[0], ('DATA', sid, dest, r[1]))
        else:
            # proactive protocol: drop if no route exists at send time
            self.m.record_send(self.net.loop.time)


# ─── Scenarios ───────────────────────────────────────────────────────────────

BASE_POS = [('A',0,2), ('B',2,4), ('C',2,0), ('D',4,2), ('E',6,4), ('F',6,0), ('G',8,2)]

# tx_range=3.0 keeps BASE_POS connected (inter-node distance = 2*sqrt(2) ~ 2.83).
# Sparse uses tx_range=2.0 so nodes are initially disconnected and must drift into range.
#
# DSDV's bc_interval is tuned per scenario: static can afford slow updates while
# mobile scenarios need faster periodic broadcasts to limit route staleness.
SCENARIOS = [
    dict(name='Static',         speed=0.0, bounds=(8, 5), tx_range=3.0, positions=BASE_POS, dsdv_bc=5.0),
    dict(name='Low\nMobility',  speed=0.3, bounds=(8, 5), tx_range=3.0, positions=BASE_POS, dsdv_bc=3.0),
    dict(name='High\nMobility', speed=0.8, bounds=(8, 5), tx_range=3.0, positions=BASE_POS, dsdv_bc=2.0),
    dict(name='Sparse\nNetwork',speed=0.4, bounds=(8, 5), tx_range=2.0, positions=BASE_POS, dsdv_bc=3.0),
]

# Source and destination for all data transfers
SRC, DST = 'A', 'G'

# Start data at t=20: enough time for DSDV tables to fully converge across 4 hops.
# SIM_END=90 ensures DATA packets still in transit after t=70 are delivered.
DATA_TIMES = list(range(20, 72, 4))   # t = 20, 24, 28, ..., 68  (13 packets)
SIM_END    = 90


# ─── Run one simulation ──────────────────────────────────────────────────────

def run_simulation(protocol, scenario):
    """Run one (protocol × scenario) combination; return Metrics."""
    m    = Metrics()
    loop = EventLoop()
    net  = WirelessNetwork(loop,
                           tx_range=scenario['tx_range'],
                           tx_time=0.5,
                           loss=0.0,
                           seed=42,
                           verbose=False)

    node_cls = {'AODV': AODVNode, 'DSR': DSRNode, 'DSDV': DSDVNode}[protocol]
    bc = scenario.get('dsdv_bc', 5.0)
    for nid, x, y in scenario['positions']:
        kwargs = {'bc_interval': bc} if protocol == 'DSDV' else {}
        net.add_node(node_cls(nid, m, **kwargs), x, y)

    if protocol == 'DSDV':
        for node in net.nodes.values():
            node.start_updates()

    if scenario['speed'] > 0:
        mob = MobilityManager(net,
                              interval=0.5,
                              speed=scenario['speed'],
                              bounds=scenario['bounds'])
        mob.start('waypoint')

    for t in DATA_TIMES:
        loop.schedule(t, net.nodes[SRC].send_data, DST)

    loop.run(until=SIM_END)
    return m


# ─── Collect results ─────────────────────────────────────────────────────────

PROTOCOLS     = ['AODV', 'DSR', 'DSDV']
scenario_keys = [s['name'] for s in SCENARIOS]

print("Running simulations …")
results = {}
for sc in SCENARIOS:
    for proto in PROTOCOLS:
        label = f"{proto:4s}  {sc['name'].replace(chr(10),' ')}"
        m = run_simulation(proto, sc)
        results[(proto, sc['name'])] = m
        print(f"  {label:<22}  PDR={m.pdr:.2f}  ctrl={m.ctrl:4d}  "
              f"lat={m.avg_latency:.2f}s  hops={m.avg_hops:.1f}")

print("Done.")


# ─── Plot ────────────────────────────────────────────────────────────────────

COLORS = {'AODV': '#2196F3', 'DSR': '#FF9800', 'DSDV': '#4CAF50'}

x       = np.arange(len(SCENARIOS))
width   = 0.22
offsets = [-width, 0, width]

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle('Routing Protocol Performance Comparison\nAODV vs DSR vs DSDV',
             fontsize=15, fontweight='bold', y=0.98)

SUBPLOT_CFG = [
    (axes[0, 0], 'pdr',           'Packet Delivery Ratio (PDR)',        'PDR',            (0, 1.08), True),
    (axes[0, 1], 'ctrl_overhead', 'Control Overhead\n(ctrl msgs / delivered pkt)', 'Messages', None,       False),
    (axes[1, 0], 'avg_latency',   'Mean End-to-End Latency',            'Seconds',        None,       False),
    (axes[1, 1], 'avg_hops',      'Mean Path Length',                   'Hops',           None,       False),
]

for ax, attr, title, ylabel, ylim, higher_better in SUBPLOT_CFG:
    for proto, offset in zip(PROTOCOLS, offsets):
        vals = [getattr(results[(proto, sc['name'])], attr) for sc in SCENARIOS]
        bars = ax.bar(x + offset, vals, width,
                      label=proto, color=COLORS[proto], alpha=0.85, edgecolor='white', linewidth=0.5)
        for bar, v in zip(bars, vals):
            if not np.isnan(v) and v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (0.01 if attr == 'pdr' else bar.get_height() * 0.02),
                        f'{v:.2f}', ha='center', va='bottom', fontsize=7.5, rotation=40,
                        color='#333333')

    ax.set_title(title, fontsize=11, fontweight='bold', pad=8)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([s['name'] for s in SCENARIOS], fontsize=9)
    ax.legend(fontsize=9, framealpha=0.7)
    ax.grid(axis='y', alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if ylim:
        ax.set_ylim(*ylim)

    hint = '↑ higher is better' if higher_better else '↓ lower is better'
    ax.text(0.98, 0.97 if not higher_better else 0.03,
            hint, transform=ax.transAxes,
            ha='right', va='top' if not higher_better else 'bottom',
            fontsize=7.5, color='gray', style='italic')

# Scenario annotation strip along the bottom
fig.text(0.5, 0.01,
         f"7 nodes, {len(DATA_TIMES)} data sends (A->G) per run  |  "
         "Static/Mob: tx_range=3.0, bounds=8x5  |  Sparse: tx_range=2.0  |  "
         "DSDV bc_interval: Static=5s, Low Mob=3s, High Mob=2s, Sparse=3s",
         ha='center', fontsize=7.5, color='gray')

plt.tight_layout(rect=[0, 0.03, 1, 0.96])

out = Path(__file__).parent / 'protocol_comparison.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.show()
print(f"\nPlot saved -> {out}")
