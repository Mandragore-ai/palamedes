"""Couplage inductif boîte-chargeur -> dé : inductance mutuelle (Neumann, spires filamentaires),
circuit récepteur (bobine + C3 en parallèle + doubleur de Greinacher + charge du TP4054),
tension continue obtenue selon l'écart, le décentrage, la fréquence et le réglage de C3.

Hypothèses (à confirmer par la mesure) :
- émetteur du kit : bobine plate Ø10 mm, 12 spires, courant crête 0,5 A (sensibilité étudiée)
- fréquence de l'émetteur inconnue : 150 kHz, 500 kHz et 1 MHz étudiées
- charge : TP4054 à 30 mA sous ≥ 4,4 V -> 150 Ω ; diodes Schottky 0,3 V ; zener 5,6 V (limite haute)
"""
import json, math
import numpy as np

MU0 = 4e-7 * math.pi


def spires(r_in, r_out, n_rad, n_couches, pas_z, z0=0.0):
    """liste (rayon, z) des spires d'une galette multicouche"""
    rs = np.linspace(r_in, r_out, n_rad)
    return [(r, z0 + k * pas_z) for k in range(n_couches) for r in rs]


def mutuelle_boucles(a, b, d, x=0.0, n=96):
    """inductance mutuelle entre deux boucles circulaires de rayons a, b, écart axial d, décalage latéral x (Neumann)"""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    p1 = np.stack([a * np.cos(t), a * np.sin(t), np.zeros(n)], 1)
    dl1 = np.stack([-a * np.sin(t), a * np.cos(t), np.zeros(n)], 1) * (2 * np.pi / n)
    p2 = np.stack([x + b * np.cos(t), b * np.sin(t), np.full(n, d)], 1)
    dl2 = np.stack([-b * np.sin(t), b * np.cos(t), np.zeros(n)], 1) * (2 * np.pi / n)
    R = np.linalg.norm(p1[:, None, :] - p2[None, :, :], axis=2)
    return MU0 / (4 * np.pi) * np.sum((dl1 @ dl2.T) / R)


def mutuelle(c1, c2, d, x=0.0):
    return sum(mutuelle_boucles(a, b, d + z2 - z1, x) for (a, z1) in c1 for (b, z2) in c2)


def inductance_propre(c, fil_r):
    """L = somme des self de chaque spire + mutuelles entre spires (rayon de fil fil_r)"""
    L = 0.0
    for i, (a, z1) in enumerate(c):
        L += MU0 * a * (math.log(8 * a / fil_r) - 2)
        for j, (b, z2) in enumerate(c):
            if j > i: L += 2 * mutuelle_boucles(a, b, abs(z2 - z1) + 1e-9 if abs(z2 - z1) > 0 else fil_r * 2.2 if a == b else 0.0, 0.0) if not (a == b and z1 == z2) else 0
    return L


def resistance(c, d_fil, f):
    longueur = sum(2 * math.pi * r for r, _ in c)
    rho = 1.72e-8; s = math.pi * (d_fil / 2) ** 2
    rdc = rho * longueur / s
    delta = math.sqrt(rho / (math.pi * f * MU0))        # effet de peau (sans effet de proximité)
    return rdc * max(1.0, (d_fil / 2) / (2 * delta)) * 1.3   # +30 % : effet de proximité approximé


def recepteur(M, L, Rc, f, C, Itx, RL=150.0, vd=0.3, vz=5.6):
    """tension continue en sortie du doubleur (bornée par la zener) et puissance reçue"""
    w = 2 * math.pi * f
    Vind = w * M * Itx                       # f.é.m. crête induite
    # boucle : source série (Rc + jwL) ; en parallèle : C et la charge AC équivalente du doubleur
    def vout(Vdc):
        Rac = max(RL, 1.0) / 8.0             # doubleur : R_ac ≈ R_L / 8 (pertes diodes traitées à part)
        Zp = 1 / (1j * w * C + 1 / Rac)
        Vp = abs(Vind * Zp / (Rc + 1j * w * L + Zp))
        return 2 * max(Vp - vd, 0.0)
    Vdc = vout(0)
    return min(Vdc, vz), Vdc


