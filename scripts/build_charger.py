"""Carte émettrice de la boîte-chargeur MCDice (7 emplacements) — génération du PCB (KiCad 7, API pcbnew).

2 couches, 0,8 mm, 152 × 82 mm, logée sous le plancher de la boîte (face dessus plaquée contre le plancher).
Dessus : uniquement les spirales émettrices + plan de masse (rien qui dépasse).
Dessous : tous les composants.

Électronique : USB-C 5 V -> demi-pont commun 1 MHz (AO3401A / AO3400A pilotés par UCC27524, signaux
complémentaires avec temps mort du TIM1 d'un CH32V203) -> bus SW -> 7 branches série
[10 nF + 2,2 nF C0G] -> spirale Ø10 (≈2,0 µH) -> AO3400A (mise en service de l'emplacement) -> 2 × 2,2 Ω -> masse.
Mesure du courant : détecteur de crête (B5819W + 100 nF + 100 kΩ) sur la résistance -> ADC.

Coordonnées « boîte » (mm, origine coin bas-gauche de la boîte, y vers le haut, vue de dessus) ;
KiCad : X = X0 + x, Y = Y0 + (87 - y).
"""
import math, os, sys, json
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/de-mandragore/hw/charger/chargeur.kicad_pcb"
LCSC = "/home/claude/de-mandragore/lib/lcsc.pretty"
KIFP = "/usr/share/kicad/footprints"
X0, Y0, DBOX = 50.0, 50.0, 87.0
BOX = json.load(open("/home/claude/de-mandragore/charger/boite_chargeur.json"))
BX0, BY0, BX1, BY1 = 2.5, 2.5, 154.5, 84.5            # contour de la carte (coordonnées boîte)
BOSSES = [(5.0, 5.0), (152.0, 5.0), (5.0, 82.0), (152.0, 82.0)]
NOTCH_R = 4.1

board = pcbnew.BOARD()
board.SetCopperLayerCount(2)
ds = board.GetDesignSettings()
ds.SetBoardThickness(FromMM(0.8))
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_MinClearance = FromMM(0.127)
ds.m_ViasMinSize = FromMM(0.5)
ds.m_ViasMinAnnularWidth = FromMM(0.13)
ds.m_SolderMaskExpansion = FromMM(0.04)
ds.m_SolderMaskMinWidth = FromMM(0.0)
ds.m_MinTextHeight = FromMM(0.8) if hasattr(ds, "m_MinTextHeight") else None
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_CopperEdgeClearance = FromMM(0.3)
ds.m_HoleToHoleMin = FromMM(0.25)
ds.m_HoleClearance = FromMM(0.15)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetClearance(FromMM(0.127)); nc.SetTrackWidth(FromMM(0.25))
nc.SetViaDiameter(FromMM(0.6)); nc.SetViaDrill(FromMM(0.3))


def P(x, y):
    return VECTOR2I(FromMM(X0 + x), FromMM(Y0 + DBOX - y))


def LS(*layers):
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    return ls


nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]


def load(lib, name):
    fp = pcbnew.FootprintLoad(lib, name)
    if fp is None: raise SystemExit(f"empreinte introuvable {lib} {name}")
    return fp


R0603 = (KIFP + "/Resistor_SMD.pretty", "R_0603_1608Metric")
R1206 = (KIFP + "/Resistor_SMD.pretty", "R_1206_3216Metric")
C0603 = (KIFP + "/Capacitor_SMD.pretty", "C_0603_1608Metric")
C0805 = (KIFP + "/Capacitor_SMD.pretty", "C_0805_2012Metric")
SOT23 = (LCSC, "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR")
SOT23_P = (LCSC, "SOT-23_L2.9-W1.3-P1.90-LS2.4-BR")

# ------------------------------------------------------------------ nomenclature
# ref: (empreinte, valeur, LCSC, x, y, rot, {pad: net})   (tout est en face dessous)
PARTS = {}

def part(ref, fpspec, val, lcsc, x, y, rot, pads):
    PARTS[ref] = (fpspec, val, lcsc, x, y, rot, pads)

