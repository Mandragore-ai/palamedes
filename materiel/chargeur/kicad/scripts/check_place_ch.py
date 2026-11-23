"""contrôle de placement de la carte chargeur : chevauchements (dessous), bord, disques de bobines"""
import sys, math, itertools, json, pcbnew
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1]); G = json.load(open(sys.argv[1].rsplit('/',1)[0] + "/chargeur_geometrie.json"))
X0, Y0, D = G["transfo"]["X0"], G["transfo"]["Y0"], G["transfo"]["DBOX"]
bx = lambda X: X - X0; by = lambda Y: D - (Y - Y0)
boxes = []
for fp in b.GetFootprints():
    xs, ys = [], []
    for p in fp.Pads():
        bb = p.GetBoundingBox(); xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]; ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    for it in fp.GraphicalItems():
        if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            bb = it.GetBoundingBox(); xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]; ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    x0, x1, y0, y1 = bx(min(xs)), bx(max(xs)), by(max(ys)), by(min(ys))
    boxes.append((fp.GetReference(), (x0, y0, x1, y1)))
bad = 0
c0, cy0, c1, cy1 = G["contour"]
for r, (x0, y0, x1, y1) in boxes:
    if r != "J1" and (x0 < c0 + 0.5 or x1 > c1 - 0.5 or y0 < cy0 + 0.5 or y1 > cy1 - 0.5): print("BORD", r); bad += 1
    for (ex, ey) in G["encoches"]:
        if math.hypot(max(x0, min(ex, x1)) - ex, max(y0, min(ey, y1)) - ey) < G["r_encoche"] + 0.5: print("ENCOCHE", r); bad += 1
    for k, c in G["bobines"].items():
        cx, cy = c["centre"]
        if math.hypot(max(x0, min(cx, x1)) - cx, max(y0, min(cy, y1)) - cy) < 6.4: print("BOBINE", k, r); bad += 1
for (r1, a), (r2, c) in itertools.combinations(boxes, 2):
    m = 0.15
    if a[0] < c[2] - m and c[0] < a[2] - m and a[1] < c[3] - m and c[1] < a[3] - m: print("CHEV", r1, r2); bad += 1
print("problèmes:", bad)
for r, bxx in boxes:
    if len(sys.argv) > 2 and r in sys.argv[2].split(","): print(r, [round(v, 2) for v in bxx])
