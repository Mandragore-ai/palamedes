"""Relie au plan principal les morceaux de masse isolés : union des morceaux (dessus/dessous) reliés par des vias ;
pour chaque groupe isolé, pose une via là où un de ses morceaux recouvre un morceau du groupe principal.
usage : join_gnd.py carte.kicad_pcb"""
import sys, pcbnew
from pcbnew import ToMM, FromMM, VECTOR2I
from shapely.geometry import Polygon, Point
b = pcbnew.LoadBoard(sys.argv[1]); gnd = b.FindNet("GND")
import json
a_relier = []
for it in range(6):
    a_relier = []
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pieces = []
    for z in b.Zones():
        if z.GetNetname() != "GND": continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            sp = z.GetFilledPolysList(layer)
            for i in range(sp.OutlineCount()):
                o = sp.Outline(i); P = Polygon([(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]).buffer(0)
                for h in range(sp.HoleCount(i)):
                    hh = sp.Hole(i, h); P = P.difference(Polygon([(ToMM(hh.CPoint(k).x), ToMM(hh.CPoint(k).y)) for k in range(hh.PointCount())]))
                pieces.append((layer, P))
    parent = list(range(len(pieces)))
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    vias = [(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    for v in vias:
        hit = [k for k, (l, P) in enumerate(pieces) if P.buffer(0.05).contains(Point(v))]
        for k in hit[1:]: parent[find(k)] = find(hit[0])
    # les pastilles traversantes GND relient aussi les deux faces
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                q = (ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
                hit = [k for k, (l, P) in enumerate(pieces) if P.buffer(0.6).contains(Point(q))]
                for k in hit[1:]: parent[find(k)] = find(hit[0])
    main = find(max(range(len(pieces)), key=lambda k: pieces[k][1].area))
    groups = {}
    for k in range(len(pieces)): groups.setdefault(find(k), []).append(k)
    lonely = [g for r, g in groups.items() if r != main]
    if not lonely: print("masse : un seul groupe"); break
    added = 0
    mainF = [pieces[k][1] for k in groups[main] if pieces[k][0] == pcbnew.F_Cu]
    mainB = [pieces[k][1] for k in groups[main] if pieces[k][0] == pcbnew.B_Cu]
    for g in lonely:
        done = False
        for k in g:
            l, P = pieces[k]
            for M in (mainB if l == pcbnew.F_Cu else mainF):
                ok = P.intersection(M).buffer(-0.45)
                if not ok.is_empty:
                    pt = ok.representative_point()
                    if all((pt.x - vx) ** 2 + (pt.y - vy) ** 2 > 0.81 for vx, vy in vias):
                        v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(pt.x), FromMM(pt.y))); v.SetWidth(FromMM(0.6))
                        v.SetDrill(FromMM(0.3)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
                        vias.append((pt.x, pt.y)); added += 1; done = True; break
            if done: break
        if not done:
            print("groupe isolé sans solution :", [(b.GetLayerName(pieces[k][0]), [round(c, 1) for c in pieces[k][1].bounds]) for k in g])
            # à relier par une piste : on note une pastille GND du groupe et les vias du groupe principal
            seeds = []
            for fp in b.GetFootprints():
                for p in fp.Pads():
                    if p.GetNetname() == "GND":
                        q = Point(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
                        if any(pieces[k][1].buffer(0.05).contains(q) for k in g): seeds.append((q.x, q.y))
            for k in g:
                for v in vias:
                    if pieces[k][1].buffer(0.05).contains(Point(v)): seeds.append(v)
            mainv = [v for v in vias if any(pieces[k][1].buffer(0.05).contains(Point(v)) for k in groups[main])]
            a_relier.append({"graines": seeds, "principal": mainv})
    print(f"passe {it} : {len(lonely)} groupes isolés, {added} vias ajoutées")
    if added == 0: break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[1])
json.dump(a_relier, open("/tmp/gnd_a_relier.json", "w"))
print("groupes à relier par piste :", len(a_relier))
