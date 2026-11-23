"""Reprend la liaison masse de C1 (pastille 2) de la v0.2 : piste F.Cu contournant la pastille 1 jusqu'à une via."""
import sys, pcbnew
from pcbnew import FromMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1]); gnd = b.FindNet("GND")
pts = [(105.4, 95.72), (105.4, 95.75), (105.5, 95.85), (105.5, 95.9), (105.9, 96.3), (105.9, 96.35),
       (105.95, 96.4), (105.95, 97.0), (106.3, 97.35), (106.3, 97.5), (106.35, 97.55)]
for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
    t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
    t.SetWidth(FromMM(0.25)); t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd); b.Add(t)
v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(106.35), FromMM(97.55))); v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.25))
v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
f = pcbnew.ZONE_FILLER(b); f.Fill(b.Zones())
b.Save(sys.argv[1]); print("ok")