# --- alimentation USB-C (puits 5 V : CC1/CC2 tirés à la masse par 5,1 kΩ)
part("J1", (LCSC, "USB-C-SMD_TYPE-C-16PIN-2MD-073"), "USB-C 16P", "C2765186", 7.4, 43.5, 270,
     {"A1B12": "GND", "B1A12": "GND", "A4B9": "VBUS", "B4A9": "VBUS", "A5": "CC1", "B5": "CC2",
      "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "A8": None, "B8": None, "13": "GND", "14": "GND"})
part("R1", R0603, "5.1k", "C23186", 13.0, 39.6, 90, {"1": "CC1", "2": "GND"})
part("R2", R0603, "5.1k", "C23186", 13.0, 47.4, 90, {"1": "CC2", "2": "GND"})
part("C1", C0805, "22uF", "C45783", 16.0, 44.8, 90, {"1": "VBUS", "2": "GND"})
part("C2", C0805, "22uF", "C45783", 18.4, 44.8, 90, {"1": "VBUS", "2": "GND"})
part("U1", (LCSC, "SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR"), "XC6206P332MR", "C5446", 18.0, 38.2, 0,
     {"1": "GND", "2": "3V3", "3": "VBUS"})
part("C3", C0603, "1uF", "C15849", 15.2, 36.0, 0, {"1": "VBUS", "2": "GND"})
part("C4", C0603, "1uF", "C15849", 20.8, 36.0, 0, {"1": "3V3", "2": "GND"})
# --- demi-pont commun
part("U2", (LCSC, "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL"), "UCC27524ADR", "C185857", 27.0, 42.0, 0,
     {"1": None, "2": "PWM_H", "3": "GND", "4": "PWM_L", "5": "GATE_L", "6": "VBUS", "7": "GATE_H", "8": None})
part("C5", C0603, "1uF", "C15849", 27.0, 37.6, 0, {"1": "VBUS", "2": "GND"})
part("R3", R0603, "10k", "C25804", 22.6, 41.0, 90, {"1": "PWM_H", "2": "3V3"})      # P bloqué au repos
part("R4", R0603, "10k", "C25804", 22.6, 44.6, 90, {"1": "PWM_L", "2": "GND"})      # N bloqué au repos
part("Q1", SOT23_P, "AO3401A", "C15127", 34.0, 44.8, 0, {"1": "GATE_H", "2": "VBUS", "3": "SW"})
part("Q2", SOT23, "AO3400A", "C20917", 34.0, 39.6, 0, {"1": "GATE_L", "2": "GND", "3": "SW"})
part("C6", C0805, "22uF", "C45783", 38.4, 42.4, 90, {"1": "VBUS", "2": "GND"})
part("C7", C0603, "100nF", "C14663", 30.8, 47.4, 0, {"1": "VBUS", "2": "GND"})
# --- microcontrôleur CH32V203C8T6 (3,3 V, USB pour la mise à jour, SWD sur pastilles)
MCU = (64.0, 39.6)
mcu_pads = {str(n): None for n in range(1, 49)}
mcu_pads.update({"1": "3V3", "9": "3V3", "24": "3V3", "36": "3V3", "48": "3V3",
                 "8": "GND", "23": "GND", "35": "GND", "47": "GND", "20": "GND",      # PB2/BOOT1 à la masse
                 "5": "XIN", "6": "XOUT", "7": "NRST", "44": "BOOT0",
                 "32": "USB_DM", "33": "USB_DP", "34": "SWDIO", "37": "SWCLK",
                 "29": "PWM_H", "26": "PWM_L", "22": "LED",                          # TIM1_CH1 (PA8) / TIM1_CH1N (PB13)
                 # emplacements : mesure de crête (ADC) et mise en service, choisies du côté de chaque bobine
                 "10": "PK1", "11": "PK2", "12": "PK3", "13": "PK4", "19": "PK5", "18": "PK6", "16": "PK7",
                 "2": "EN1", "3": "EN2", "15": "EN3", "14": "EN4", "40": "EN5", "21": "EN6", "17": "EN7"})
part("U3", (LCSC, "LQFP-48_L7.0-W7.0-P0.50-LS9.0-BL"), "CH32V203C8T6", "C3001172", MCU[0], MCU[1], 0, mcu_pads)
part("Y1", (LCSC, "CRYSTAL-SMD_4P-L3.2-W2.5-BL"), "8MHz", "C2682774", 55.6, 44.2, 0,
     {"1": "XIN", "2": "GND", "3": "XOUT", "4": "GND"})
part("C8", C0603, "20pF", "C1648", 53.0, 46.4, 0, {"1": "XIN", "2": "GND"})
part("C9", C0603, "20pF", "C1648", 58.2, 46.4, 0, {"1": "XOUT", "2": "GND"})
part("C10", C0603, "100nF", "C14663", 60.6, 33.4, 0, {"1": "3V3", "2": "GND"})
part("C11", C0603, "100nF", "C14663", 67.4, 33.4, 0, {"1": "3V3", "2": "GND"})
part("C12", C0603, "100nF", "C14663", 69.8, 44.4, 90, {"1": "3V3", "2": "GND"})
part("C14", C0603, "100nF", "C14663", 56.2, 40.0, 90, {"1": "NRST", "2": "GND"})
part("R5", R0603, "10k", "C25804", 45.0, 41.2, 90, {"1": "BOOT0", "2": "GND"})
part("SW1", (LCSC, "SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5"), "BOOT", "C318884", 49.8, 41.2, 0,
     {"1": "BOOT0", "2": "BOOT0", "3": "3V3", "4": "3V3"})
part("D1", (LCSC, "LED0603-RD"), "LED verte", "C72043", 98.0, 44.4, 0, {"1": "GND", "2": "LED_A"})
part("R6", R0603, "1k", "C21190", 98.0, 41.6, 0, {"1": "LED", "2": "LED_A"})

# --- 7 emplacements
SLOTS = BOX["logements"]
COIL = {}
for k, s in enumerate(SLOTS, start=1):
    cx, cy = s["centre_bobine_mm"]
    d = -1.0 if cy > 43.5 else 1.0          # côté de la bande centrale
    y0, y1 = cy + d * 8.0, cy + d * 10.8
    part(f"C{20+k}", C0805, "10nF C0G", "C27071", cx - 6.0, y0, 0, {"1": "SW", "2": f"COIL{k}"})
    part(f"C{30+k}", C0603, "2.2nF C0G", "C33353", cx - 6.0, y1, 0, {"1": "SW", "2": f"COIL{k}"})
    part(f"Q{10+k}", SOT23, "AO3400A", "C20917", cx + 2.6, y0, 0 if d > 0 else 180,
         {"1": f"EN{k}", "2": f"S{k}", "3": f"COIL{k}"})
    part(f"R{10+k}", R0603, "100k", "C25803", cx + 2.6, y1 + d * 0.3, 0, {"1": f"EN{k}", "2": "GND"})
    part(f"R{20+k}", R1206, "2.2R", "C17947", cx + 6.6, y0, 0, {"1": f"S{k}", "2": "GND"})
    part(f"R{30+k}", R1206, "2.2R", "C17947", cx + 6.6, y1 + d * 0.3, 0, {"1": f"S{k}", "2": "GND"})
    part(f"D{10+k}", (LCSC, "SOD-123_L2.7-W1.6-LS3.7-RD-1"), "B5819W", "C8598", cx + 11.6, y0, 0,
         {"1": f"PK{k}", "2": f"S{k}"})
    part(f"C{40+k}", C0603, "100nF", "C14663", cx + 11.0, y1 + d * 0.3, 0, {"1": f"PK{k}", "2": "GND"})
    part(f"R{40+k}", R0603, "100k", "C25803", cx + 14.2, y1 + d * 0.3, 90, {"1": f"PK{k}", "2": "GND"})
    COIL[k] = (cx, cy, d, s["de"])

# pastilles de test / programmation (dessous)
TPS = {"TP1": ("SWDIO", 84.0, 44.0), "TP2": ("SWCLK", 86.6, 44.0), "TP3": ("3V3", 89.2, 44.0), "TP4": ("GND", 91.8, 44.0),
       "TP5": ("SW", 44.5, 49.6), "TP6": ("VBUS", 11.0, 50.8), "TP7": ("NRST", 94.4, 44.0)}

placed = {}
for ref, (fpspec, val, lcsc, x, y, rot, padnets) in PARTS.items():
    fp = load(*fpspec)
    fp.SetReference(ref); fp.SetValue(val)
    fp.SetProperty("LCSC", lcsc)
    board.Add(fp)
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    fp.Flip(P(x, y), False)
    for pad in fp.Pads():
        if not pad.GetNumber() and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:   # plots de centrage : trous non métallisés
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetLayerSet(LS(pcbnew.F_Mask, pcbnew.B_Mask))
            pad.SetSize(pad.GetDrillSize())
        n = padnets.get(pad.GetNumber(), "__missing__") if pad.GetNumber() else None
        if n == "__missing__": raise SystemExit(f"{ref} pastille {pad.GetNumber()} sans net")
        if n: pad.SetNet(net(n))
        else: pad.SetNetCode(0)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    for it in fp.GraphicalItems():
        if isinstance(it, pcbnew.FP_TEXT): it.SetVisible(False)
    placed[ref] = fp

for ref, (label, x, y) in TPS.items():
    fp = pcbnew.FOOTPRINT(board); fp.SetFPID(pcbnew.LIB_ID("chargeur", "TP_" + label))
    p = pcbnew.PAD(fp); p.SetNumber("1"); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetSize(VECTOR2I(FromMM(1.2), FromMM(1.2))); p.SetLayerSet(LS(pcbnew.F_Cu, pcbnew.F_Mask)); fp.Add(p)
    fp.SetReference(ref); fp.SetValue(label)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_SMD)
    board.Add(fp); fp.SetPosition(P(x, y)); fp.Flip(P(x, y), False)
    for pad in fp.Pads(): pad.SetNet(net(label))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    t = pcbnew.PCB_TEXT(board); t.SetText(label); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
    t.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); t.SetTextThickness(FromMM(0.15)); t.SetTextAngleDegrees(90)
    t.SetPosition(P(x, y - 2.6)); board.Add(t)
    placed[ref] = fp

