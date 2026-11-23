"""Monte-Carlo des tolérances + dissipation de la zener pile pleine + détection de présence."""
import os, sys, json, math, re, subprocess, tempfile
import numpy as np
os.environ.setdefault("RLIM", "1.0")
import sim_wpt as W
rng = np.random.default_rng(3)
w = 2 * math.pi * W.F
out = {}
for k in ("D20", "D6-D12"):
    C5n = 1 / (w * w * W.L_rx[k]); res = []
    for (gap, off) in ((1.0, 0.0), (3.0, 1.5)):
        M0 = W.M_of(k, gap, off)
        for _ in range(25):
            Lr = W.L_rx[k] * rng.uniform(0.85, 1.15)          # bobinage à la main : ±15 %
            C5 = C5n * rng.uniform(0.95, 1.05)                # C0G ±5 %
            Ct = W.Ctx * rng.uniform(0.95, 1.05)
            M = M0 * math.sqrt(Lr / W.L_rx[k])
            v, i, p = W.spice(k, M, Lr, W.R_rx[k], C5, Ct, 1.0)
            res.append((gap, off, v))
    vs = [r[2] for r in res]
    out[k] = {"min_V": min(vs), "max_V": max(vs), "n": len(vs)}
    print(k, "tolérances : Vdc min %.2f V, max %.2f V sur %d tirages" % (min(vs), max(vs), len(vs)))
# zener pile pleine (TP4054 ne tire presque plus rien) : charge 10 kΩ, écart le plus favorable
def zener_power(k, gap):
    M = W.M_of(k, gap, 0.0); C5 = 1 / (w * w * W.L_rx[k])
    net_v, i, p = W.spice(k, M, W.L_rx[k], W.R_rx[k], C5, W.Ctx, 1.0, RL=1e4)
    return net_v
for k in ("D20",):
    v = zener_power(k, 1.0)
    print(f"pile pleine, écart 1 mm : Vdc = {v:.2f} V")
json.dump(out, open("/home/claude/de-mandragore/sim_wpt_mc.json", "w"), indent=1)
