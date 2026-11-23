import sys, pcbnew, re, collections
b = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
out = sys.argv[2]
ok = pcbnew.WriteDRCReport(b, out, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(out).read()
types = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
print("rapport:", ok, dict(types))
for m in re.finditer(r"^\*\* Found (\d+) (.*)$", txt, re.M): print(m.group(0))
