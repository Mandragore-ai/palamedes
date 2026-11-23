"""Vias de couture GND de la carte chargeur : partout où les deux plans de masse (dessus et dessous) sont pleins
autour du point (marge = rayon de via + 0,15 mm), sur une grille de 4 mm. Puis remplissage des zones.
usage : stitch_charger.py carte.kicad_pcb"""
import sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
VIA_D, VIA_DR, PAS = 0.6, 0.3, 4.0


def filled(layer):
    polys = []
    for z in b.Zones():
        if z.GetNetname() != "GND" or not z.IsOnLayer(layer): continue
        sp = z.GetFilledPolysList(layer)
        for i in range(sp.OutlineCount()):
            o = sp.Outline(i); pts = [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]
            if len(pts) < 3: continue
            poly = Polygon(pts)
            for h in range(sp.HoleCount(i)):
                hh = sp.Hole(i, h); poly = poly.difference(Polygon([(ToMM(hh.CPoint(k).x), ToMM(hh.CPoint(k).y)) for k in range(hh.PointCount())]))
            polys.append(poly.buffer(0))
    return unary_union(polys)


both = filled(pcbnew.F_Cu).intersection(filled(pcbnew.B_Cu)).buffer(-(VIA_D / 2 + 0.15))
existing = [ToMM(t.GetPosition().x) for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
vias = [(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)) for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
minx, miny, maxx, maxy = both.bounds
n = 0
x = minx
gnd = b.FindNet("GND")
while x <= maxx:
    y = miny
    while y <= maxy:
        if both.contains(Point(x, y)) and all((x - vx) ** 2 + (y - vy) ** 2 > 1.0 for vx, vy in vias):
            v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetWidth(FromMM(VIA_D))
            v.SetDrill(FromMM(VIA_DR)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
            vias.append((x, y)); n += 1
        y += PAS
    x += PAS
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
# second passage : chaque îlot de masse sans via en reçoit une, si elle tient aussi dans le plan de l'autre face
gv = [(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
fF, fB = filled(pcbnew.F_Cu), filled(pcbnew.B_Cu)
ajout = 0
for la, other in ((fF, fB), (fB, fF)):
    geoms = getattr(la, "geoms", [la])
    for isl in geoms:
        if any(isl.contains(Point(v)) for v in gv): continue
        zone_ok = isl.intersection(other).buffer(-(VIA_D / 2 + 0.15))
        if zone_ok.is_empty: print("îlot sans via possible :", [round(c, 2) for c in isl.bounds]); continue
        pt = zone_ok.representative_point()
        v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(pt.x), FromMM(pt.y))); v.SetWidth(FromMM(VIA_D))
        v.SetDrill(FromMM(VIA_DR)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v); gv.append((pt.x, pt.y)); ajout += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("vias de couture :", n, "+ îlots :", ajout)
