#!/bin/sh
# package JLCPCB de la carte émettrice du chargeur : make_package_charger.sh version
set -e
V=$1; R=/home/claude/de-mandragore; PCB=$R/hw/charger/chargeur_routed.kicad_pcb; OUT=$R/jlcpcb_chargeur
rm -rf $OUT/gerbers $OUT/*.csv $OUT/gerbers_*.zip $OUT/kicad; mkdir -p $OUT/gerbers $OUT/kicad/scripts $OUT/kicad/lib
kicad-cli pcb export gerbers -o $OUT/gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask --no-x2 --no-netlist $PCB >/dev/null
kicad-cli pcb export drill -o $OUT/gerbers/ --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 $PCB >/dev/null
kicad-cli pcb export pos -o /tmp/pos_ch.csv --format csv --units mm --side both $PCB >/dev/null
python3 - <<PY
import csv, collections, pcbnew
b = pcbnew.LoadBoard('$PCB')
info = {}
for fp in b.GetFootprints():
    if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES: continue
    pr = fp.GetProperties(); l = pr.get("LCSC") or pr.get("LCSC Part")
    info[fp.GetReference()] = (fp.GetValue(), l, fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), "wx_str") else str(fp.GetFPID().GetLibItemName()))
rows = list(csv.DictReader(open('/tmp/pos_ch.csv')))
with open('$OUT/CPL_chargeur.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in rows:
        if r['Ref'] not in info: continue
        w.writerow([r['Ref'], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm", "Top" if r['Side'] == 'top' else "Bottom", f"{float(r['Rot']) % 360:.0f}"])
grp = collections.OrderedDict()
for ref, (val, l, fpn) in sorted(info.items()):
    grp.setdefault((val, fpn, l), []).append(ref)
with open('$OUT/BOM_chargeur.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (v, p, l), refs in grp.items(): w.writerow([v, ",".join(refs), p, l])
miss = [r for r, (v, l, p) in info.items() if not l]
print("composants :", len(info), "lignes BOM :", len(grp), "sans référence LCSC :", miss)
PY
(cd $OUT/gerbers && zip -q ../gerbers_chargeur_$V.zip *)
cp $PCB $OUT/kicad/chargeur.kicad_pcb; cp ${PCB%.kicad_pcb}.kicad_pro $OUT/kicad/chargeur.kicad_pro 2>/dev/null || true
cp $R/hw/charger/chargeur_geometrie.json $OUT/kicad/
cp $R/scripts/build_charger.py $R/scripts/route_charger.py $R/scripts/stitch_charger.py $R/scripts/check_place_ch.py $R/scripts/sim_tx_carte.py $OUT/kicad/scripts/
cp -r $R/lib/lcsc.pretty $R/lib/lcsc.kicad_sym $OUT/kicad/lib/