# ------------------------------------------------------------------ bobines
fil = 0.1e-3
TX = spires(1.5e-3, 4.8e-3, 12, 1, 0, 0.0)                          # kit : Ø10, 12 spires (hypothèse)
RX20 = spires(1.6e-3, 3.65e-3, 9, 4, 0.12e-3)                       # D20 : Ø7,5 × 0,5 mm, 36 spires de 0,1 mm
RX10 = spires(1.5e-3, 4.8e-3, 12, 2, 0.12e-3)                       # dés D6–D12 : bobine Ø10 du kit (24 spires, hypothèse)

L_rx20 = inductance_propre(RX20, fil / 2); L_rx10 = inductance_propre(RX10, fil / 2)
print(f"L récepteur D20 Ø7,5 : {L_rx20*1e6:.1f} µH ; L récepteur Ø10 : {L_rx10*1e6:.1f} µH")

GAPS = [0.8, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0]   # mm entre les plans des bobines
OFFS = [0.0, 0.5, 1.0, 1.5, 2.0]                            # mm de décentrage
FREQS = [150e3, 500e3, 1e6]
res = {"hypotheses": __doc__, "L_uH": {"D20": L_rx20 * 1e6, "kit10": L_rx10 * 1e6}, "cas": {}}

for nom, RX, L in (("D20_Ø7,5", RX20, L_rx20), ("D6-D12_Ø10", RX10, L_rx10)):
    k_by_gap = {}
    for g in GAPS:
        k_by_gap[g] = mutuelle(TX, RX, g * 1e-3)
    off_15 = {o: mutuelle(TX, RX, 1.5e-3, o * 1e-3) for o in OFFS}
    for f in FREQS:
        Rc = resistance(RX, fil, f); C = 1 / ((2 * math.pi * f) ** 2 * L)
        out = {"C3_nF": C * 1e9, "R_bobine_ohm": Rc, "M_nH": {g: k_by_gap[g] * 1e9 for g in GAPS}}
        out["Vdc_gap"] = {g: recepteur(k_by_gap[g], L, Rc, f, C, 0.5)[1] for g in GAPS}
        out["Vdc_decentrage_1.5mm"] = {o: recepteur(off_15[o], L, Rc, f, C, 0.5)[1] for o in OFFS}
        # tolérance d'accord : C3 à ±10 % / ±20 % (ou fréquence décalée)
        out["Vdc_desaccord_1.5mm"] = {p: recepteur(k_by_gap[1.5], L, Rc, f, C * (1 + p / 100), 0.5)[1] for p in (-30, -20, -10, 0, 10, 20, 30)}
        out["Vdc_sans_C3_1.5mm"] = recepteur(k_by_gap[1.5], L, Rc, f, 1e-15, 0.5)[1]
        out["Vdc_Itx_0.25A_1.5mm"] = recepteur(k_by_gap[1.5], L, Rc, f, C, 0.25)[1]
        res["cas"][f"{nom} @ {int(f/1e3)} kHz"] = out
        print(f"\n{nom} @ {f/1e3:.0f} kHz : C3 = {C*1e9:.1f} nF, R bobine = {Rc:.2f} Ω")
        print("  écart (mm) -> Vdc :", {g: round(v, 1) for g, v in out['Vdc_gap'].items()})
        print("  décentrage à 1,5 mm :", {o: round(v, 1) for o, v in out['Vdc_decentrage_1.5mm'].items()})
        print("  désaccord C3 (%) :", {p: round(v, 1) for p, v in out['Vdc_desaccord_1.5mm'].items()}, "| sans C3 :", round(out['Vdc_sans_C3_1.5mm'], 2), "| Itx 0,25 A :", round(out['Vdc_Itx_0.25A_1.5mm'], 1))
json.dump(res, open("/home/claude/de-mandragore/sim_coil.json", "w"), indent=1, default=float)