# ------------------------------------------------------------------ spirales émettrices
PITCH, W_COIL, R_OUT = 0.35, 0.2, 4.825
T_TOP, T_BOT = 9.75, 10.125
R_IN = R_OUT - T_TOP * PITCH                # 1,4125
R_VIA_C = 0.8
VIA_COIL = (0.6, 0.3)
coil_info = {}


def seg(layer, a, b, w, netname):
    t = pcbnew.PCB_TRACK(board); t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(FromMM(w))
    t.SetLayer(layer); t.SetNet(net(netname)); board.Add(t)


def via(pt, netname, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board); v.SetPosition(P(*pt)); v.SetWidth(FromMM(d)); v.SetDrill(FromMM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(netname)); board.Add(v)


def pol(cx, cy, r, a):
    return (cx + r * math.cos(a), cy + r * math.sin(a))


for k, (cx, cy, d, lab) in COIL.items():
    nn = f"COIL{k}"
    # sortie haute vers la bande centrale, décalée vers la gauche (côté des condensateurs)
    th_a = math.radians(-90 if d < 0 else 90) + (math.radians(-25) if d < 0 else math.radians(25))
    STEP = math.radians(5)
    # dessus : de R_OUT vers l'intérieur, sens horaire (angle décroissant), T_TOP tours
    n = int(round(T_TOP * 2 * math.pi / STEP))
    pts = [pol(cx, cy, R_OUT - PITCH * (i * STEP) / (2 * math.pi), th_a - i * STEP) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]): seg(pcbnew.F_Cu, a, b, W_COIL, nn)
    th_end = th_a - n * STEP
    pc = pol(cx, cy, R_VIA_C, th_end)
    seg(pcbnew.F_Cu, pts[-1], pc, W_COIL, nn); via(pc, nn, *VIA_COIL)
    # dessous : de R_IN vers l'extérieur, même sens de rotation, T_BOT tours
    m = int(round(T_BOT * 2 * math.pi / STEP))
    qts = [pol(cx, cy, R_IN + PITCH * (i * STEP) / (2 * math.pi), th_end - i * STEP) for i in range(m + 1)]
    seg(pcbnew.B_Cu, pc, qts[0], W_COIL, nn)
    for a, b in zip(qts, qts[1:]): seg(pcbnew.B_Cu, a, b, W_COIL, nn)
    th_b = th_end - m * STEP
    # amorces de sortie : via haute (dessus -> dessous), sortie basse radiale
    va = pol(cx, cy, 5.7, th_a)
    seg(pcbnew.F_Cu, pts[0], va, 0.3, nn); via(va, nn)
    vb = pol(cx, cy, 6.0, th_b)
    seg(pcbnew.B_Cu, qts[-1], vb, 0.3, nn)
    coil_info[k] = {"centre": (cx, cy), "sortie_a": va, "sortie_b": vb, "de": lab,
                    "angle_a_deg": math.degrees(th_a) % 360, "angle_b_deg": math.degrees(th_b) % 360}
    # étiquette
    t = pcbnew.PCB_TEXT(board); t.SetText(f"{k}: {lab}"); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
    t.SetTextSize(VECTOR2I(FromMM(1.2), FromMM(1.2))); t.SetTextThickness(FromMM(0.2))
    t.SetPosition(P(cx - 9.5, cy - d * 3.0)); board.Add(t)

