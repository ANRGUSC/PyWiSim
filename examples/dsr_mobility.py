"""DSR – Dynamic Source Routing over a mobile ad-hoc network.

DSR is a reactive protocol: routes are discovered on demand by flooding RREQs
that accumulate the full path.  The discovered path is embedded in every DATA
packet (source routing), so intermediate nodes need no per-destination state.
Nodes also cache routes they learn from overheard RREPs.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pywisim import EventLoop, Node, WirelessNetwork
from mobility import MobilityManager


class DSRNode(Node):
    def __init__(self, nid):
        super().__init__(nid)
        self.route_cache = {}    # dest -> [self.nid, ..., dest]
        self.seen_rreqs = set()  # (orig, dest, rid)
        self.pending = {}        # dest -> [payload, ...]
        self._rid = 0

    def on_receive(self, msg, sender):
        kind = msg[0]

        if kind == 'RREQ':
            _, orig, dest, rid, path = msg
            key = (orig, dest, rid)
            if key in self.seen_rreqs:
                return
            self.seen_rreqs.add(key)
            new_path = path + [self.nid]

            if dest == self.nid:
                # Path fully accumulated; send RREP back along reversed path
                self.net.log(f"{self.nid}: RREP path={new_path}")
                if len(new_path) > 1:
                    self.unicast(new_path[-2], ('RREP', orig, dest, new_path))
            elif self.nid not in path:
                # Check cache for a shortcut to dest
                if dest in self.route_cache:
                    cached = self.route_cache[dest]   # [self.nid, ..., dest]
                    full_path = new_path + cached[1:]
                    if len(full_path) > 1:
                        self.unicast(full_path[-2], ('RREP', orig, dest, full_path))
                else:
                    self.broadcast(('RREQ', orig, dest, rid, new_path))

        elif kind == 'RREP':
            _, orig, dest, path = msg
            try:
                idx = path.index(self.nid)
            except ValueError:
                return
            # Cache the route segment from here to dest
            segment = path[idx:]
            cur = self.route_cache.get(dest)
            if not cur or len(segment) < len(cur):
                self.route_cache[dest] = segment
            if self.nid == orig:
                self.net.log(f"{self.nid}: route to {dest} -> {' -> '.join(path)}")
                self._flush_pending(dest)
            elif idx > 0:
                self.unicast(path[idx - 1], ('RREP', orig, dest, path))

        elif kind == 'DATA':
            _, dest, path, payload = msg
            if self.nid == dest:
                self.net.log(f"{self.nid}: DATA received payload={payload!r}")
            else:
                try:
                    idx = path.index(self.nid)
                    if idx + 1 < len(path):
                        self.unicast(path[idx + 1], ('DATA', dest, path, payload))
                except ValueError:
                    pass  # stale route; real DSR would send RERR

    def _flush_pending(self, dest):
        for payload in self.pending.pop(dest, []):
            self._deliver_data(dest, payload)

    def _deliver_data(self, dest, payload):
        path = self.route_cache.get(dest)
        if path and len(path) > 1:
            self.unicast(path[1], ('DATA', dest, path, payload))
        else:
            self.net.log(f"{self.nid}: no cached route to {dest}")

    def discover(self, dest):
        self._rid += 1
        rid = self._rid
        self.seen_rreqs.add((self.nid, dest, rid))
        self.net.log(f"{self.nid}: RREQ -> {dest}")
        self.broadcast(('RREQ', self.nid, dest, rid, [self.nid]))

    def send_data(self, dest, payload='pkt'):
        if dest in self.route_cache:
            self._deliver_data(dest, payload)
        else:
            self.pending.setdefault(dest, []).append(payload)
            self.discover(dest)


# --- helpers ---
def trace_route(net, src, dst):
    path = net.nodes[src].route_cache.get(dst)
    return path if path else None

def show_phase(net, label):
    print(f"\n{'='*55}\n  {label}  (t={net.loop.time:.1f})\n{'='*55}")
    for n in sorted(net.nodes):
        pos = tuple(round(c, 1) for c in net.pos[n])
        print(f"  {n} at {pos}  neighbors: {net.neighbors(n)}")

def reset_dsr(net):
    for n in net.nodes.values():
        n.route_cache.clear()
        n.seen_rreqs.clear()
        n.pending.clear()
        n._rid = 0


# --- setup: 7 nodes in an 8x5 area ---
loop = EventLoop()
net = WirelessNetwork(loop, tx_range=2.5, tx_time=0.5, loss=0.0, seed=4, verbose=False)
for nid, x, y in [('A',0,2), ('B',2,4), ('C',2,0), ('D',4,2), ('E',6,4), ('F',6,0), ('G',8,2)]:
    net.add_node(DSRNode(nid), x, y)

mob = MobilityManager(net, interval=0.5, speed=0.4, bounds=(8, 5))


# --- phase 1: movement, then pause and discover ---
def phase1():
    mob.stop()
    show_phase(net, "Phase 1 – topology after initial movement")
    net.nodes['A'].send_data('G', payload='hello-G')

def report1():
    route = trace_route(net, 'A', 'G')
    print(f"\n  Cached route: {' -> '.join(route)}" if route else "\n  No route cached!")
    reset_dsr(net)
    mob.start('waypoint')

# --- phase 2: more movement, then pause and discover again ---
def phase2():
    mob.stop()
    show_phase(net, "Phase 2 – topology after more movement")
    net.nodes['A'].send_data('G', payload='hello-G-2')

def report2():
    route = trace_route(net, 'A', 'G')
    print(f"\n  Cached route: {' -> '.join(route)}" if route else "\n  No route cached!")


mob.start('waypoint')
loop.schedule(5.0,  phase1)
loop.schedule(10.0, report1)
loop.schedule(20.0, phase2)
loop.schedule(25.0, report2)
loop.run(until=30)

print("\nFinal route caches:")
for nid in sorted(net.nodes):
    c = net.nodes[nid].route_cache
    if c:
        for dest, path in sorted(c.items()):
            print(f"  {nid} -> {dest}: {' -> '.join(path)}")
    else:
        print(f"  {nid}: (empty)")
