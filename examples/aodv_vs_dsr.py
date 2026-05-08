"""
aodv_vs_dsr.py  –  Head-to-head comparison exposing the real mechanical
                   differences between AODV and DSR.

Two protocol mechanisms under test
-----------------------------------
  DSR gratuitous path caching
      When the source receives a RREP for G via path [A,B,D,E,G] it caches
      routes to *every* prefix:  A->B, A->B->D, A->B->D->E, A->B->D->E->G.
      AODV only records the single destination G.  Subsequent sends from A to
      any intermediate node (B, D, E) are instant cache-hits for DSR; AODV
      must flood a fresh RREQ for each new destination.

  AODV reverse routing
      Every node that *forwards* an RREQ also builds a reverse route back to
      the originator.  After A->G is discovered, G already has A in its table.
      DSR records no reverse path; G must start its own RREQ to reach A.

Four test cases
---------------
  1. Single destination  A->G repeated.  Baseline – protocols identical.
  2. Multi-destination   A discovers G, then sends to intermediate nodes D, E, B.
                         DSR: instant cache-hits.  AODV: fresh RREQ per dest.
  3. Bidirectional       A->G discovery, then G->A.
                         AODV: G already has A from RREQ flood (cache-hit).
                         DSR: G must discover A (new RREQ).
  4. Mobile multi-dest   Scenario 2 under slow mobility; shows how quickly
                         DSR's cached advantage erodes when topology shifts.

Metrics plotted
---------------
  PDR            – packet delivery ratio (higher = better)
  Discoveries    – total RREQ floods initiated (lower = better)
  Cache hit rate – fraction of sends that found a cached route (higher = better)
  Ctrl overhead  – control transmissions / delivered packet (lower = better)
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


# ─── Metrics ────────────────────────────────────────────────────────────────

class Metrics:
    def __init__(self):
        self.ctrl        = 0
        self.sent        = 0
        self.recvd       = 0
        self.discoveries = 0   # RREQ floods initiated by the source node
        self.cache_hits  = 0   # sends that found a cached route immediately
        self._t0         = {}
        self._seq        = 0
        self.latencies   = []
        self.hops        = []

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
    def pdr(self):            return self.recvd / max(self.sent, 1)
    @property
    def cache_hit_rate(self): return self.cache_hits / max(self.sent, 1)
    @property
    def ctrl_overhead(self):  return self.ctrl / max(self.recvd, 1)
    @property
    def avg_latency(self):    return float(np.mean(self.latencies)) if self.latencies else float('nan')
    @property
    def avg_hops(self):       return float(np.mean(self.hops))      if self.hops      else float('nan')


# ─── AODV ───────────────────────────────────────────────────────────────────
# Difference from DSR:
#   * Only the destination is cached at the source — no prefix caching.
#   * RREQ forwarders build a reverse route back to the originator, so once
#     A discovers G, G (and every intermediate node) already has A in its table.

class AODVNode(Node):
    def __init__(self, nid, m):
        super().__init__(nid)
        self.m    = m
        self.seq  = 0
        self.routes      = {}     # dest -> (next_hop, dest_seq, hops)
        self.seen        = set()  # dedup (orig, dest, seq, rid)
        self._buf        = {}     # dest -> [seq_id, ...]
        self._discovering = set() # destinations with an in-flight RREQ

    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'RREQ':
            _, orig, dest, seq, rid, hops = msg
            key = (orig, dest, seq, rid)
            if key in self.seen:
                return
            self.seen.add(key)
            hops += 1
            # Reverse route: every forwarder learns how to reach orig
            self._update(orig, sender, seq, hops)
            if dest == self.nid:
                self.seq = max(self.seq, seq) + 1
                self._send_rrep(dest, orig)
            elif dest in self.routes:
                self._send_rrep(dest, orig)    # shortcut via cached route
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
        if orig not in self.routes:
            return
        # Use our known hop-count to dest so the originator gets correct metrics
        d_hops = self.routes[dest][2] if dest in self.routes else 0
        self.m.ctrl += 1
        self.unicast(self.routes[orig][0], ('RREP', dest, self.seq, orig, d_hops))

    def _flush(self, dest):
        if dest not in self.routes:
            return
        self._discovering.discard(dest)
        hops = self.routes[dest][2]
        for sid in self._buf.pop(dest, []):
            self.unicast(self.routes[dest][0], ('DATA', sid, dest, hops))

    def send_data(self, dest):
        if dest in self.routes:
            self.m.cache_hits += 1
            hops = self.routes[dest][2]
            sid  = self.m.record_send(self.net.loop.time)
            self.unicast(self.routes[dest][0], ('DATA', sid, dest, hops))
        else:
            sid = self.m.record_send(self.net.loop.time)
            self._buf.setdefault(dest, []).append(sid)
            if dest not in self._discovering:   # suppress duplicate in-flight RREQs
                self._discovering.add(dest)
                self._discover(dest)

    def _discover(self, dest):
        self.seq += 1
        self.seen.add((self.nid, dest, self.seq, self.seq))
        self.m.ctrl       += 1
        self.m.discoveries += 1
        self.broadcast(('RREQ', self.nid, dest, self.seq, self.seq, 0))


# ─── DSR ────────────────────────────────────────────────────────────────────
# Difference from AODV:
#   * Gratuitous path caching: when the source receives RREP for G via
#     [A,B,D,E,G] it caches routes to ALL prefixes A->B, A->D, A->E, A->G.
#   * No reverse-route mechanism — G does NOT learn A from the RREQ flood.
#     G must run its own route discovery if it needs to send to A.

class DSRNode(Node):
    def __init__(self, nid, m):
        super().__init__(nid)
        self.m           = m
        self.route_cache  = {}    # dest -> [self.nid, ..., dest]
        self.seen         = set()
        self._buf         = {}
        self._rid         = 0
        self._discovering = set() # destinations with an in-flight RREQ

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
                    # Shortcut: reply with cached route without re-flooding
                    cached    = self.route_cache[dest]
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
            # Every forwarder caches the path segment from itself to dest
            seg = path[idx:]
            cur = self.route_cache.get(dest)
            if not cur or len(seg) < len(cur):
                self.route_cache[dest] = seg

            if self.nid == orig:
                # ── DSR gratuitous path caching ──────────────────────────
                # Cache routes to ALL intermediate nodes along the full path,
                # not just the final destination.  This is the key DSR advantage
                # over AODV: one discovery seeds routes to many destinations.
                for k in range(1, len(path)):
                    mid      = path[k]
                    sub_path = path[:k + 1]
                    cur2     = self.route_cache.get(mid)
                    if not cur2 or len(sub_path) < len(cur2):
                        self.route_cache[mid] = sub_path
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
                    pass

    def _flush(self, dest):
        if dest not in self.route_cache:
            return
        self._discovering.discard(dest)
        path = self.route_cache[dest]
        hops = len(path) - 1
        for sid in self._buf.pop(dest, []):
            if len(path) > 1:
                self.unicast(path[1], ('DATA', sid, dest, hops, path))

    def send_data(self, dest):
        if dest in self.route_cache:
            self.m.cache_hits += 1
            path = self.route_cache[dest]
            hops = len(path) - 1
            sid  = self.m.record_send(self.net.loop.time)
            if len(path) > 1:
                self.unicast(path[1], ('DATA', sid, dest, hops, path))
        else:
            sid = self.m.record_send(self.net.loop.time)
            self._buf.setdefault(dest, []).append(sid)
            if dest not in self._discovering:   # suppress duplicate in-flight RREQs
                self._discovering.add(dest)
                self._discover(dest)

    def _discover(self, dest):
        self._rid += 1
        self.seen.add((self.nid, dest, self._rid))
        self.m.ctrl       += 1
        self.m.discoveries += 1
        self.broadcast(('RREQ', self.nid, dest, self._rid, [self.nid]))


# ─── Network helpers ────────────────────────────────────────────────────────

# tx_range=3.0 keeps BASE_POS connected: all inter-node distances = 2*sqrt(2) ~ 2.83
BASE_POS = [('A',0,2), ('B',2,4), ('C',2,0), ('D',4,2),
            ('E',6,4), ('F',6,0), ('G',8,2)]

def build_net(m, protocol, tx_range=3.0, seed=42):
    loop = EventLoop()
    net  = WirelessNetwork(loop, tx_range=tx_range, tx_time=0.5,
                           loss=0.0, seed=seed, verbose=False)
    cls  = AODVNode if protocol == 'AODV' else DSRNode
    for nid, x, y in BASE_POS:
        net.add_node(cls(nid, m), x, y)
    return loop, net


# ─── Scenario runners ───────────────────────────────────────────────────────

SEND_GAP = 2.0   # seconds between data sends within one scenario phase


def run_sc1(protocol):
    """Scenario 1: Single destination – A→G repeated (baseline)."""
    m = Metrics()
    loop, net = build_net(m, protocol)
    for i in range(12):
        loop.schedule(5.0 + i * SEND_GAP, net.nodes['A'].send_data, 'G')
    loop.run(until=40)
    return m


def run_sc2(protocol):
    """Scenario 2: Multi-destination – A→G then A→D, A→E, A→B.
    DSR advantage: A caches D, E, B as prefixes of the A→G path.
    AODV must flood a fresh RREQ for each new destination.
    """
    m = Metrics()
    loop, net = build_net(m, protocol)
    # Phase 1: discover G and send a few packets
    for i in range(4):
        loop.schedule(5.0 + i * SEND_GAP, net.nodes['A'].send_data, 'G')
    # Phase 2: now send to nodes that lie ON the A→G path
    for i in range(4):
        loop.schedule(14.0 + i * SEND_GAP, net.nodes['A'].send_data, 'D')
    for i in range(4):
        loop.schedule(23.0 + i * SEND_GAP, net.nodes['A'].send_data, 'E')
    for i in range(4):
        loop.schedule(32.0 + i * SEND_GAP, net.nodes['A'].send_data, 'B')
    loop.run(until=45)
    return m


def run_sc3(protocol):
    """Scenario 3: Bidirectional – A→G discovery then G→A.
    AODV advantage: every RREQ forwarder builds a reverse route to A,
                    so G gets A for free and needs zero re-discovery.
    DSR: G has no reverse path; it must flood its own RREQ for A.
    """
    m = Metrics()
    loop, net = build_net(m, protocol)
    # Phase 1: A discovers and sends to G
    for i in range(6):
        loop.schedule(5.0 + i * SEND_GAP, net.nodes['A'].send_data, 'G')
    # Phase 2: G sends back to A
    for i in range(6):
        loop.schedule(18.0 + i * SEND_GAP, net.nodes['G'].send_data, 'A')
    loop.run(until=35)
    return m


def run_sc4(protocol):
    """Scenario 4: Mobile multi-destination – same as Sc2 under slow mobility.
    Shows how DSR's cached intermediate routes erode as nodes drift.
    """
    m = Metrics()
    loop, net = build_net(m, protocol, seed=7)
    mob = MobilityManager(net, interval=0.5, speed=0.3, bounds=(8, 5))
    mob.start('waypoint')
    for i in range(4):
        loop.schedule(8.0  + i * SEND_GAP, net.nodes['A'].send_data, 'G')
    for i in range(4):
        loop.schedule(17.0 + i * SEND_GAP, net.nodes['A'].send_data, 'D')
    for i in range(4):
        loop.schedule(26.0 + i * SEND_GAP, net.nodes['A'].send_data, 'E')
    for i in range(4):
        loop.schedule(35.0 + i * SEND_GAP, net.nodes['A'].send_data, 'B')
    loop.run(until=50)
    return m


# ─── Run all scenarios ───────────────────────────────────────────────────────

SCENARIOS = [
    ('1 – Single Dest\n(baseline)',    run_sc1),
    ('2 – Multi-Dest\n(DSR caches prefixes)', run_sc2),
    ('3 – Bidirectional\n(AODV reverse route)', run_sc3),
    ('4 – Mobile\nMulti-Dest',         run_sc4),
]
PROTOCOLS = ['AODV', 'DSR']
COLORS    = {'AODV': '#2196F3', 'DSR': '#FF9800'}

print("Running AODV vs DSR scenarios …")
results = {}
for sc_name, sc_fn in SCENARIOS:
    for proto in PROTOCOLS:
        m = sc_fn(proto)
        results[(proto, sc_name)] = m
        label = sc_name.replace('\n', ' ')
        print(f"  {proto}  {label:<38} "
              f"PDR={m.pdr:.2f}  disc={m.discoveries:2d}  "
              f"chit={m.cache_hit_rate:.0%}  ctrl={m.ctrl:3d}  "
              f"lat={m.avg_latency:.2f}s")

print("Done.\n")

# ─── Plot ────────────────────────────────────────────────────────────────────

sc_labels = [s[0] for s in SCENARIOS]
x         = np.arange(len(SCENARIOS))
width     = 0.30
offsets   = [-width / 2, width / 2]

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle('AODV vs DSR – Protocol Mechanism Comparison\n'
             '(static topology unless noted; 7 nodes, tx_range=3.0)',
             fontsize=13, fontweight='bold', y=0.99)

SUBPLOT_CFG = [
    (axes[0, 0], 'pdr',           'Packet Delivery Ratio (PDR)',
     'PDR',            (0, 1.15), True,
     'Both reactive — PDR should track closely.\n'
     'Drops in Sc4 show mobility stressing both equally.'),

    (axes[0, 1], 'discoveries',   'Route Discoveries (RREQ Floods)',
     'Count',          None,      False,
     'Sc2: DSR discovers once (G) and caches D,E,B for free.\n'
     'AODV needs a separate RREQ per destination.\n'
     'Sc3: DSR must discover A from G (no reverse route).'),

    (axes[1, 0], 'cache_hit_rate','Cache Hit Rate\n(sends w/ cached route / total sends)',
     'Rate',           (0, 1.15), True,
     'Sc2: DSR hits ~100% after one discovery;\n'
     'AODV misses on the 1st send to each new destination.\n'
     'Sc3: AODV wins — G already has A via reverse route.'),

    (axes[1, 1], 'ctrl_overhead', 'Control Overhead\n(ctrl msgs / delivered pkt)',
     'Messages',       None,      False,
     'Derived from discoveries: fewer RREQs = lower overhead.\n'
     'Sc2 benefits DSR; Sc3 benefits AODV.'),
]

for ax, attr, title, ylabel, ylim, higher_better, annotation in SUBPLOT_CFG:
    for proto, offset in zip(PROTOCOLS, offsets):
        vals = [getattr(results[(proto, sc[0])], attr) for sc in SCENARIOS]
        bars = ax.bar(x + offset, vals, width,
                      label=proto, color=COLORS[proto], alpha=0.85,
                      edgecolor='white', linewidth=0.5)
        for bar, v in zip(bars, vals):
            if not np.isnan(v):
                fmt = f'{v:.0%}' if attr == 'cache_hit_rate' else (
                      f'{v:.2f}' if isinstance(v, float) else f'{int(v)}')
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (0.01 if attr in ('pdr','cache_hit_rate') else bar.get_height() * 0.03),
                        fmt, ha='center', va='bottom', fontsize=8, rotation=35,
                        color='#222222')

    ax.set_title(title, fontsize=10.5, fontweight='bold', pad=6)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(sc_labels, fontsize=8.5)
    ax.legend(fontsize=9, framealpha=0.7)
    ax.grid(axis='y', alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if ylim:
        ax.set_ylim(*ylim)

    hint = '↑ higher is better' if higher_better else '↓ lower is better'
    va   = 'bottom' if higher_better else 'top'
    y_p  = 0.03     if higher_better else 0.97
    ax.text(0.98, y_p, hint, transform=ax.transAxes,
            ha='right', va=va, fontsize=7.5, color='gray', style='italic')

    # Annotation box explaining the expected result
    ax.text(0.01, 0.97, annotation, transform=ax.transAxes,
            ha='left', va='top', fontsize=6.8, color='#444444',
            style='italic', linespacing=1.4)

plt.tight_layout(rect=[0, 0.02, 1, 0.97])

fig.text(0.5, 0.005,
         'Sc1: A->G x12  |  Sc2: A->G x4, A->D x4, A->E x4, A->B x4  |  '
         'Sc3: A->G x6 then G->A x6  |  Sc4: Sc2 with speed=0.3 mobility',
         ha='center', fontsize=7.5, color='gray')

out = Path(__file__).parent / 'aodv_vs_dsr_comparison.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Plot saved -> {out}")
