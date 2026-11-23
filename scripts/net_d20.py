"""Numérotation (faces opposées = 21, face de recharge = 1), correspondance groupes -> pastilles du circuit,
et patron déplié 1:1 (PDF/PNG) servant de gabarit pour la peinture et la découpe du cuivre."""
import json, math, sys, itertools
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
import sim_pads as S
D = "/home/claude/de-mandragore/shell"
g = json.load(open(f"{D}/D20_geometrie.json"))
N = np.array(g["normales"]); GROUP = g["groupe_de_chaque_face"]
F = S.faces
charge = g["face_recharge"]
opp = {f: int(np.argmin(N @ N[f])) for f in range(20)}
# numérotation : recharge = 1 ; on parcourt les faces par proximité angulaire depuis la face de recharge
num = {charge: 1, opp[charge]: 20}
order = sorted(range(20), key=lambda f: -(N[f] @ N[charge]))
k = 2
for f in order:
    if f in num: continue
    num[f] = k; num[opp[f]] = 21 - k; k += 1
assert sorted(num.values()) == list(range(1, 21)) and all(num[f] + num[opp[f]] == 21 for f in range(20))
# câblage : trou du groupe -> pastille du circuit (alignement des azimuts, voir notice)
GROUP_TO_PAD = {1: "G3", 2: "G4", 3: "G2", 4: "G1"}
PAD_TO_GPIO = {"G1": "P0.11", "G2": "P0.12", "G3": "P0.13", "G4": "P0.18"}
holes = {h["face"]: h["groupe"] for h in g["trous_fils"]}

# ---- dépliage : arbre couvrant en largeur depuis la face de recharge
edge = 22.5 / 2 / S.inr0 * 2.0          # longueur d'arête (mm) : arête unité = 2 dans S.V
adj = {i: [] for i in range(20)}
for i, j in itertools.combinations(range(20), 2):
    sh = set(F[i]) & set(F[j])
    if len(sh) == 2: adj[i].append((j, tuple(sorted(sh)))); adj[j].append((i, tuple(sorted(sh))))
pos = {}
h3 = math.sqrt(3) / 2
f0 = charge; a, b, c = F[f0]
pos[f0] = {a: np.array([0.0, 0.0]), b: np.array([edge, 0.0]), c: np.array([edge / 2, edge * h3])}
placed = [f0]; queue = [f0]
tris2d = {}
def tri_ok(P, others):
    cen = sum(P) / 3
    for Q in others:
        qc = sum(Q) / 3
        if np.linalg.norm(cen - qc) < edge * 0.55: return False
    return True
while queue:
    f = queue.pop(0)
    for (n_, sh) in sorted(adj[f], key=lambda x: num[x[0]]):
        if n_ in pos: continue
        p, q = sh; P, Q = pos[f][p], pos[f][q]
        third_f = [v for v in F[f] if v not in sh][0]; R = pos[f][third_f]
        third_n = [v for v in F[n_] if v not in sh][0]
        mid = (P + Q) / 2; T = 2 * mid - R           # reflet du sommet opposé
        cand = {p: P, q: Q, third_n: T}
        if not tri_ok([P, Q, T], [list(v.values()) for v in pos.values()]): continue
        pos[n_] = cand; queue.append(n_)
missing = [f for f in range(20) if f not in pos]
assert not missing, missing
cols = {1: "#4C78A8", 2: "#F58518", 3: "#54A24B", 4: "#B279A2"}
allp = np.array([v for d in pos.values() for v in d.values()])
w, hgt = allp.max(0) - allp.min(0)
fig_w, fig_h = 210 / 25.4, 297 / 25.4          # A4
fig = plt.figure(figsize=(fig_w, fig_h)); ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 210); ax.set_ylim(0, 297); ax.axis("off")
off = np.array([(210 - w) / 2, 297 - 30 - hgt]) - allp.min(0)
for f, d in pos.items():
    P = [d[v] + off for v in F[f]]
    ax.add_patch(MPoly(P, closed=True, fill=False, lw=0.4, ec="black"))
    cen = sum(P) / 3
    Pin = [cen + 0.75 * (p - cen) for p in P]
    ax.add_patch(MPoly(Pin, closed=True, fc=cols[GROUP[f]], ec="none", alpha=0.55))
    ax.text(*cen, str(num[f]), ha="center", va="center", fontsize=9, weight="bold")
    if f in holes: ax.plot(cen[0], cen[1] - 2.6, "o", ms=3.2, mfc="white", mec="black", mew=0.7)
    if f == charge:
        ax.text(cen[0], cen[1] + 2.4, "recharge", ha="center", fontsize=4.5)
        # pastille en peigne : 5 fentes depuis un bord, pour ne pas former de boucle sous la bobine
        A, B, C = Pin
        for k in range(1, 6):
            t = k / 6; p0 = A + (B - A) * t; p1 = p0 + (C - (A + B) / 2) * 0.82
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="white", lw=1.1)
y = 297 - 30 - hgt - 10
ax.text(105, 285, "D20 Mandragore — patron 1:1 (22,5 mm face à face)", ha="center", fontsize=11, weight="bold")
ax.text(105, 279, "Imprimer à 100 % (sans mise à l'échelle). Triangles colorés = pastilles de cuivre (75 % de la face).", ha="center", fontsize=7)
lines = ["Groupes (couleur) -> fil -> pastille du circuit -> broche nRF :"]
for gr in range(1, 5):
    faces_g = sorted(num[f] for f in range(20) if GROUP[f] == gr)
    hole_face = [num[f] for f, gg in holes.items() if gg == gr][0]
    lines.append(f"  groupe {gr} : faces {faces_g} ; trou de fil sur la face {hole_face} -> {GROUP_TO_PAD[gr]} ({PAD_TO_GPIO[GROUP_TO_PAD[gr]]})")
lines += ["Cercle blanc = trou de fil vers la cavité. Les faces voisines d'un même groupe sont reliées par un pont (1 mm) au milieu de l'arête.",
          "Faces opposées : somme 21. La face 1 est la face de recharge (bobine) ; la face 20 est en haut pendant la charge.",
          "Face 1 : cuivre découpé EN PEIGNE (fentes blanches, ~0,5 mm) — une plaque pleine bloquerait la recharge sans fil."]
for i, t in enumerate(lines):
    ax.text(15, y - i * 5, t, fontsize=6.5, family="monospace")
for i, (c_, lab) in enumerate(cols.items()):
    pass
ax.plot([15, 65], [12, 12], color="black", lw=0.6); ax.text(40, 14, "50 mm (contrôle d'échelle)", ha="center", fontsize=6)
plt.savefig(f"{D}/D20_patron_A4.pdf"); plt.savefig(f"{D}/D20_patron_A4.png", dpi=160)
table = {"numero_de_la_face": {str(f): num[f] for f in range(20)},
         "groupe_vers_pastille_circuit": GROUP_TO_PAD, "pastille_vers_gpio": PAD_TO_GPIO}
g.update(table); json.dump(g, open(f"{D}/D20_geometrie.json", "w"), indent=1)
print("ok ; groupes :", {gr: sorted(num[f] for f in range(20) if GROUP[f] == gr) for gr in range(1, 5)})
