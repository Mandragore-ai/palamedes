"""Coque D20 (22,5 mm face à face) pour le cœur D-core v0.1 — deux moitiés imprimables.

Repère « palet » : axe z = axe du palet (circuit en haut, bobine en bas) ; la face du bas
(normale -z) est la face de recharge. Le cœur (bobine + pile + circuit) est posé dans la cavité
puis noyé dans la résine coulée par le trou de remplissage : la coque sert de moule.

Éléments :
- cavité cylindrique Ø17,2 × 11,2 mm (palet de résine contenant le cœur)
- 20 logements de pastilles (triangles à 75 %, profondeur 0,15 mm) sur les faces extérieures
- ponts de 1 mm entre faces voisines d'un même groupe (continuité du ruban de cuivre / encre)
- 4 trous Ø0,9 mm (un par groupe) de la pastille vers la cavité, pour les fils G1..G4
- trou de remplissage Ø1,6 et évent Ø1,0 aux sommets (hors pastilles)
- logement de lest Ø3 × 3 mm dans l'axe, au-dessus du palet (pâte de tungstène)
- 3 trous de goupille Ø1,05 × 2 mm sur le plan de joint (goupilles = filament 1 mm)
"""
import json, math, sys
import numpy as np
import trimesh
from trimesh.creation import cylinder
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
import sim_pads as S

OUT = "/home/claude/de-mandragore/shell"
F2F = 22.5
R_IN = F2F / 2
CAV_R, CAV_H = 8.6, 11.2
PAD_SCALE, PAD_DEPTH = 0.75, 0.15
BRIDGE_W = 1.0
WIRE_D = 0.9

# orientation trouvée par optimisation : axe du palet sur la normale de la face 7, rotation 20,3°
ANG = math.radians(20.3)
R0 = S.rot_to(np.array([0, 0, 1.0]), S.normals[7])
Rz = np.array([[math.cos(ANG), -math.sin(ANG), 0], [math.sin(ANG), math.cos(ANG), 0], [0, 0, 1]])
M = (R0 @ Rz).T                     # repère D20 -> repère palet
scale = R_IN / S.inr0
V = (S.V * scale) @ M.T
FACES = S.faces
N = S.normals @ M.T                 # normales dans le repère palet
GROUP = S.groups4_clustered()
bottom = int(np.argmin(N[:, 2])); top = int(np.argmax(N[:, 2]))


def manifold_ok(m):
    return m.is_watertight and m.is_volume


body = trimesh.convex.convex_hull(V)
cuts = []

# cavité
cav = cylinder(radius=CAV_R, height=CAV_H, sections=96)
cuts.append(cav)


def prism_from_tri(tri, normal, depth, extra=0.3):
    """prisme triangulaire : de la surface vers l'intérieur sur depth (+extra vers l'extérieur)"""
    a = np.array(tri)
    top_ = a + normal * extra
    bot_ = a - normal * depth
    pts = np.vstack([top_, bot_])
    return trimesh.convex.convex_hull(pts)


def box_between(p0, p1, normal, width, depth, extra=0.3):
    """barreau plat le long de la surface, de p0 à p1 (points sur la surface)"""
    d = p1 - p0; L = np.linalg.norm(d); u = d / L
    w = np.cross(normal, u); w /= np.linalg.norm(w)
    corners = []
    for s in (-1, 1):
        for q in (p0, p1):
            for h in (extra, -depth):
                corners.append(q + w * s * width / 2 + normal * h)
    return trimesh.convex.convex_hull(np.array(corners))


pad_tris = {}
for f, (i, j, k) in enumerate(FACES):
    tri = [V[i], V[j], V[k]]
    c = sum(tri) / 3
    tri_in = [c + PAD_SCALE * (p - c) for p in tri]
    pad_tris[f] = (tri, tri_in, c)
    cuts.append(prism_from_tri(tri_in, N[f], PAD_DEPTH))

# ponts entre faces voisines d'un même groupe : à travers le milieu de l'arête commune
bridges = 0
for f1 in range(20):
    for f2 in range(f1 + 1, 20):
        if GROUP[f1] != GROUP[f2]: continue
        shared = set(FACES[f1]) & set(FACES[f2])
        if len(shared) != 2: continue
        a, b = [V[s] for s in shared]; mid = (a + b) / 2
        for f in (f1, f2):
            c = pad_tris[f][2]
            p_in = mid + PAD_SCALE * 0.0 + (c - mid) * 0.35     # pénètre dans le triangle de pastille
            cuts.append(box_between(p_in, mid, N[f], BRIDGE_W, PAD_DEPTH))
        bridges += 1

