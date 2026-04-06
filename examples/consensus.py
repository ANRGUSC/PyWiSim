"""Simple flood-and-majority consensus on a binary value."""
import sys, random; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class ConsensusNode(Node):
    def __init__(self, nid, value):
        super().__init__(nid)
        self.value = value
        self.votes = {nid: value}
        self.decided = None
    def on_receive(self, msg, sender):
        _, origin, val = msg
        if origin not in self.votes:
            self.votes[origin] = val
            self.broadcast(msg)
    def propose(self):
        self.broadcast(('VOTE', self.nid, self.value))
    def decide(self):
        ones = sum(self.votes.values())
        self.decided = 1 if ones > len(self.votes) / 2 else 0

# --- network: line topology with dense connectivity for reliable flooding ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=2.5, loss=0.0, tx_time=0.1, seed=42, verbose=True)
rng = random.Random(42)
for nid, x, y in [('A',0,0), ('B',1,0), ('C',2,0), ('D',3,0), ('E',4,0)]:
    net.add_node(ConsensusNode(nid, rng.choice([0, 1])), x, y)

vals = {n: net.nodes[n].value for n in net.nodes}
print("Initial values:", vals)
print("Topology:", {n: net.neighbors(n) for n in net.nodes})

for i, n in enumerate(net.nodes.values()): loop.schedule(1.0 + i * 0.2, n.propose)
for n in net.nodes.values(): loop.schedule(15.0, n.decide)
loop.run(until=20)

print("\nDecisions:")
for nid in sorted(net.nodes):
    n = net.nodes[nid]
    print(f"  {nid} (initial={n.value}): votes={dict(sorted(n.votes.items()))}, decided={n.decided}")
