"""Boîte-chargeur pour un set de 7 dés Mandragore (impression 3D, deux pièces : boîte + fond vissé).

Chaque logement épouse le dé posé sur sa face de recharge (jeu de 0,35 mm), avec un plancher de 0,6 mm.
Sous les planchers : la carte émettrice MCDice (152 × 82 × 0,8 mm, hw/charger), face cuivre des spirales plaquée
contre le dessous du plancher ; ses encoches d'angle laissent passer les bossages de vis. Le fond porte un téton
sous chaque spirale qui maintient la carte contre le plancher. Prise USB-C (5 V) dans la paroi gauche.
"""
import math, json, os, sys
import numpy as np
import trimesh
from scipy.spatial import HalfspaceIntersection, ConvexHull
sys.path.insert(0, "/home/claude/de-mandragore/scripts")
import sim_pads as S

OUT = "/home/claude/de-mandragore/charger"
phi = (1 + 5 ** 0.5) / 2


def normals(name):
    import itertools
    if name == "D6":
        v = [p for p in itertools.product([-1, 0, 1], repeat=3) if sum(map(abs, p)) == 1]
    elif name == "D8":
        v = list(itertools.product([-1, 1], repeat=3))
    elif name == "D12":
        v = []
        for a in (-1, 1):
            for b in (-1, 1):
                v += [(0, a, b * phi), (a, b * phi, 0), (b * phi, 0, a)]
    elif name == "D20":
        return S.normals.copy()
    elif name == "D10":          # trapézoèdre pentagonal (proportions usuelles)
        el = math.radians(46.0); v = []
        for k in range(5):
            th = 2 * math.pi * k / 5
            v.append((math.cos(el) * math.cos(th), math.cos(el) * math.sin(th), math.sin(el)))
            th2 = th + math.pi / 5
            v.append((math.cos(el) * math.cos(th2), math.cos(el) * math.sin(th2), -math.sin(el)))
    v = np.array(v, float)
    return v / np.linalg.norm(v, axis=1)[:, None]


def solid(name, r):
    """polyèdre convexe de rayon inscrit r (pour le D10 : r = demi-distance entre faces opposées)"""
    n = normals(name)
    hs = np.hstack([n, -r * np.ones((len(n), 1))])
    pts = HalfspaceIntersection(hs, np.zeros(3)).intersections
    return trimesh.convex.convex_hull(pts), n


# (étiquette, forme, taille face à face en mm) — tailles calculées autour du cœur D-core
SET = [("D4*", "D8", 22.0), ("D6", "D6", 20.0), ("D8", "D8", 22.0), ("D10", "D10", 23.0),
       ("D%", "D10", 23.0), ("D12", "D12", 23.0), ("D20", "D20", 22.5)]
CLEAR, FLOOR, HOLLOW, DEPTH = 0.35, 0.6, 7.0, 5.0     # jeu, plancher, creux technique, profondeur des logements
PITCH, MARGIN, WALL = 35.0, 9.0, 2.0
ROWS = [SET[:4], SET[4:]]
W = 4 * PITCH + 2 * MARGIN - PITCH + 34
D = 2 * PITCH + 2 * MARGIN - PITCH + 34
H = HOLLOW + FLOOR + DEPTH
z_floor = HOLLOW + FLOOR

box = trimesh.creation.box(extents=[W, D, H]); box.apply_translation([W / 2, D / 2, H / 2])
cuts, slots = [], []
for ri, row in enumerate(ROWS):
    for ci, (lab, shape, f2f) in enumerate(row):
        cx = MARGIN + 17 + ci * PITCH + (PITCH / 2 if ri == 1 else 0)
        cy = D - (MARGIN + 17) - ri * PITCH
        m, n = solid(shape, f2f / 2 + CLEAR)
        # face de recharge vers le bas : on prend la face dont la normale a la plus petite composante z après rotation
        fc = int(np.argmin(n[:, 2])) if shape != "D20" else int(np.argmin(n @ np.array([0, 0, 1.0])))
        R = S.rot_to(n[fc], np.array([0, 0, -1.0]))
        T = np.eye(4); T[:3, :3] = R; m.apply_transform(T)
        m.apply_translation([cx, cy, z_floor - m.bounds[0][2]])
        cuts.append(m)
        # centre de la bobine = projection du centre du dé
        slots.append({"de": lab, "forme": shape, "taille_mm": f2f, "centre_bobine_mm": [round(cx, 1), round(cy, 1)]})
