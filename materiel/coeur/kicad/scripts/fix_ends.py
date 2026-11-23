"""Prolonge jusqu'au centre de la pastille toute fin de piste qui s'arrête à côté d'une pastille du même net
(coins arrondis), et fusionne les vias d'un même net trop proches. usage : fix_ends.py carte.kicad_pcb"""
import sys, math, pcbnew
from pcbnew import ToMM, FromMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
pads = [(p, fp.GetReference()) for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname()]
tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
def connected(pt, layer, net, me):
    for t in tracks:
        if t is me or t.GetNetname() != net or t.GetLayer() != layer: continue
        if t.HitTest(pt, 0): return True
    for v in vias:
        if v.GetNetname() == net and v.HitTest(pt, 0): return True
    for p, _ in pads:
        if p.GetNetname() == net and p.IsOnLayer(layer) and p.HitTest(pt, 0): return True
    return False
added = 0
for t in list(tracks):
    for pt in (t.GetStart(), t.GetEnd()):
        if connected(pt, t.GetLayer(), t.GetNetname(), t): continue
        best = None
        for p, ref in pads:
            if p.GetNetname() != t.GetNetname() or not p.IsOnLayer(t.GetLayer()): continue
            d = math.hypot(ToMM(pt.x - p.GetPosition().x), ToMM(pt.y - p.GetPosition().y))
            if d < 1.0 and (best is None or d < best[0]): best = (d, p)
        if best:
            n = pcbnew.PCB_TRACK(b); n.SetStart(pt); n.SetEnd(best[1].GetPosition()); n.SetWidth(t.GetWidth())
            n.SetLayer(t.GetLayer()); n.SetNet(t.GetNet()); b.Add(n); added += 1
print("prolongements :", added)
# fusion des vias d'un même net trop proches (< 0,5 mm entre centres)
merged = 0
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
gone = set()
for i, a in enumerate(vias):
    if id(a) in gone: continue
    for c in vias[i + 1:]:
        if id(c) in gone or c.GetNetname() != a.GetNetname(): continue
        pa, pc = a.GetPosition(), c.GetPosition()
        if math.hypot(ToMM(pa.x - pc.x), ToMM(pa.y - pc.y)) < 0.5:
            for t in b.GetTracks():
                if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != c.GetNetname(): continue
                if t.GetStart() == pc: t.SetStart(pa)
                if t.GetEnd() == pc: t.SetEnd(pa)
            b.Remove(c); gone.add(id(c)); merged += 1
print("vias fusionnées :", merged)
b.Save(sys.argv[1])
