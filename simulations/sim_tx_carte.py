"""Revalidation SPICE de la recharge avec la bobine émettrice réellement dessinée sur la carte du chargeur.

Spirale d'Archimède 2 couches (PCB 0,8 mm), telle que dessinée par build_charger.py : 9,75 tours en surface de 4,825 à
1,4125 mm de rayon (piste 0,2, pas 0,35), via centrale, 10,125 tours au dos vers l'extérieur.
Accord : 10 nF + 2,2 nF C0G = 12,2 nF.
Chaîne série par emplacement : demi-pont AO3401A/AO3400A (≈0,1 Ω) + interrupteur AO3400A (≈0,04 Ω) + 2 × 2,2 Ω // (1,1 Ω).
"""
import math, json, sys
import numpy as np
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
import sim_wpt as W

top = [(4.825e-3 - 0.35e-3 * (k + 0.5) * (9.75 / 10), 0.0) for k in range(10)]
bot = [(1.4125e-3 + 0.35e-3 * (k + 0.5) * (10.125 / 10), -0.8e-3) for k in range(10)]
W.TX = top + bot
W.L_tx = W.self_L(W.TX, 0.1e-3)
W.R_tx = 1.72e-8 * W.longueur(W.TX) / (0.2e-3 * 35e-6) * 1.15
CTX = 12.2e-9
RSER = 0.1 - 0.25 + 0.04 + 1.1          # spice() ajoute déjà 0,25 Ω de commutateur : on corrige
print(f"L_tx = {W.L_tx*1e6:.3f} µH, R_tx = {W.R_tx:.2f} Ω, f0 = {1/(2*math.pi*math.sqrt(W.L_tx*CTX))/1e3:.0f} kHz")
w = 2 * math.pi * W.F
res = {"L_tx_uH": W.L_tx * 1e6, "R_tx": W.R_tx, "C_tx_nF": CTX * 1e9, "R_serie": RSER + 0.25, "cas": {}}
for k in W.RX:
    C5 = 1.0e-9 if k == "D20" else 1 / (w * w * W.L_rx[k])     # D20 : C5 réel = 1 nF C0G (BOM du cœur)
    rows = []
    for gap in (1.5, 2.0, 2.5):
        for off in (0.0, 1.5):
            M = W.M_of(k, gap, off)
            v, i, p = W.spice(k, M, W.L_rx[k], W.R_rx[k], C5, CTX, RSER)
            rows.append([gap, off, round(M * 1e9), round(v, 2), round(i, 3), round(p, 3)])
            print(f"{k} écart {gap} décentrage {off}: M={M*1e9:.0f} nH -> {v:.2f} V, Itx {i:.3f} A, pertes {p:.2f} W")
    res["cas"][k] = rows
v, i, p = W.spice("D20", 0, W.L_rx["D20"], W.R_rx["D20"], 1e-9, CTX, RSER, with_rx=False)
print(f"à vide : Itx {i:.3f} A, pertes {p:.2f} W"); res["a_vide"] = [i, p]
# tolérances : Ctx ±5 %, C5 ±5 %, L ±5 %
rng = np.random.default_rng(1); mins = []
for n in range(40):
    ctx = CTX * rng.uniform(0.95, 1.05); c5 = 1e-9 * rng.uniform(0.95, 1.05); lr = W.L_rx["D20"] * rng.uniform(0.95, 1.05)
    v, i, p = W.spice("D20", W.M_of("D20", 2.0, 1.5), lr, W.R_rx["D20"], c5, ctx, RSER); mins.append(v)
print(f"Monte-Carlo D20 (écart 2 mm, décentré 1,5) : min {min(mins):.2f} V, médiane {np.median(mins):.2f} V")
res["mc_D20"] = {"min": min(mins), "mediane": float(np.median(mins))}
json.dump(res, open("/home/claude/de-mandragore/sim_tx_carte.json", "w"), indent=1, default=float)