# ------------------------------------------------------------------ contour (rectangle à encoches)
def edge(a, b):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetWidth(FromMM(0.1)); board.Add(s)


def arc(c, a, b, mid):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetArcGeometry(P(*a), P(*mid), P(*b)); s.SetWidth(FromMM(0.1)); board.Add(s)


def notch_pts(bx, by, sx, sy):
    """points où le cercle d'encoche coupe les bords x = bord et y = bord ; sx, sy = sens vers l'intérieur"""
    ex = BX0 if sx > 0 else BX1; ey = BY0 if sy > 0 else BY1
    dy = math.sqrt(NOTCH_R ** 2 - (ex - bx) ** 2); dx = math.sqrt(NOTCH_R ** 2 - (ey - by) ** 2)
    p_on_x = (ex, by + sy * dy)       # sur le bord vertical
    p_on_y = (bx + sx * dx, ey)       # sur le bord horizontal
    ang = math.atan2(sy, sx); mid = (bx + NOTCH_R * math.cos(ang), by + NOTCH_R * math.sin(ang))
    return p_on_x, p_on_y, mid

c_bl = notch_pts(5.0, 5.0, 1, 1); c_br = notch_pts(152.0, 5.0, -1, 1)
c_tl = notch_pts(5.0, 82.0, 1, -1); c_tr = notch_pts(152.0, 82.0, -1, -1)
edge(c_bl[1], c_br[1]); edge(c_br[0], c_tr[0]); edge(c_tr[1], c_tl[1]); edge(c_tl[0], c_bl[0])
for c in (c_bl, c_br, c_tl, c_tr): arc(None, c[0], c[1], c[2])
OUTLINE = []
for (pa, pb) in ((c_bl[1], c_br[1]), (c_br[0], c_tr[0]), (c_tr[1], c_tl[1]), (c_tl[0], c_bl[0])):
    OUTLINE += [pa, pb]

