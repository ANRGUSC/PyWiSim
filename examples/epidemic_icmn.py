"""Epidemic flooding over an intermittently connected mobile network (DTN)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork
from encounter import EncounterManager

class EpidemicNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.buffer = set()                        # message IDs this node carries

    def inject(self, mid):
        self.buffer.add(mid)
        self.net.log(f"{self.nid}: originated '{mid}'")

    def on_receive(self, msg, sender):
        if msg[0] == 'ENCOUNTER':                  # encounter triggers exchange
            for mid in sorted(self.buffer):
                self.unicast(sender, ('DATA', mid)) # standard pywisim send
        elif msg[0] == 'DATA' and msg[1] not in self.buffer:
            self.buffer.add(msg[1])
            self.net.log(f"  {self.nid} got '{msg[1]}' from {sender}")

# --- setup: 8 nodes, lossless encounters ---
loop = EventLoop()
net = WirelessNetwork(loop, loss=0.0, tx_time=0.01, verbose=True, seed=42)
for nid in 'ABCDEFGH':
    net.add_node(EpidemicNode(nid), 0, 0)

enc = EncounterManager(net, rate=1.5, duration=1.0)

# A originates a file at t=0.1
loop.schedule(0.1, net.nodes['A'].inject, 'file.pdf')
enc.start()

# periodic status checks; stop once all nodes have the file
done = False
def status():
    global done
    if done: return
    have = sorted(n for n in net.nodes if net.nodes[n].buffer)
    print(f"\n  Status (t={loop.time:.1f}): {len(have)}/{len(net.nodes)} nodes have file: {have}\n")
    if len(have) == len(net.nodes):
        enc.stop(); done = True

for t in range(2, 30, 2):
    loop.schedule(float(t), status)

loop.run(until=30)
