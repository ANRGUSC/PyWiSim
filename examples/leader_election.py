"""Flood-based leader election: elect the node with the highest random value."""
import sys, random; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class ElectionNode(Node):
    def __init__(self, nid, value):
        super().__init__(nid)
        self.value = value
        self.leader = value
        self.seen = {nid}
    def on_receive(self, msg, sender):
        _, origin, val = msg
        if origin not in self.seen:
            self.seen.add(origin)
            if val > self.leader: self.leader = val
            self.broadcast(msg)
    def announce(self):
        self.broadcast(('ELECT', self.nid, self.value))

# --- network: line topology with dense connectivity for reliable flooding ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=2.5, loss=0.0, tx_time=0.1, seed=42, verbose=True)
rng = random.Random(99)
for nid, x, y in [('A',0,0), ('B',1,0), ('C',2,0), ('D',3,0), ('E',4,0)]:
    net.add_node(ElectionNode(nid, rng.randint(1, 100)), x, y)

vals = {n: net.nodes[n].value for n in net.nodes}
print("Values:", vals)
print("Topology:", {n: net.neighbors(n) for n in net.nodes})

for i, n in enumerate(net.nodes.values()): loop.schedule(1.0 + i * 0.2, n.announce)
loop.run(until=30)

true_max = max(vals.values())
print(f"\nResults (true max = {true_max}):")
for nid in sorted(net.nodes):
    n = net.nodes[nid]
    tag = " <-- LEADER" if n.leader == n.value and n.value == true_max else ""
    print(f"  {nid} (val={n.value}): leader={n.leader}{tag}")
