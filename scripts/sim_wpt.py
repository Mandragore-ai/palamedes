"""Conception de la recharge sans fil complète (émetteur maison + récepteur du dé), validée par SPICE.

Émetteur : bobine spirale gravée sur PCB 2 couches (Ø10 mm), accord série, pont en demi-pont alimenté en 5 V,
fréquence fixe. Récepteur : bobine galette bobinée (D20 : Ø7,5 mm) ou Ø10 (autres dés), accord série par C5,
doubleur BAT54S, zener 5,6 V, C6 4,7 µF, charge TP4054 ≈ 150 Ω (30 mA sous 4,5 V).

Étapes : inductances et mutuelles (Neumann) -> SPICE nominal -> Monte-Carlo de tolérances.
"""
import math, json, re, os, subprocess, tempfile, sys
import numpy as np
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
from sim_coil import mutuelle, mutuelle_boucles, MU0   # noqa (réutilise Neumann)

# ------------------------------------------------------------------ bobines
def spirale_pcb(r_out, r_in, pas, z_couches):
    rs = np.arange(r_out - pas / 2, r_in, -pas)
    return [(r, z) for z in z_couches for r in rs]

def galette(r_in, r_out, n_rad, n_couches, pas_z, z0=0.0):
    rs = np.linspace(r_in, r_out, n_rad)
    return [(r, z0 + k * pas_z) for k in range(n_couches) for r in rs]

def self_L(c, rfil):
    L = 0.0
    for i, (a, z1) in enumerate(c):
        L += MU0 * a * (math.log(8 * a / rfil) - 2)
        for j in range(i + 1, len(c)):
            b, z2 = c[j]
            L += 2 * mutuelle_boucles(a, b, abs(z2 - z1), 0.0)
    return L

def longueur(c): return sum(2 * math.pi * r for r, _ in c)

F = 1.0e6                                   # fréquence de travail retenue
# émetteur : PCB 2 couches de 0,8 mm, cuivre 35 µm, piste 0,2 / espace 0,15 -> pas 0,35 mm
TX = spirale_pcb(5.0e-3, 1.6e-3, 0.35e-3, [0.0, -0.8e-3])
L_tx = self_L(TX, 0.1e-3)
R_tx = 1.72e-8 * longueur(TX) / (0.2e-3 * 35e-6) * 1.15           # +15 % (peau/proximité à 1 MHz, 35 µm < δ=66 µm)
# récepteurs : fil émaillé 0,1 mm
RX = {"D20": galette(1.6e-3, 3.65e-3, 9, 8, 0.12e-3),           # 72 spires, Ø7,5 × 1,0 mm
      "D6-D12": galette(1.6e-3, 4.8e-3, 13, 5, 0.12e-3)}        # 65 spires, Ø10 × 0,6 mm
L_rx = {k: self_L(v, 0.05e-3) for k, v in RX.items()}
R_rx = {k: 1.72e-8 * longueur(v) / (math.pi * 0.05e-3 ** 2) * 1.3 for k, v in RX.items()}
print(f"TX : {len(TX)} spires, L = {L_tx*1e6:.2f} µH, R = {R_tx:.2f} Ω")
for k in RX: print(f"RX {k} : {len(RX[k])} spires, L = {L_rx[k]*1e6:.2f} µH, R = {R_rx[k]:.2f} Ω")

# géométrie : surface du cuivre TX -> plancher 0,6 -> face du dé -> 0,8 mm -> bobine RX (sa face basse)
def M_of(k, gap_mm, off_mm):
    # gap = distance entre la couche haute du PCB et la face basse de la bobine du dé
    return mutuelle(TX, RX[k], gap_mm * 1e-3, off_mm * 1e-3)

# ------------------------------------------------------------------ SPICE
def spice(k, M, Lrx, Rrx, C5, Ctx, Rlim, Vbus=5.0, RL=150.0, with_rx=True):
    kk = min(M / math.sqrt(L_tx * Lrx), 0.98)
    per = 1 / F; T = 2.0e-3
    rx = f"""Lrx a 0 {Lrx}
K1 Ltx Lrx {kk}
Rrx a b {Rrx}
C5 b x {C5}
D1 0 x BAT54
D2 x vr BAT54
Dz1 0 vr DZ
C6 vr 0 4.7u
RL vr 0 {RL}""" if with_rx else ""
    net = f"""* wpt
Vb bus 0 {Vbus}
Vsw sw 0 PULSE(0 {Vbus} 0 5n 5n {per/2-5e-9} {per})
Rsw sw n1 {0.25 + Rlim}
Ctx n1 n2 {Ctx}
Rtx n2 t {R_tx}
Ltx t 0 {L_tx}
{rx}
.model BAT54 D(Is=2e-7 N=1.02 Rs=1.2 Cjo=10p BV=30)
.model DZ D(Is=1e-14 N=1 Rs=2 BV=5.6 IBV=1m)
.options reltol=2e-3
.tran {per/50} {T} {T*0.85} uic
.control
run
meas tran vdc AVG v(vr) from={T*0.9} to={T}
meas tran itx RMS i(Vsw) from={T*0.9} to={T}
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as fh:
        fh.write(net); p = fh.name
    o = subprocess.run(["ngspice", "-b", p], capture_output=True, text=True, timeout=600).stdout; os.unlink(p)
    g = lambda n: float(re.search(rf"{n}\s*=\s*([-\d.eE+]+)", o).group(1)) if re.search(rf"{n}\s*=\s*([-\d.eE+]+)", o) else float("nan")
    vdc = g("vdc") if with_rx else 0.0; itx = g("itx")
    return vdc, itx, itx ** 2 * (R_tx + 0.25 + Rlim)     # pertes ohmiques côté émetteur (W)

w = 2 * math.pi * F
Ctx = 1 / (w * w * L_tx)
res = {"f_Hz": F, "L_tx_uH": L_tx * 1e6, "R_tx": R_tx, "C_tx_nF": Ctx * 1e9,
       "L_rx_uH": {k: v * 1e6 for k, v in L_rx.items()}, "R_rx": R_rx, "C5_nF": {}, "balayages": {}, "montecarlo": {}}

if __name__ == "__main__":
    RLIM = float(os.environ.get("RLIM", "1.0"))
    for k in RX:
        C5 = 1 / (w * w * L_rx[k]); res["C5_nF"][k] = C5 * 1e9
        print(f"\n== {k} : C5 = {C5*1e9:.2f} nF, C_tx = {Ctx*1e9:.2f} nF, R série émetteur = {RLIM} Ω")
        rows = []
        for gap in (1.0, 1.5, 2.0, 2.5, 3.0):
            for off in (0.0, 1.0, 1.5):
                M = M_of(k, gap, off)
                v, i, p = spice(k, M, L_rx[k], R_rx[k], C5, Ctx, RLIM)
                rows.append((gap, off, round(M * 1e9), round(v, 2), round(i, 3), round(p, 2)))
                print(f"  écart {gap} mm, décentrage {off} mm : M = {M*1e9:.0f} nH -> {v:.2f} V, I_tx = {i:.2f} A eff, pertes TX {p:.2f} W")
        res["balayages"][k] = rows
    v, i, p = spice("D20", 0, L_rx["D20"], R_rx["D20"], 1e-9, Ctx, RLIM, with_rx=False)
    res["a_vide"] = {"I_tx_A": i, "pertes_W": p}
    print(f"\nà vide (pas de dé) : I_tx = {i:.2f} A eff, pertes {p:.2f} W par emplacement")
    json.dump(res, open(f"/home/claude/de-mandragore/sim_wpt_R{RLIM}.json", "w"), indent=1, default=float)