# ------------------------------------------------------------------ zones
def add_zone(layers, netname, pts, rule=None, prio=0):
    z = pcbnew.ZONE(board)
    if rule is not None:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(rule.get("tracks", False))
        z.SetDoNotAllowVias(rule.get("vias", False)); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net(netname)); z.SetAssignedPriority(prio)
        z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetLayerSet(LS(*layers))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in pts: ol.Append(FromMM(X0 + x), FromMM(Y0 + DBOX - y))
    board.Add(z); return z

inset = 0.4
add_zone([pcbnew.F_Cu, pcbnew.B_Cu], "GND",
         [(BX0 + inset, BY0 + inset + NOTCH_R), (BX0 + inset + NOTCH_R, BY0 + inset), (BX1 - inset - NOTCH_R, BY0 + inset),
          (BX1 - inset, BY0 + inset + NOTCH_R), (BX1 - inset, BY1 - inset - NOTCH_R), (BX1 - inset - NOTCH_R, BY1 - inset),
          (BX0 + inset + NOTCH_R, BY1 - inset), (BX0 + inset, BY1 - inset - NOTCH_R)])
for k, (cx, cy, d, lab) in COIL.items():   # pas de plan de masse près des spirales (courants de Foucault)
    add_zone([pcbnew.F_Cu, pcbnew.B_Cu], None, [pol(cx, cy, 7.0, math.radians(a)) for a in range(0, 360, 10)], rule={})

# ------------------------------------------------------------------ textes
for txt, x, y, sz in (("MCDice - chargeur 7 des v0.1", 120.0, 42.0, 1.5), ("Mandragore - CC BY-NC 4.0", 120.0, 39.4, 1.0),
                      ("BOOT", 48.6, 44.6, 0.8)):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
    t.SetTextSize(VECTOR2I(FromMM(sz), FromMM(sz))); t.SetTextThickness(FromMM(sz * 0.15)); t.SetPosition(P(x, y)); board.Add(t)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
board.Save(OUT)
json.dump({"bobines": coil_info, "contour": [BX0, BY0, BX1, BY1], "encoches": BOSSES, "r_encoche": NOTCH_R,
           "transfo": {"X0": X0, "Y0": Y0, "DBOX": DBOX}},
          open(os.path.join(os.path.dirname(OUT), "chargeur_geometrie.json"), "w"), indent=1, default=float)
print("ok", OUT, len(placed), "empreintes", len(nets), "nets")
