"""Post-traitement : relie chaque îlot de masse (F.Cu / B.Cu) au plan In1 par une via de couture,
puis remplit les zones. usage : post_stitch.py carte.kicad_pcb"""
import sys, math
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
CX = CY = 100.0
VIA_D, VIA_DR = 0.45, 0.25
CLR = 0.13               # marge au-dessus de la règle 0,10
ANT_Y = -2.8
MOD_YC = -1.6
gnd = b.FindNet("GND")


def fill():
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())


def other_copper(layer):
    """géométrie du cuivre des autres nets sur une couche (pistes, vias, pastilles)"""
    geoms = []
    for t in b.GetTracks():
        if t.GetNetname() == "GND": continue
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition(); geoms.append(Point(ToMM(p.x) - CX, ToMM(p.y) - CY).buffer(ToMM(t.GetWidth()) / 2))
        elif t.GetLayer() == layer:
            s, e = t.GetStart(), t.GetEnd()
            geoms.append(LineString([(ToMM(s.x) - CX, ToMM(s.y) - CY), (ToMM(e.x) - CX, ToMM(e.y) - CY)]).buffer(ToMM(t.GetWidth()) / 2))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND" or not p.IsOnLayer(layer): continue
            bb = p.GetBoundingBox()
            geoms.append(Polygon([(ToMM(bb.GetLeft()) - CX, ToMM(bb.GetTop()) - CY), (ToMM(bb.GetRight()) - CX, ToMM(bb.GetTop()) - CY),
                                  (ToMM(bb.GetRight()) - CX, ToMM(bb.GetBottom()) - CY), (ToMM(bb.GetLeft()) - CX, ToMM(bb.GetBottom()) - CY)]))
    return unary_union(geoms) if geoms else Polygon()


def holes():
    return [(ToMM(t.GetPosition().x) - CX, ToMM(t.GetPosition().y) - CY) for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]


def gnd_pads_xy(layer):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND" and p.IsOnLayer(layer):
                bb = p.GetBoundingBox()
                out.append(Polygon([(ToMM(bb.GetLeft()) - CX, ToMM(bb.GetTop()) - CY), (ToMM(bb.GetRight()) - CX, ToMM(bb.GetTop()) - CY),
                                    (ToMM(bb.GetRight()) - CX, ToMM(bb.GetBottom()) - CY), (ToMM(bb.GetLeft()) - CX, ToMM(bb.GetBottom()) - CY)]))
    return unary_union(out) if out else Polygon()


added = 0
for rnd in range(3):
    fill()
    blockers = {l: other_copper(l) for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)}
    padsF = gnd_pads_xy(pcbnew.F_Cu).buffer(0.05); padsB = gnd_pads_xy(pcbnew.B_Cu).buffer(0.05)
    new = 0
    for z in b.Zones():
        if z.GetNetname() != "GND" or z.IsOnLayer(pcbnew.In1_Cu): continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer): continue
            polys = z.GetFilledPolysList(layer)
            for k in range(polys.OutlineCount()):
                ol = polys.Outline(k)
                pts = [(ToMM(ol.CPoint(i).x) - CX, ToMM(ol.CPoint(i).y) - CY) for i in range(ol.PointCount())]
                if len(pts) < 3: continue
                poly = Polygon(pts)
                if poly.area < 0.3: continue
                if any(poly.contains(Point(h)) for h in holes()):
                    continue          # déjà cousu
                core = poly.buffer(-(VIA_D / 2 + 0.02))
                if core.is_empty: continue
                pads = padsF if layer == pcbnew.F_Cu else padsB
                best = None
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                c = poly.representative_point()
                x = min(xs)
                while x <= max(xs):
                    y = min(ys)
                    while y <= max(ys):
                        pt = Point(x, y)
                        under_mod = (-1.7 - 0.65 - 0.25 < x < 1.9 + 0.65 + 0.25) and (MOD_YC - 0.92 - 0.65 - 0.25 < y < MOD_YC + 3.88 + 0.65 + 0.25)
                        if (y > ANT_Y + 0.4 and not under_mod and core.contains(pt) and not pads.contains(pt)
                                and all(blockers[l].distance(pt) >= VIA_D / 2 + CLR for l in blockers)
                                and all(math.hypot(x - hx, y - hy) >= 0.55 for hx, hy in holes())):
                            d = pt.distance(c)
                            if best is None or d < best[0]: best = (d, x, y)
                        y += 0.05
                    x += 0.05
                if best:
                    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(CX + best[1]), FromMM(CY + best[2])))
                    v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_DR)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v); new += 1
                else:
                    print("îlot sans place pour une via :", pcbnew.LayerName(layer) if hasattr(pcbnew, "LayerName") else layer, round(poly.area, 2), "mm²", [round(v, 2) for v in poly.bounds])
    added += new
    if new == 0: break
fill()
b.Save(PCB)
print("vias de couture ajoutées :", added)
