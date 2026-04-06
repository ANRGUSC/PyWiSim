"""pywisim – minimal wireless network discrete-event simulator.

Subclass Node, override on_receive(msg, sender), use broadcast/unicast/schedule.
"""
import heapq, math, random

class EventLoop:
    def __init__(self): self.time, self._q, self._seq = 0.0, [], 0
    def schedule(self, delay, fn, *a):
        self._seq += 1; heapq.heappush(self._q, (self.time + max(0, delay), self._seq, fn, a))
    def run(self, until=100):
        while self._q and self.time <= until:
            t, _, fn, a = heapq.heappop(self._q); self.time = t; fn(*a)

class Node:
    def __init__(self, nid): self.nid, self.net = nid, None
    def on_receive(self, msg, sender): pass
    def broadcast(self, msg): self.net._send(self.nid, self.net.neighbors(self.nid), msg)
    def unicast(self, dest, msg): self.net._send(self.nid, [dest], msg)
    def schedule(self, delay, fn, *a): self.net.loop.schedule(delay, fn, *a)

class WirelessNetwork:
    def __init__(self, loop, tx_range=1.6, loss=0.02, tx_time=0.5, seed=42, verbose=True):
        self.loop, self.R, self.loss, self.tx = loop, tx_range, loss, tx_time
        self.verbose, self.rng = verbose, random.Random(seed)
        self.nodes, self.pos, self._txs, self._mid = {}, {}, [], 0
    def add_node(self, n, x, y): self.nodes[n.nid] = n; self.pos[n.nid] = (x, y); n.net = self
    def log(self, s):
        if self.verbose: print(f"[{self.loop.time:.2f}] {s}")
    def dist(self, a, b): return math.hypot(self.pos[a][0]-self.pos[b][0], self.pos[a][1]-self.pos[b][1])
    def neighbors(self, nid): return [o for o in self.nodes if o != nid and self.dist(nid, o) <= self.R]
    def _busy(self, nid):
        return any(s <= self.loop.time < e and self.dist(nid, snd) <= self.R for _, s, e, snd in self._txs)
    def _send(self, sender, targets, msg):
        if self._busy(sender):
            return self.loop.schedule(self.rng.uniform(.2, .6), self._send, sender, targets, msg)
        self._mid += 1; mid = self._mid
        self._txs.append((mid, self.loop.time, self.loop.time + self.tx, sender))
        self.log(f"{sender} >> {msg}")
        for r in targets: self.loop.schedule(.01, self._deliver, sender, r, msg, mid)
        self.loop.schedule(self.tx, self._end, mid)
    def _end(self, mid): self._txs = [t for t in self._txs if t[0] != mid]
    def _deliver(self, sender, recv, msg, mid):
        if not any(m == mid for m, *_ in self._txs): return
        d = self.dist(sender, recv)
        if d > self.R: return
        if self.loss and self.rng.random() > (1 - self.loss) * (1 - .5 * (d / self.R) ** 2): return
        self.log(f"{recv} <- {sender}: {msg}")
        self.nodes[recv].on_receive(msg, sender)
