"""Encounter-based contact model for intermittently connected networks (DTN).

Behind the scenes, non-encountering nodes are kept far apart (no radio neighbors).
When a pair encounters, both are co-located so standard unicast/broadcast works
through pywisim's normal send/deliver path. Positions restore after the encounter.
"""

class EncounterManager:
    def __init__(self, net, rate=1.0, duration=1.0):
        self.net, self.rate, self.running = net, rate, False
        self.duration, self._eid, self._cur = duration, 0, {}
        self._home = {}
        for i, nid in enumerate(net.nodes):               # isolate all nodes
            self._home[nid] = (1e6 * (i + 1), 0)
            net.pos[nid] = self._home[nid]

    def start(self):
        self.running = True
        self._next()

    def stop(self): self.running = False

    def _next(self):
        if not self.running: return
        self.net.loop.schedule(self.net.rng.expovariate(self.rate), self._encounter)

    def _encounter(self):
        if not self.running: return
        nids = list(self.net.nodes)
        a, b = self.net.rng.sample(nids, 2)
        self.net.log(f"encounter: {a} <-> {b}")
        self._eid += 1; eid = self._eid
        self._cur[a] = self._cur[b] = eid
        self.net.pos[a] = self.net.pos[b] = (-1e6 * eid, 0) # co-locate pair
        self.net.nodes[a].on_receive(('ENCOUNTER',), b)       # trigger exchange
        self.net.nodes[b].on_receive(('ENCOUNTER',), a)
        self.net.loop.schedule(self.duration, self._end, a, b, eid)
        self._next()

    def _end(self, a, b, eid):                              # separate after encounter
        if self._cur.get(a) == eid: self.net.pos[a] = self._home[a]; del self._cur[a]
        if self._cur.get(b) == eid: self.net.pos[b] = self._home[b]; del self._cur[b]
