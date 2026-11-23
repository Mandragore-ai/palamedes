import sys, json, pcbnew
from pcbnew import FromMM, VECTOR2I
pcb = sys.argv[1]
b = pcbnew.LoadBoard(pcb)
for d in b.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() in (pcbnew.B_SilkS, pcbnew.F_SilkS):
        d.SetTextSize(VECTOR2I(FromMM(0.6), FromMM(0.6))); d.SetTextThickness(FromMM(0.1))
b.Save(pcb)
pro = pcb.replace(".kicad_pcb", ".kicad_pro")
j = json.load(open(pro)); r = j["board"]["design_settings"]["rules"]
r["min_text_height"] = 0.5; r["min_text_thickness"] = 0.08
json.dump(j, open(pro, "w"), indent=2)
print("ok")
