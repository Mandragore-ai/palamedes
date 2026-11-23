import os, math, re, subprocess, tempfile, json
os.environ["RLIM"] = "1.0"
import sim_wpt as W
w = 2 * math.pi * W.F
def run(k, gap, off, Rlim, RL, Lmul=1.0):
    M = W.M_of(k, gap, off) * math.sqrt(Lmul); Lr = W.L_rx[k] * Lmul; kk = M / math.sqrt(W.L_tx * Lr); C5 = 1 / (w * w * W.L_rx[k]); per = 1 / W.F; T = 2e-3
    net = f"""* r
Vsw sw 0 PULSE(0 5 0 5n 5n {per/2-5e-9} {per})
Rsw sw n1 {0.25+Rlim}
Ctx n1 n2 {W.Ctx}
Rtx n2 t {W.R_tx}
Ltx t 0 {W.L_tx}
Lrx a 0 {Lr}
K1 Ltx Lrx {kk}
Rrx a b {W.R_rx[k]}
C5 b x {C5}
D1 0 x BAT54
D2 x vr BAT54
Vz vr vz 0
Dz1 0 vz DZ
C6 vr 0 4.7u
RL vr 0 {RL}
.model BAT54 D(Is=2e-7 N=1.02 Rs=1.2 Cjo=10p BV=30)
.model DZ D(Is=1e-14 N=1 Rs=2 BV=5.6 IBV=1m)
.tran {per/50} {T} {T*0.85} uic
.control
run
meas tran vdc AVG v(vr) from={T*0.9} to={T}
meas tran iz AVG i(Vz) from={T*0.9} to={T}
meas tran itx RMS i(Vsw) from={T*0.9} to={T}
quit
.endc
.end"""
    p = tempfile.mktemp(suffix=".cir"); open(p, "w").write(net)
    o = subprocess.run(["ngspice", "-b", p], capture_output=True, text=True).stdout; os.unlink(p)
    g = lambda n: float(re.search(rf"{n}\s*=\s*([-\d.eE+]+)", o).group(1))
    return g("vdc"), abs(g("iz")) * g("vdc"), g("itx")
rows = []
for Rlim in (1.0, 2.2, 3.3, 4.7, 6.8):
    worst = min(run(k, 3.0, 1.5, Rlim, 150, Lm)[0] for k in ("D20", "D6-D12") for Lm in (0.85, 1.15))
    pz = max(run(k, g, 0.0, Rlim, 1e4)[1] for k in ("D20", "D6-D12") for g in (1.0, 2.0, 3.0))
    idle = (5 * 2 / math.pi) / math.sqrt(2) / (W.R_tx + 0.25 + Rlim)
    rows.append((Rlim, worst, pz, idle ** 2 * (W.R_tx + 0.25 + Rlim)))
    print(f"R lim {Rlim} Ω : pire tension en charge {worst:.2f} V | zener pile pleine max {pz*1e3:.0f} mW | à vide ≈ {rows[-1][3]:.2f} W")
json.dump(rows, open("/home/claude/de-mandragore/sim_wpt_rlim.json", "w"))
