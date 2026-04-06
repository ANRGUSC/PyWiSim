"""AODV reactive routing protocol."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class AODVNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.seq = 0
        self.routes = {}        # dest -> (next_hop, seq, hops)
        self.seen_rreqs = set()

    def on_receive(self, msg, sender):
        if msg[0] == 'RREQ':
            _, orig, dest, seq, rid, hops = msg
            key = (orig, dest, seq, rid)
            if key in self.seen_rreqs: return
            self.seen_rreqs.add(key)
            hops += 1
            self._update(orig, sender, seq, hops)
            if dest == self.nid:
                self.seq = max(self.seq, seq) + 1
                self._rrep(dest, orig)
            elif dest in self.routes:
                self._rrep(dest, orig)
            else:
                self.broadcast(('RREQ', orig, dest, seq, rid, hops))
        elif msg[0] == 'RREP':
            _, dest, dseq, orig, hops = msg
            hops += 1
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
        self.net.log(f"{self.nid}: route discovery -> {dest}")
        self.broadcast(('RREQ', self.nid, dest, self.seq, self.seq, 0))

# --- network: line topology A--B--C--D--E ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=1.5, tx_time=0.8, seed=7, verbose=True)
for nid, x, y in [('A',0,0), ('B',1,0), ('C',2,0), ('D',3,0), ('E',4,0)]:
    net.add_node(AODVNode(nid), x, y)

print("Topology:", {n: net.neighbors(n) for n in net.nodes})
loop.schedule(1.0, net.nodes['A'].discover, 'E')
loop.run(until=25)

print("\nRoute tables:")
for nid in sorted(net.nodes):
    r = net.nodes[nid].routes
    print(f"  {nid}: " + (", ".join(f"{d}->via {v[0]} ({v[2]}h)" for d, v in sorted(r.items())) or "(empty)"))
