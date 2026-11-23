#!/bin/sh
# génère le package JLCPCB depuis la carte routée : make_package.sh version
set -e
V=$1; R=/home/claude/de-mandragore; PCB=$R/hw/core/de_core_routed.kicad_pcb; OUT=$R/jlcpcb
rm -rf $OUT/gerbers $OUT/*.csv $OUT/gerbers_*.zip $OUT/kicad; mkdir -p $OUT/gerbers $OUT/kicad/scripts $OUT/kicad/lib
kicad-cli pcb export gerbers -o $OUT/gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask --no-x2 --no-netlist $PCB >/dev/null
kicad-cli pcb export drill -o $OUT/gerbers/ --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 $PCB >/dev/null
kicad-cli pcb export pos -o /tmp/pos.csv --format csv --units mm --side both $PCB >/dev/null
python3 - <<PY
import re, csv, collections, pcbnew
src=open('$R/scripts/build_core.py').read()
parts={m.group(1):(m.group(2),m.group(3)) for m in re.finditer(r'"(\w+)": \((?:\(LCSC, "[^"]+"\)|C0402|R0402|"BC832"), "([^"]*)", "(C\d+)", "([FB])"', src)}
rows=list(csv.DictReader(open('/tmp/pos.csv')))
with open('$OUT/CPL_de_core.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(["Designator","Mid X","Mid Y","Layer","Rotation"])
    for r in rows: w.writerow([r['Ref'],f"{float(r['PosX']):.3f}mm",f"{float(r['PosY']):.3f}mm","Top" if r['Side']=='top' else "Bottom",f"{float(r['Rot'])%360:.0f}"])
grp=collections.OrderedDict()
for r in rows:
    val,lcsc=parts[r['Ref']]; key=('BC832' if val.startswith('BC832') else val.split(' (')[0], r['Package'], lcsc); grp.setdefault(key,[]).append(r['Ref'])
with open('$OUT/BOM_de_core.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(["Comment","Designator","Footprint","LCSC Part #"])
    for (v,p,l),refs in grp.items(): w.writerow([v,",".join(sorted(refs)),p,l])
b=pcbnew.LoadBoard('$PCB')
refs={fp.GetReference() for fp in b.GetFootprints() if not (fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES)}
bom=set(); [bom.update(r['Designator'].split(',')) for r in csv.DictReader(open('$OUT/BOM_de_core.csv'))]
print("composants carte/CPL/BOM :", len(refs), len(rows), len(bom), "écarts :", refs ^ bom)
PY
(cd $OUT/gerbers && zip -q ../gerbers_de_core_$V.zip *)
cp $PCB $OUT/kicad/de_core.kicad_pcb; cp ${PCB%.kicad_pcb}.kicad_pro $OUT/kicad/de_core.kicad_pro
cp $R/scripts/*.py $R/scripts/*.sh $OUT/kicad/scripts/; cp -r $R/lib/lcsc.pretty $R/lib/lcsc.kicad_sym $OUT/kicad/lib/
