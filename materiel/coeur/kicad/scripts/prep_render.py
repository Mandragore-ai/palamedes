"""Prépare les maillages pour les rendus Blender (repère palet, mm)."""
import json, math, os, sys
import numpy as np
import trimesh
from trimesh.creation import cylinder, box
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
import sim_pads as S

OUT = "/home/claude/de-mandragore/render/meshes"; os.makedirs(OUT, exist_ok=True)
SH = "/home/claude/de-mandragore/shell"
g = json.load(open(f"{SH}/D20_geometrie.json"))
N = np.array(g["normales"]); bottom = g["face_recharge"]

shell = trimesh.load(f"{SH}/D20_coque_assemblee.stl")
top = shell.slice_plane([0, 0, 0], [0, 0, 1], cap=True)
bot = shell.slice_plane([0, 0, 0], [0, 0, -1], cap=True)
top.export(f"{OUT}/coque_haut.stl"); bot.export(f"{OUT}/coque_bas.stl")

# pastilles de cuivre (75 % de chaque face), au fond des logements (0,15 mm) — épaisseur 0,08 mm
R_IN = g["F2F_mm"] / 2
ANG = math.radians(20.3)
R0 = S.rot_to(np.array([0, 0, 1.0]), S.normals[7])
Rz = np.array([[math.cos(ANG), -math.sin(ANG), 0], [math.sin(ANG), math.cos(ANG), 0], [0, 0, 1]])
M = (R0 @ Rz).T
V = (S.V * (R_IN / S.inr0)) @ M.T
pads_top, pads_bot = [], []
for f, (i, j, k) in enumerate(S.faces):
    tri = np.array([V[i], V[j], V[k]]); c = tri.mean(0); n = N[f]
    tin = c + 0.75 * (tri - c)
    pts = np.vstack([tin - n * 0.15, tin - n * 0.07])
    p = trimesh.convex.convex_hull(pts)
    (pads_top if c[2] > 0 else pads_bot).append(p)
trimesh.util.concatenate(pads_top).export(f"{OUT}/cuivre_haut.stl")
trimesh.util.concatenate(pads_bot).export(f"{OUT}/cuivre_bas.stl")

# palet de résine et son contenu
puck = cylinder(radius=8.6, height=10.2, sections=96); puck.export(f"{OUT}/palet.stl")
pile = cylinder(radius=6.05, height=5.4, sections=72); pile.apply_translation([0, 0, -4.6 + 2.7]); pile.export(f"{OUT}/pile.stl")
pcb = cylinder(radius=8.0, height=0.8, sections=96); pcb.apply_translation([0, 0, 2.5]); pcb.export(f"{OUT}/circuit.stl")
mod = box(extents=[7.8, 8.8, 1.3]); mod.apply_translation([0, -1.6 * -1, 2.9 + 0.65]); mod.export(f"{OUT}/module.stl")
acc = box(extents=[2, 2, 0.9]); acc.apply_translation([1.6, -4.6, 2.9 + 0.45]); acc.export(f"{OUT}/accelero.stl")
# bobine sous la face de recharge
nb = N[bottom]; cb = V[list(S.faces[bottom])].mean(0)
coil = trimesh.creation.annulus(r_min=1.6, r_max=3.8, height=1.0, sections=72)
T = np.eye(4); T[:3, :3] = S.rot_to(np.array([0, 0, 1.0]), -nb); T[:3, 3] = cb - nb * (0.8 + 0.5)
coil.apply_transform(T); coil.export(f"{OUT}/bobine.stl")
json.dump({"normale_recharge": nb.tolist(), "centre_face_recharge": cb.tolist()}, open(f"{OUT}/infos.json", "w"))

# boîte + dés en place
sys.argv = ["x"]
src = open("/home/claude/de-mandragore/scripts/make_box.py").read()
src = src.split("os.makedirs(OUT")[0]
ns = {}
exec(compile(src, "make_box", "exec"), ns)
dice = []
for c in ns["cuts"]:
    d = c.copy(); ctr = d.centroid
    # dé réel = logement réduit du jeu (0,35 mm) autour de son centre
    d.apply_translation(-ctr); d.apply_scale(1 - 0.35 / 11.5); d.apply_translation(ctr + [0, 0, -0.35 * 0.0])
    d.apply_translation([0, 0, ns["z_floor"] - d.bounds[0][2]])
    dice.append(d)
trimesh.util.concatenate(dice).export(f"{OUT}/des_boite.stl")
trimesh.load("/home/claude/de-mandragore/charger/boite_chargeur_corps.stl").export(f"{OUT}/boite.stl")
print("ok", os.listdir(OUT))
