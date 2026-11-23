"""Cœur compact du dé connecté Mandragore — génération du PCB (KiCad 7, API pcbnew).

Disque Ø16 mm, 4 couches, 0,8 mm. Dessus : module BC832 (nRF52832), accéléromètre,
pont de mesure de la pile. Dessous : recharge sans fil (doubleur + zener), chargeur TP4054, LDO 3,0 V,
pastilles batterie / bobine / 4 groupes capacitifs / SWD.
"""
import math, os, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/de-mandragore/hw/core/de_core.kicad_pcb"
LCSC = "/home/claude/de-mandragore/lib/lcsc.pretty"
KIFP = "/usr/share/kicad/footprints"
CX, CY = 100.0, 100.0          # centre de la carte
R_BOARD = 8.0                  # Ø16 mm
ANT_Y = -2.8                   # au-dessus (y < ANT_Y) : zone antenne, pas de cuivre de masse
MOD_YC = -1.6                  # centre du module BC832

board = pcbnew.BOARD()
board.SetCopperLayerCount(4)
ds = board.GetDesignSettings()
ds.SetBoardThickness(FromMM(0.8))
ds.m_TrackMinWidth = FromMM(0.127)
ds.m_MinClearance = FromMM(0.10)
ds.m_ViasMinSize = FromMM(0.45)
ds.m_MinThroughDrill = FromMM(0.25)
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_HoleToHoleMin = FromMM(0.25)
ds.m_HoleClearance = FromMM(0.2)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetClearance(FromMM(0.10)); nc.SetTrackWidth(FromMM(0.15))
nc.SetViaDiameter(FromMM(0.45)); nc.SetViaDrill(FromMM(0.25))


def LS(*layers):
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    return ls


def P(x, y):
    return VECTOR2I(FromMM(CX + x), FromMM(CY + y))


nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]


# ---------------------------------------------------------------- empreintes maison
def fp_bc832():
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("de_core", "Fanstel_BC832"))
    for n in range(1, 17):
        if n <= 8:
            x, y = -4.0, -3.92 + (n - 1) * 1.1
        else:
            x, y = 4.0, 3.78 - (n - 9) * 1.1
        p = pcbnew.PAD(fp); p.SetNumber(str(n)); p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
        p.SetRoundRectRadiusRatio(0.2)
        p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetSize(VECTOR2I(FromMM(1.0), FromMM(0.7)))
        p.SetLayerSet(LS(pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask))
        p.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); p.SetPos0(VECTOR2I(FromMM(x), FromMM(y)))
        fp.Add(p)
    def rect(layer, x0, y0, x1, y1, w=0.1):
        for (a, b, c, d) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            s = pcbnew.FP_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT); s.SetLayer(layer)
            s.SetStart0(VECTOR2I(FromMM(a), FromMM(b))); s.SetEnd0(VECTOR2I(FromMM(c), FromMM(d)))
            s.SetWidth(FromMM(w)); fp.Add(s)
    rect(pcbnew.F_Fab, -3.9, -4.4, 3.9, 4.4)
    rect(pcbnew.F_Fab, -3.9, -4.4, 3.9, -1.2, 0.05)   # zone antenne 3,2 mm
    rect(pcbnew.F_CrtYd, -4.65, -4.65, 4.65, 4.65, 0.05)
    return fp


def fp_pad(name, w, h, shape="rect"):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("de_core", name))
    p = pcbnew.PAD(fp); p.SetNumber("1")
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE if shape == "circle" else pcbnew.PAD_SHAPE_ROUNDRECT)
    if shape != "circle": p.SetRoundRectRadiusRatio(0.15)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetSize(VECTOR2I(FromMM(w), FromMM(h)))
    p.SetLayerSet(LS(pcbnew.F_Cu, pcbnew.F_Mask))   # pas de pâte : soudure à la main
    fp.Add(p)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_SMD)
    return fp