# creux technique (ouvert en dessous), bossages de vis aux 4 coins
hollow = trimesh.creation.box(extents=[W - 2 * WALL, D - 2 * WALL, HOLLOW + 0.01]); hollow.apply_translation([W / 2, D / 2, HOLLOW / 2 - 0.01])
boss_pos = [(WALL + 3.0, WALL + 3.0), (W - WALL - 3.0, WALL + 3.0), (WALL + 3.0, D - WALL - 3.0), (W - WALL - 3.0, D - WALL - 3.0)]   # bossages engagés de 0,5 mm dans la paroi
bosses = [trimesh.creation.cylinder(radius=3.5, height=HOLLOW, sections=32, transform=trimesh.transformations.translation_matrix([x, y, HOLLOW / 2])) for x, y in boss_pos]
pilots = [trimesh.creation.cylinder(radius=0.9, height=HOLLOW + 2, sections=20, transform=trimesh.transformations.translation_matrix([x, y, HOLLOW / 2])) for x, y in boss_pos]
hollow = hollow.difference(trimesh.boolean.union(bosses, engine="manifold"), engine="manifold")
# ouverture USB-C (paroi gauche) : la prise de la carte pend sous la carte (z 3,0 -> 6,2) ; passage du surmoulage de la fiche
PCB_T = 0.8
usb_z = HOLLOW - PCB_T - 1.6
usb = trimesh.creation.box(extents=[WALL * 3, 12.5, 7.0]); usb.apply_translation([0, D / 2, usb_z])
# dégagement au-dessus de la prise USB-C : ses pattes traversantes et ses plots dépassent sur la face plaquée au plancher
usb_relief = trimesh.creation.box(extents=[11.0, 14.0, 1.6]); usb_relief.apply_translation([2.0 + 5.5, D / 2, HOLLOW + 0.8 - 0.01])
body = box.difference(trimesh.boolean.union(cuts + [hollow, usb, usb_relief] + pilots, engine="manifold"), engine="manifold")

lid = trimesh.creation.box(extents=[W, D, 2.0]); lid.apply_translation([W / 2, D / 2, 1.0])
holes = [trimesh.creation.cylinder(radius=1.15, height=5, sections=20, transform=trimesh.transformations.translation_matrix([x, y, 1.0])) for x, y in boss_pos]
heads = [trimesh.creation.cylinder(radius=2.1, height=1.2, sections=24, transform=trimesh.transformations.translation_matrix([x, y, 0.6 - 0.01])) for x, y in boss_pos]
lid = lid.difference(trimesh.boolean.union(holes + heads, engine="manifold"), engine="manifold")
# tétons sous chaque spirale : plaquent la carte contre le plancher (hauteur = creux - épaisseur de carte)
pegs = [trimesh.creation.cylinder(radius=2.0, height=HOLLOW - PCB_T, sections=32,
        transform=trimesh.transformations.translation_matrix([s_["centre_bobine_mm"][0], s_["centre_bobine_mm"][1], 2.0 + (HOLLOW - PCB_T) / 2]))
        for s_ in slots]
lid = trimesh.boolean.union([lid] + pegs, engine="manifold")


def clean(m):
    """exporte/recharge en STL (float32) et ne garde la version nettoyée que si elle reste étanche"""
    import tempfile
    p = tempfile.mktemp(suffix=".stl"); m.export(p); r = trimesh.load(p)
    if r.is_watertight: return m
    for dec in (4, 3):
        c = m.copy(); c.vertices = np.round(c.vertices, dec); c.merge_vertices()
        c.update_faces(c.nondegenerate_faces()); c.remove_unreferenced_vertices(); trimesh.repair.fix_normals(c)
        c.export(p); r = trimesh.load(p)
        if r.is_watertight: return c
    return m


os.makedirs(OUT, exist_ok=True)
body, lid = clean(body), clean(lid)
body.export(f"{OUT}/boite_chargeur_corps.stl"); lid.export(f"{OUT}/boite_chargeur_fond.stl")
json.dump({"dimensions_mm": [round(W, 1), round(D, 1), round(H, 1)], "plancher_mm": FLOOR, "logements": slots},
          open(f"{OUT}/boite_chargeur.json", "w"), indent=1)
print("corps étanche", body.is_watertight, "| fond étanche", lid.is_watertight, "| dimensions", [round(W, 1), round(D, 1), round(H, 1)])