# trous de fil : pour chaque groupe, la face dont la normale rentrante touche le flanc de la cavité
wire_holes = []
for g in range(4):
    cand = []
    for f in range(20):
        if GROUP[f] != g or f in (top, bottom): continue
        c = pad_tris[f][2]
        # point d'entrée dans la cavité le long de -normale
        for t in np.linspace(0, R_IN, 400):
            p = c - N[f] * t
            if math.hypot(p[0], p[1]) <= CAV_R and abs(p[2]) <= CAV_H / 2:
                break
        cand.append((abs(p[2] - 2.0), f, c, p))     # sortir près du circuit (z ≈ +2 mm)
    cand.sort(key=lambda x: x[0])
    _, f, c, p = cand[0]
    L = np.linalg.norm(p - c) + 0.6
    h = cylinder(radius=WIRE_D / 2, height=L + 0.6, sections=24)
    axis = -N[f]
    T = np.eye(4); T[:3, :3] = S.rot_to(np.array([0, 0, 1.0]), axis); T[:3, 3] = c + axis * (L / 2 - 0.3)
    h.apply_transform(T); cuts.append(h)
    wire_holes.append({"groupe": g + 1, "face": int(f), "entree_cavite_mm": [round(float(v), 2) for v in p],
                       "azimut_deg": round(math.degrees(math.atan2(p[1], p[0])) % 360, 1)})

# remplissage + évent : par deux sommets du haut (hors pastilles), vers la cavité
vz = sorted(range(12), key=lambda i: -V[i][2])
fill_pts = []
for idx, (vi, d) in enumerate(((vz[0], 1.6), (vz[1], 1.0))):
    v = V[vi]; axis = -v / np.linalg.norm(v)
    L = np.linalg.norm(v) - CAV_H / 2 + 1.0
    h = cylinder(radius=d / 2, height=L, sections=24)
    T = np.eye(4); T[:3, :3] = S.rot_to(np.array([0, 0, 1.0]), axis); T[:3, 3] = v + axis * (L / 2 - 0.3)
    h.apply_transform(T); cuts.append(h); fill_pts.append(vi)

# logement de lest dans l'axe, au-dessus du palet
ballast = cylinder(radius=1.5, height=3.0, sections=32); ballast.apply_translation([0, 0, CAV_H / 2 + 1.5 - 0.01])
cuts.append(ballast)

shell = body.difference(trimesh.boolean.union(cuts, engine="manifold"), engine="manifold")

# goupilles d'alignement sur le plan de joint z = 0 (dans la paroi, hors cavité)
pins = []
for a in (90, 210, 330):
    r = (CAV_R + R_IN * 0.98) / 2 + 0.2
    p = cylinder(radius=1.05 / 2, height=4.0, sections=20); p.apply_translation([r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0])
    pins.append(p)
shell = shell.difference(trimesh.boolean.union(pins, engine="manifold"), engine="manifold")

big = 40
top_half = shell.intersection(trimesh.creation.box(extents=[big, big, big], transform=trimesh.transformations.translation_matrix([0, 0, big / 2])), engine="manifold")
bot_half = shell.intersection(trimesh.creation.box(extents=[big, big, big], transform=trimesh.transformations.translation_matrix([0, 0, -big / 2])), engine="manifold")

import os
os.makedirs(OUT, exist_ok=True)
# moitié haute retournée (plan de joint à plat sur le plateau d'impression)
th = top_half.copy(); th.apply_transform(np.diag([1.0, -1.0, -1.0, 1.0]));   # retournement exact (180° autour de x)
th.apply_translation([0, 0, -th.bounds[0][2]])
bh = bot_half.copy(); bh.apply_translation([0, 0, -bh.bounds[0][2]])
def clean(m):
    """aimante les sommets quasi confondus (précision float32 des STL) puis nettoie"""
    m = m.copy(); m.vertices = np.round(m.vertices, 3); m.merge_vertices()
    m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    return m
th, bh = clean(th), clean(bh)
th.export(f"{OUT}/D20_coque_haut.stl"); bh.export(f"{OUT}/D20_coque_bas.stl")
shell.export(f"{OUT}/D20_coque_assemblee.stl")

# géométrie pour le firmware : normales des faces dans le repère palet + groupes
geo = {"F2F_mm": F2F, "face_recharge": bottom, "face_haut": top,
       "normales": [[round(float(x), 5) for x in n] for n in N],
       "groupe_de_chaque_face": [int(g) + 1 for g in GROUP],
       "trous_fils": wire_holes, "sommets_remplissage_event": [int(v) for v in fill_pts]}
json.dump(geo, open(f"{OUT}/D20_geometrie.json", "w"), indent=1)
print("étanche:", manifold_ok(shell), "| volume coque cm3:", round(shell.volume / 1000, 2),
      "| moitiés:", manifold_ok(th), manifold_ok(bh), "| ponts:", bridges)
print("trous de fil:", wire_holes)