def load(lib, name):
    fp = pcbnew.FootprintLoad(lib, name)
    assert fp is not None, (lib, name)
    return fp


R0402 = (KIFP + "/Resistor_SMD.pretty", "R_0402_1005Metric")
C0402 = (KIFP + "/Capacitor_SMD.pretty", "C_0402_1005Metric")

# ref: (empreinte, valeur, LCSC, face, x, y, rot, {pad: net}, options)
PARTS = {
    # ---------------- dessus
    "U1": ("BC832", "BC832 (nRF52832)", "C6470192", "F", 0.0, MOD_YC, 0,
           {"1": "GND", "2": "RX_SHORT", "3": "SWDIO", "4": "SWCLK", "5": "CAP_G4", "6": "CAP_G3",
            "7": "CAP_G1", "8": "CAP_G2", "9": "ACC_INT", "10": None, "11": None, "12": "CHRG",
            "13": "VBAT_SENSE", "14": "SCL", "15": "SDA", "16": "VDD"}),
    "U2": ((LCSC, "LGA-12_L2.0-W2.0-P0.50-BL"), "LIS2DH12TR", "C110926", "F", 1.6, 4.6, 0,
           {"1": "SCL", "2": "VDD", "3": "GND", "4": "SDA", "5": "GND", "6": "GND", "7": "GND", "8": "GND",
            "9": "VDD", "10": "VDD", "11": None, "12": "ACC_INT"}),
    "C1": (C0402, "100nF", "C1525", "F", 5.4, -3.8, 270, {"1": "VDD", "2": "GND"}),
    "C2": (C0402, "100nF", "C1525", "F", 3.4, 4.6, 90, {"1": "VDD", "2": "GND"}),
    "R2": (R0402, "1M", "C26083", "F", -3.2, 4.5, 90, {"1": "VBAT", "2": "VBAT_SENSE"}),
    "R3": (R0402, "1M", "C26083", "F", -1.9, 4.5, 90, {"1": "VBAT_SENSE", "2": "GND"}),
    "C9": (C0402, "100nF", "C1525", "F", -0.6, 4.5, 90, {"1": "VBAT_SENSE", "2": "GND"}),
    # ---------------- dessous
    "U3": ((LCSC, "SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL"), "TP4054", "C32574", "B", -2.6, -0.9, 180,
           {"1": "CHRG", "2": "GND", "3": "VBAT", "4": "VRECT", "5": "PROG"}),
    "U4": ((LCSC, "SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR"), "XC6206P302MR", "C9972", "B", 1.8, -0.9, 0,
           {"1": "GND", "2": "VDD", "3": "VBAT"}),
    "D2": ((LCSC, "SOT-23-3_L3.0-W1.7-P0.95-LS2.9-BR"), "BAT54S", "C47546", "B", 2.6, 3.6, 0,
           {"1": "GND", "2": "VRECT", "3": "RX_X"}),
    "Z1": ((LCSC, "SOD-323_L1.8-W1.3-LS2.5-RD"), "BZT52C5V6S", "C22612", "B", -1.3, 4.4, 0,
           {"1": "VRECT", "2": "GND"}),
    "C6": (C0402, "4.7uF", "C23733", "B", -1.4, 6.2, 0, {"1": "VRECT", "2": "GND"}),
    "Q1": ((LCSC, "SOT-523-3_L1.6-W0.8-P0.50-LS1.6-BR"), "2N7002T", "C2844731", "B", 2.8, 6.0, 0,
           {"1": "RX_SHORT", "2": "GND", "3": "RX_X"}),
    "R4": (R0402, "100k", "C25741", "F", 2.6, 6.4, 180, {"1": "RX_SHORT", "2": "GND"}),
    "C5": (C0402, "1nF C0G", "C53547", "B", 0.2, 6.1, 90, {"1": "COIL1", "2": "RX_X"}),
    "R1": (R0402, "33k", "C25779", "B", -5.2, -1.1, 90, {"1": "PROG", "2": "GND"}),
    "C7": (C0402, "4.7uF", "C23733", "B", -0.4, 1.3, 90, {"1": "VBAT", "2": "GND"}),
    "C8": (C0402, "4.7uF", "C23733", "B", 4.1, -0.9, 270, {"1": "VDD", "2": "GND"}),
}
# pastilles à souder à la main (dessous) ; G1..G4 reliées directement aux GPIO
PADS = {
    "TP_BATP": ("BAT+", 1.4, 1.2, "rect", -5.9, 1.3, "VBAT"),
    "TP_BATN": ("BAT-", 1.4, 1.2, "rect", 5.7, 1.6, "GND"),
    "TP_L1": ("COIL1", 0.9, 0.9, "rect", 1.2, 7.0, "COIL1"),
    "TP_G1": ("G1", 0.9, 0.9, "circle", -6.8, -1.0, "CAP_G1"),
    "TP_G2": ("G2", 0.9, 0.9, "circle", -6.2, 3.4, "CAP_G2"),
    "TP_G3": ("G3", 0.9, 0.9, "circle", 6.8, -1.0, "CAP_G3"),
    "TP_G4": ("G4", 0.9, 0.9, "circle", 6.2, 3.4, "CAP_G4"),
    "TP_SWDIO": ("SWDIO", 0.8, 0.8, "circle", -3.3, 3.0, "SWDIO"),
    "TP_SWCLK": ("SWCLK", 0.8, 0.8, "circle", -2.05, 3.0, "SWCLK"),
    "TP_VDD": ("VDD", 0.8, 0.8, "circle", -0.8, 3.0, "VDD"),
    "TP_GND": ("GND", 0.8, 0.8, "circle", 0.45, 3.0, "GND"),
}

