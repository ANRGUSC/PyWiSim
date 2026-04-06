"""Flooding / reliable broadcast over a multi-hop wireless network."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class FloodNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.seen = set()
    def on_receive(self, msg, sender):
        _, origin, payload = msg
        if origin not in self.seen:
            self.seen.add(origin)
            self.net.log(f"{self.nid} got '{payload}' from {origin} (via {sender})")
            self.broadcast(msg)
    def flood(self, payload):
        self.seen.add(self.nid)
        self.net.log(f"{self.nid} starts flood: '{payload}'")
        self.broadcast(('FLOOD', self.nid, payload))

# --- network: line topology A--B--C--D--E ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=1.5, seed=42, verbose=True)
for nid, x, y in [('A',0,0), ('B',1,0), ('C',2,0), ('D',3,0), ('E',4,0)]:
    net.add_node(FloodNode(nid), x, y)

print("Topology:", {n: net.neighbors(n) for n in net.nodes})
loop.schedule(1.0, net.nodes['A'].flood, "hello!")
loop.run(until=20)
print("\nDelivered to:", [n for n in sorted(net.nodes) if net.nodes[n].seen])
