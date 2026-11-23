import sys, pcbnew, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, x1, y0, y1 = map(float, sys.argv[3].split(",")) if len(sys.argv) > 3 else (50, 207, 50, 137)
fig, ax = plt.subplots(figsize=(16, 16 * (y1 - y0) / (x1 - x0)))
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox(); c = "#888" if not p.GetNetname() else ("#3a3" if p.GetNetname() == "GND" else "#c60")
        ax.add_patch(plt.Rectangle((ToMM(bb.GetLeft()), ToMM(bb.GetTop())), ToMM(bb.GetWidth()), ToMM(bb.GetHeight()), color=c, alpha=0.6))
    r = fp.GetReference(); pos = fp.GetPosition()
    if x0 < ToMM(pos.x) < x1 and y0 < ToMM(pos.y) < y1: ax.text(ToMM(pos.x), ToMM(pos.y), r, fontsize=6, ha="center")
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        ax.add_patch(plt.Circle((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)), ToMM(t.GetWidth()) / 2, color="k"))
    else:
        col = "r" if t.GetLayer() == pcbnew.F_Cu else "b"
        ax.plot([ToMM(t.GetStart().x), ToMM(t.GetEnd().x)], [ToMM(t.GetStart().y), ToMM(t.GetEnd().y)], col, lw=ToMM(t.GetWidth()) * 72 * 16 / (x1 - x0) / 1.0, alpha=0.7, solid_capstyle="round")
for (n, xy) in []: pass
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal"); plt.savefig(sys.argv[2], dpi=110, bbox_inches="tight")