LABEL_OFF = {"TP_SWDIO": (0, -0.75), "TP_SWCLK": (0, 0.75), "TP_VDD": (0, -0.75), "TP_GND": (0, 0.75),
             "TP_BATP": (0, -1.0), "TP_BATN": (0, -1.0), "TP_G1": (0, 0.9), "TP_G3": (0, 0.9), "TP_L1": (-1.0, 0.0), "TP_L2": (0.9, -0.6), "TP_G2": (0, -0.85), "TP_G4": (0, -0.85)}
placed = {}
for ref, (fpspec, val, lcsc, side, x, y, rot, padnets) in PARTS.items():
    fp = fp_bc832() if fpspec == "BC832" else load(*fpspec)
    fp.SetReference(ref); fp.SetValue(val)
    fp.SetField("LCSC", lcsc) if hasattr(fp, "SetField") else None
    if "NC" in val:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(fp)
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(rot)
    if side == "B":
        fp.Flip(P(x, y), False)
    for pad in fp.Pads():
        n = padnets.get(pad.GetNumber(), "__missing__")
        if n == "__missing__":
            raise SystemExit(f"{ref} pad {pad.GetNumber()} sans net")
        if n: pad.SetNet(net(n))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    for it in fp.GraphicalItems():
        if isinstance(it, pcbnew.FP_TEXT) and it.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab, pcbnew.F_SilkS, pcbnew.B_SilkS): it.SetVisible(False)
    placed[ref] = fp

for ref, (label, w, h, shape, x, y, n) in PADS.items():
    fp = fp_pad("pad_" + label, w, h, shape)
    fp.SetReference(ref); fp.SetValue(label)
    board.Add(fp); fp.SetPosition(P(x, y)); fp.Flip(P(x, y), False)
    for pad in fp.Pads(): pad.SetNet(net(n))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    # étiquette sérigraphie
    t = pcbnew.PCB_TEXT(board); t.SetText(label.replace("COIL", "L")); t.SetLayer(pcbnew.B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(0.4), FromMM(0.4))); t.SetTextThickness(FromMM(0.07)); t.SetMirrored(True)
    off = LABEL_OFF.get(ref, (0, -0.9))
    t.SetPosition(P(x + off[0], y + off[1])); board.Add(t)
    placed[ref] = fp

