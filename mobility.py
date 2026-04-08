"""Mobility models for pywisim nodes."""
import math

class MobilityManager:
    def __init__(self, net, interval=1.0, speed=0.5, bounds=(10, 10)):
        self.net, self.interval, self.speed = net, interval, speed
        self.bx, self.by = bounds
        self.targets = {}                          # waypoint targets {nid: (tx,ty)}

    def start(self, model='waypoint'):
        self.model, self.running = model, True
        self._step()

    def stop(self): self.running = False

    def _step(self):
        if not self.running: return
        ds = self.speed * self.interval            # distance per step
        rng = self.net.rng                         # reuse network's seeded RNG
        for nid in self.net.nodes:
            x, y = self.net.pos[nid]
            if self.model == 'waypoint':
                t = self.targets.get(nid)
                if not t or math.hypot(t[0]-x, t[1]-y) < ds:
                    t = (rng.uniform(0, self.bx), rng.uniform(0, self.by))
                    self.targets[nid] = t
                ang = math.atan2(t[1]-y, t[0]-x)
                x, y = x + ds*math.cos(ang), y + ds*math.sin(ang)
            elif self.model == 'walk':
                ang = rng.uniform(0, 2*math.pi)
                x, y = x + ds*math.cos(ang), y + ds*math.sin(ang)
            self.net.pos[nid] = (max(0, min(self.bx, x)), max(0, min(self.by, y)))
        self.net.loop.schedule(self.interval, self._step)
