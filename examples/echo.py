"""Echo algorithm: build a spanning tree from an initiator node."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class EchoNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.parent = None
        self.children = []
        self.echoes_needed = 0
        self.echoes_got = 0
    def on_receive(self, msg, sender):
        if msg[0] == 'EXPLORE':
            if self.parent is None:
                self.parent = sender
                others = [n for n in self.net.neighbors(self.nid) if n != sender]
                self.echoes_needed = len(others)
                if not others:
                    self.unicast(sender, ('ECHO', self.nid))
                else:
                    for n in others: self.unicast(n, ('EXPLORE',))
            else:
                self.unicast(sender, ('ECHO', self.nid))
        elif msg[0] == 'ECHO':
            self.children.append(msg[1])
            self.echoes_got += 1
            if self.echoes_got >= self.echoes_needed:
                if self.parent == 'ROOT':
                    self.net.log(f"{self.nid}: echo complete! tree built.")
                else:
                    self.unicast(self.parent, ('ECHO', self.nid))
    def initiate(self):
        self.parent = 'ROOT'
        nbrs = self.net.neighbors(self.nid)
        self.echoes_needed = len(nbrs)
        self.net.log(f"{self.nid}: initiating echo")
        for n in nbrs: self.unicast(n, ('EXPLORE',))

# --- network: line topology ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=1.5, seed=42, verbose=True)
for nid, x, y in [('A',0,0), ('B',1,0), ('C',2,0), ('D',3,0), ('E',4,0)]:
    net.add_node(EchoNode(nid), x, y)

print("Topology:", {n: net.neighbors(n) for n in net.nodes})
loop.schedule(1.0, net.nodes['A'].initiate)
loop.run(until=30)

print("\nSpanning tree:")
for nid in sorted(net.nodes):
    n = net.nodes[nid]
    print(f"  {nid}: parent={n.parent}, children={n.children}")