# ---------------------------------------------------------------- contour
circ = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
circ.SetLayer(pcbnew.Edge_Cuts); circ.SetCenter(P(0, 0)); circ.SetEnd(P(R_BOARD, 0)); circ.SetWidth(FromMM(0.1))
board.Add(circ)


def poly_circle_cut(r, ymin, n=72):
    """polygone = disque de rayon r limité à y >= ymin"""
    pts = []
    a0 = math.asin(max(-1, min(1, ymin / r)))  # angle où y = ymin
    # parcours de a0 à pi - a0 (y >= ymin en coordonnées y vers le bas)
    for k in range(n + 1):
        a = a0 + (math.pi - 2 * a0) * k / n
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def add_zone(layer, netname, pts, prio=0, rule=None):
    z = pcbnew.ZONE(board)
    if layer is not None: z.SetLayer(layer)
    if rule:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(rule.get("pour", True)); z.SetDoNotAllowTracks(rule.get("tracks", True))
        z.SetDoNotAllowVias(rule.get("vias", True)); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for l in rule["layers"]: ls.AddLayer(l)
        z.SetLayerSet(ls)
    else:
        z.SetNet(net(netname)); z.SetAssignedPriority(prio)
        z.SetLocalClearance(FromMM(0.15)); z.SetMinThickness(FromMM(0.15))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetThermalReliefGap(FromMM(0.15)); z.SetThermalReliefSpokeWidth(FromMM(0.2))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in pts: ol.Append(FromMM(CX + x), FromMM(CY + y))
    board.Add(z)
    return z


gnd_pts = poly_circle_cut(R_BOARD - 0.25, ANT_Y)
for lay in (pcbnew.In1_Cu, pcbnew.B_Cu):
    add_zone(lay, "GND", gnd_pts)
# dessus : masse seulement sous la bande basse (hors module)
add_zone(pcbnew.F_Cu, "GND", poly_circle_cut(R_BOARD - 0.25, 3.4 + MOD_YC + 0.4))
ALL = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
# zone antenne : ni piste ni via sous l'antenne (toutes couches) ; au-delà du module non plus
ytop_mod = MOD_YC - 4.4
add_zone(None, None, [(-3.45, ytop_mod - 2.5), (3.45, ytop_mod - 2.5), (3.45, MOD_YC - 1.2), (-3.45, MOD_YC - 1.2)],
         rule={"layers": ALL})
add_zone(None, None, [(-8, -8), (8, -8), (8, ytop_mod), (-8, ytop_mod)], rule={"layers": ALL})
# sous le module (pastilles LGA exposées) : pas de piste/via en F.Cu
add_zone(None, None, [(-3.45, MOD_YC - 4.4), (3.45, MOD_YC - 4.4), (3.45, MOD_YC + 4.4), (-3.45, MOD_YC + 4.4)],
         rule={"layers": [pcbnew.F_Cu], "vias": False})
# grille LGA exposée sous le module : aucune via
LGA = (-1.7 - 0.65, MOD_YC - 0.92 - 0.65, 1.9 + 0.65, MOD_YC + 3.88 + 0.65)
add_zone(None, None, [(LGA[0], LGA[1]), (LGA[2], LGA[1]), (LGA[2], LGA[3]), (LGA[0], LGA[3])],
         rule={"layers": ALL, "tracks": False, "pour": False})

# textes
for txt, x, y, layer, sz in (("D-core v0.3", 0.2, -2.55, pcbnew.B_SilkS, 0.35),):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(sz), FromMM(sz))); t.SetTextThickness(FromMM(0.07)); t.SetMirrored(layer == pcbnew.B_SilkS)
    t.SetPosition(P(x, y)); board.Add(t)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
board.Save(OUT)
print("ok", OUT, len(placed), "empreintes", len(nets), "nets")
