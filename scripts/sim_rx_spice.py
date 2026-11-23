"""Simulation temporelle (ngspice) du récepteur de recharge du dé : bobine couplée à l'émetteur,
accord parallèle (C3) ou série (C5), doubleur BAT54S, zener 5,6 V, condensateur C6, charge TP4054 ≈ 150 Ω.
Compare : A = montage actuel (C3 accordé, 36 spires) ; B = accord série par C5 (C3 retiré) ;
C = 72 spires + C3 ; D = 72 spires + accord série. Émetteur modélisé en source de courant (0,5 A et 1 A crête)."""
import subprocess, math, re, json, os, tempfile, sys
import numpy as np

M15 = {"D20": 0.947e-6, "kit10": 0.799e-6}         # mutuelle à 1,5 mm (sim_coil.py), 36 et 24 spires
LRX = {"D20": 6.8e-6, "kit10": 3.4e-6}
RRX = {"D20": 1.69, "kit10": 1.35}
LTX = 0.87e-6


def run(f, Itx, coil, turns_mul, mode):
    L = LRX[coil] * turns_mul ** 2; R = RRX[coil] * turns_mul; M = M15[coil] * turns_mul
    k = M / math.sqrt(L * LTX)
    w = 2 * math.pi * f; Cres = 1 / (w * w * L)
    if mode == "parallele": C3, C5 = Cres, 1e-6
    else: C3, C5 = 1e-12, Cres
    T = 4e-3
    net = f"""* recepteur
Itx 0 tx SIN(0 {Itx} {f})
Ltx tx 0 {LTX}
Lrx a 0 {L}
K1 Ltx Lrx {min(k, 0.99)}
Rc a coil {R}
C3 coil 0 {C3}
C5 coil x {C5}
D1 0 x BAT54
D2 x vr BAT54
Dz1 0 vr DZ
C6 vr 0 4.7u
RL vr 0 150
.model BAT54 D(Is=2e-7 N=1.02 Rs=1.2 Cjo=10p BV=30)
.model DZ D(Is=1e-14 N=1 Rs=2 BV=5.6 IBV=1m)
.options reltol=1e-3
.tran {1/f/40} {T} {T*0.8} uic
.control
run
meas tran vmoy AVG v(vr) from={T*0.85} to={T}
quit
.endc
.end
"""
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as fh:
        fh.write(net); p = fh.name
    out = subprocess.run(["ngspice", "-b", p], capture_output=True, text=True, timeout=600).stdout
    os.unlink(p)
    m = re.search(r"vmoy\s*=\s*([-\d.eE+]+)", out)
    return float(m.group(1)) if m else float("nan"), Cres


res = []
for coil in ("D20", "kit10"):
    for f in (150e3, 500e3, 1e6):
        for Itx in (0.5, 1.0):
            row = {"bobine": coil, "f_kHz": f / 1e3, "Itx_A": Itx}
            for lab, mul, mode in (("A_actuel", 1, "parallele"), ("B_serie_C5", 1, "serie"), ("C_x2_spires", 2, "parallele"), ("D_x2_spires_serie", 2, "serie")):
                v, c = run(f, Itx, coil, mul, mode)
                row[lab] = round(v, 2); row[lab + "_C_nF"] = round(c * 1e9, 1)
            res.append(row)
            print(row, flush=True)
json.dump(res, open("/home/claude/de-mandragore/sim_rx_spice.json", "w"), indent=1)
