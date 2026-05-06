"""DSDV – Destination Sequenced Distance Vector routing over a mobile ad-hoc network.

DSDV is a proactive table-driven protocol: each node periodically broadcasts its
full routing table so every node always has routes to all reachable destinations.
Sequence numbers (even = valid, odd = broken) prevent routing loops and let nodes
choose fresher routes.  When the table changes, a triggered update is scheduled
to accelerate convergence without broadcasting immediately on every micro-change.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork
from mobility import MobilityManager


class DSDVNode(Node):
    # routes: dest -> (next_hop, metric, seq_num)
    _BC_INTERVAL = 5.0   # periodic broadcast period (seconds)
    _TRIGGER_DELAY = 0.2 # coalesce rapid changes into one triggered broadcast

    def __init__(self, nid):
        super().__init__(nid)
        self.seq = 0
        self.routes = {nid: (nid, 0, 0)}
        self._pending_bc = False

    def start_updates(self):
        self.schedule(self._BC_INTERVAL, self._periodic)

    # ------------------------------------------------------------------ #
    # periodic & triggered broadcasts
    # ------------------------------------------------------------------ #
    def _periodic(self):
        self.seq += 2  # even sequence numbers signify valid routes
        self.routes[self.nid] = (self.nid, 0, self.seq)
        self._broadcast_table()
        self.schedule(self._BC_INTERVAL, self._periodic)

    def _schedule_triggered(self):
        if not self._pending_bc:
            self._pending_bc = True
            self.schedule(self._TRIGGER_DELAY, self._triggered)

    def _triggered(self):
        self._pending_bc = False
        self._broadcast_table()

    def _broadcast_table(self):
        table = list(self.routes.items())  # [(dest, (next, metric, seq)), ...]
        self.broadcast(('TABLE', self.nid, table))

    # ------------------------------------------------------------------ #
    # message handling
    # ------------------------------------------------------------------ #
    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'TABLE':
            _, _advertiser, table = msg
            changed = False
            for dest, (_via, metric, seq) in table:
                if dest == self.nid:
                    continue
                new_metric = metric + 1   # one extra hop to reach advertiser
                cur = self.routes.get(dest)
                if cur is None:
                    self.routes[dest] = (sender, new_metric, seq)
                    changed = True
                elif seq > cur[2]:
                    # fresher information always wins
                    self.routes[dest] = (sender, new_metric, seq)
                    changed = True
                elif seq == cur[2] and new_metric < cur[1]:
                    # same freshness but shorter path
                    self.routes[dest] = (sender, new_metric, seq)
                    changed = True
            if changed:
                self._schedule_triggered()

        elif kind == 'DATA':
            _, src, dest, payload = msg
            if dest == self.nid:
                self.net.log(f"{self.nid}: DATA from {src} payload={payload!r}")
            elif dest in self.routes:
                self.unicast(self.routes[dest][0], msg)
            else:
                self.net.log(f"{self.nid}: no route to {dest}, dropping DATA")

    # ------------------------------------------------------------------ #
    # application interface
    # ------------------------------------------------------------------ #
    def send_data(self, dest, payload='pkt'):
        if dest in self.routes:
            r = self.routes[dest]
            self.net.log(f"{self.nid}: DATA -> {dest} via {r[0]} (metric={r[1]}, seq={r[2]})")
            self.unicast(r[0], ('DATA', self.nid, dest, payload))
        else:
            self.net.log(f"{self.nid}: no route to {dest}")


# --- helpers ---
def trace_route(net, src, dst):
    """Follow next-hop pointers from src to dst; return path list or None."""
    path, cur, visited = [src], src, {src}
    while cur != dst:
        r = net.nodes[cur].routes.get(dst)
        if not r or r[0] in visited:
            return None
        cur = r[0]
        path.append(cur)
        visited.add(cur)
    return path

def show_phase(net, label):
    print(f"\n{'='*55}\n  {label}  (t={net.loop.time:.1f})\n{'='*55}")
    for n in sorted(net.nodes):
        pos = tuple(round(c, 1) for c in net.pos[n])
        print(f"  {n} at {pos}  neighbors: {net.neighbors(n)}")

def show_tables(net):
    print("\nRoute tables:")
    for nid in sorted(net.nodes):
        routes = net.nodes[nid].routes
        entries = ", ".join(
            f"{d}->via {v[0]} m={v[1]} s={v[2]}"
            for d, v in sorted(routes.items()) if d != nid
        )
        print(f"  {nid}: " + (entries or "(only self)"))


# --- setup: 7 nodes in an 8x5 area ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=2.5, tx_time=0.5, loss=0.0, seed=4, verbose=False)
for nid, x, y in [('A',0,2), ('B',2,4), ('C',2,0), ('D',4,2), ('E',6,4), ('F',6,0), ('G',8,2)]:
    net.add_node(DSDVNode(nid), x, y)

mob = MobilityManager(net, interval=0.5, speed=0.4, bounds=(8, 5))

# Start mobility and periodic broadcasts together so tables converge as
# nodes drift into range of one another (initial positions are out of range).
mob.start('waypoint')
for node in net.nodes.values():
    node.start_updates()


# --- phase 1: nodes have moved into range; pause, verify tables, send data ---
def phase1():
    mob.stop()
    show_phase(net, "Phase 1 – topology after initial movement (DSDV converged)")
    show_tables(net)
    route = trace_route(net, 'A', 'G')
    print(f"\n  Traced route A->G: {' -> '.join(route)}" if route else "\n  No route!")
    net.nodes['A'].send_data('G', payload='hello-G')
    mob.start('waypoint')   # resume movement

# --- phase 2: nodes have moved more; proactive tables should have adapted ---
def phase2():
    mob.stop()
    show_phase(net, "Phase 2 – topology after more movement")
    show_tables(net)
    route = trace_route(net, 'A', 'G')
    print(f"\n  Traced route A->G: {' -> '.join(route)}" if route else "\n  No route!")
    net.nodes['A'].send_data('G', payload='hello-G-2')


loop.schedule(10.0, phase1)
loop.schedule(25.0, phase2)
loop.run(until=35)

print("\nFinal route tables:")
for nid in sorted(net.nodes):
    routes = net.nodes[nid].routes
    entries = ", ".join(
        f"{d}->via {v[0]} m={v[1]} s={v[2]}"
        for d, v in sorted(routes.items()) if d != nid
    )
    print(f"  {nid}: " + (entries or "(only self)"))
