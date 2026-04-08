"""AODV over a MANET – route discovery adapts as nodes move."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork
from mobility import MobilityManager

class AODVNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.seq, self.routes, self.seen_rreqs = 0, {}, set()

    def on_receive(self, msg, sender):
        if msg[0] == 'RREQ':
            _, orig, dest, seq, rid, hops = msg
            key = (orig, dest, seq, rid)
            if key in self.seen_rreqs: return
            self.seen_rreqs.add(key); hops += 1
            self._update(orig, sender, seq, hops)
            if dest == self.nid:
                self.seq = max(self.seq, seq) + 1
                self._rrep(dest, orig)
            elif dest in self.routes: self._rrep(dest, orig)
            else: self.broadcast(('RREQ', orig, dest, seq, rid, hops))
        elif msg[0] == 'RREP':
            _, dest, dseq, orig, hops = msg; hops += 1
            self._update(dest, sender, dseq, hops)
            if orig == self.nid:
                self.net.log(f"{self.nid}: route to {dest} via {self.routes[dest][0]}, hops={hops}")
            elif orig in self.routes:
                self.unicast(self.routes[orig][0], ('RREP', dest, dseq, orig, hops))

    def _update(self, dest, via, seq, hops):
        cur = self.routes.get(dest)
        if not cur or seq > cur[1] or (seq == cur[1] and hops < cur[2]):
            self.routes[dest] = (via, seq, hops)

    def _rrep(self, dest, orig):
        if orig in self.routes:
            self.unicast(self.routes[orig][0], ('RREP', dest, self.seq, orig, 0))

    def discover(self, dest):
        self.seq += 1
        self.seen_rreqs.add((self.nid, dest, self.seq, self.seq))
        self.broadcast(('RREQ', self.nid, dest, self.seq, self.seq, 0))

# --- helpers ---
def trace_route(net, src, dst):
    path, cur = [src], src
    while cur != dst:
        r = net.nodes[cur].routes.get(dst)
        if not r or r[0] in path: return None
        cur = r[0]; path.append(cur)
    return path

def show_phase(net, label):
    print(f"\n{'='*55}\n  {label}  (t={net.loop.time:.1f})\n{'='*55}")
    for n in sorted(net.nodes):
        pos = tuple(round(c,1) for c in net.pos[n])
        print(f"  {n} at {pos}  neighbors: {net.neighbors(n)}")

def reset_routes(net):
    for n in net.nodes.values():
        n.seq, n.routes, n.seen_rreqs = 0, {}, set()

# --- setup: 7 nodes in a 8x5 area ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=2.5, tx_time=0.5, loss=0.0, seed=4, verbose=False)
for nid, x, y in [('A',0,2), ('B',2,4), ('C',2,0), ('D',4,2), ('E',6,4), ('F',6,0), ('G',8,2)]:
    net.add_node(AODVNode(nid), x, y)

mob = MobilityManager(net, interval=0.5, speed=0.4, bounds=(8, 5))

# --- phase 1: movement, then pause and discover ---
def phase1():
    mob.stop()
    show_phase(net, "Phase 1 – topology after initial movement")
    net.nodes['A'].discover('G')

def report1():
    route = trace_route(net, 'A', 'G')
    print(f"\n  Route found: {' -> '.join(route)}" if route else "\n  No route found!")
    reset_routes(net)
    mob.start('waypoint')                      # resume movement

# --- phase 2: more movement, then pause and discover again ---
def phase2():
    mob.stop()
    show_phase(net, "Phase 2 – topology after more movement")
    net.nodes['A'].discover('G')

def report2():
    route = trace_route(net, 'A', 'G')
    print(f"\n  Route found: {' -> '.join(route)}" if route else "\n  No route found!")

mob.start('waypoint')
loop.schedule(5.0, phase1)
loop.schedule(10.0, report1)
loop.schedule(20.0, phase2)
loop.schedule(25.0, report2)
loop.run(until=30)

print("\nFinal route tables:")
for nid in sorted(net.nodes):
    r = net.nodes[nid].routes
    print(f"  {nid}: " + (", ".join(f"{d}->via {v[0]} ({v[2]}h)" for d, v in sorted(r.items())) or "(empty)"))
