"""Two-phase commit protocol over a wireless network."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork

class Coordinator(Node):
    def __init__(self, nid, participants):
        super().__init__(nid)
        self.participants = participants
        self.votes = {}
        self.decision = None
    def on_receive(self, msg, sender):
        if msg[0] == 'VOTE':
            self.votes[sender] = msg[1]
            self.net.log(f"{self.nid}: got {msg[1]} from {sender}")
            if len(self.votes) >= len(self.participants):
                self.decision = 'COMMIT' if all(v == 'YES' for v in self.votes.values()) else 'ABORT'
                self.net.log(f"{self.nid}: decided {self.decision}")
                for p in self.participants: self.unicast(p, ('DECISION', self.decision))
    def start(self):
        self.net.log(f"{self.nid}: sending PREPARE to {self.participants}")
        for p in self.participants: self.unicast(p, ('PREPARE',))

class Participant(Node):
    def __init__(self, nid, vote_yes=True):
        super().__init__(nid)
        self.vote_yes = vote_yes
        self.decision = None
    def on_receive(self, msg, sender):
        if msg[0] == 'PREPARE':
            vote = 'YES' if self.vote_yes else 'NO'
            self.net.log(f"{self.nid}: voting {vote}")
            self.unicast(sender, ('VOTE', vote))
        elif msg[0] == 'DECISION':
            self.decision = msg[1]
            self.net.log(f"{self.nid}: outcome = {self.decision}")

# --- network: star topology (coordinator in center) ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=1.5, loss=0.0, seed=42, verbose=True)
net.add_node(Coordinator('C', ['P1', 'P2', 'P3']), 0, 0)
net.add_node(Participant('P1', vote_yes=True), 1, 0)
net.add_node(Participant('P2', vote_yes=True), 0, 1)
net.add_node(Participant('P3', vote_yes=False), -1, 0)   # <-- will vote NO

print("Topology:", {n: net.neighbors(n) for n in net.nodes})
print()
loop.schedule(1.0, net.nodes['C'].start)
loop.run(until=20)
