"""contrôle de placement : chevauchements (pastilles + corps) et débordement du disque"""
import sys, math, itertools, pcbnew
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1]); R = 8.0; CX = CY = 100
boxes = []
for fp in b.GetFootprints():
    side = 'B' if fp.IsFlipped() else 'F'
    xs = []; ys = []
    for p in fp.Pads():
        bb = p.GetBoundingBox(); xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]; ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    for it in fp.GraphicalItems():
        if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            bb = it.GetBoundingBox(); xs += [ToMM(bb.GetLeft()), ToMM(bb.GetRight())]; ys += [ToMM(bb.GetTop()), ToMM(bb.GetBottom())]
    box = (min(xs), min(ys), max(xs), max(ys)); boxes.append((fp.GetReference(), side, box))
    worst = max(math.hypot(x - CX, y - CY) for x in box[::2] for y in box[1::2])
    pads_r = max(math.hypot(ToMM(p.GetPosition().x) - CX, ToMM(p.GetPosition().y) - CY) + max(ToMM(p.GetSize().x), ToMM(p.GetSize().y)) / 2 for p in fp.Pads())
    if pads_r > R - 0.25: print(f"BORD  {fp.GetReference()} pastille à {pads_r:.2f} mm du centre")
bad = 0
for (r1, s1, a), (r2, s2, c) in itertools.combinations(boxes, 2):
    if s1 != s2: continue
    m = 0.1
    if a[0] < c[2] - m and c[0] < a[2] - m and a[1] < c[3] - m and c[1] < a[3] - m:
        # tolérance : TP vs TP
        print(f"CHEV  {s1} {r1} / {r2}"); bad += 1
print("chevauchements:", bad)
if len(sys.argv) > 2:
    for r, s_, bx in boxes:
        if r in sys.argv[2].split(','): print(r, s_, [round(v - 100, 2) for v in bx])
