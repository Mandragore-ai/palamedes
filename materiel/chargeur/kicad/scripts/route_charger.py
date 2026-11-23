"""Routeur 2 couches pour la carte du chargeur MCDice (grille 0,1 mm, chemin de coût minimal scikit-image).

Pile 3D : F.Cu / « couche via » / B.Cu. Passer par la couche via = poser une via (coût élevé, permis
seulement là où une via tient sur les deux faces). Chaque net est routé en arbre ; les obstacles sont le cuivre
des autres nets dilaté de (demi-largeur + garde). Les spirales sont des obstacles à part entière : leurs deux
amorces (via haute « a », piste basse « b ») sont des sous-nets distincts pour qu'aucune piste ne court-circuite
une spire. Les pastilles GND reçoivent une via vers le plan de masse.
usage : route_charger.py entree.kicad_pcb sortie.kicad_pcb
"""
import sys, math, json, time, os
import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

SRC, DST = sys.argv[1], sys.argv[2]
GEO = json.load(open(SRC.rsplit("/", 1)[0] + "/chargeur_geometrie.json"))
X0, Y0, DB = GEO["transfo"]["X0"], GEO["transfo"]["Y0"], GEO["transfo"]["DBOX"]
BX0, BY0, BX1, BY1 = GEO["contour"]
G = 0.05
NX, NY = int(round((BX1 - BX0) / G)) + 1, int(round((BY1 - BY0) / G)) + 1
CLR = 0.14
EDGE = 0.3
VIA_D, VIA_DR = 0.6, 0.3
VIA_COST = 25.0
LAYER_COST = (2.0, 1.0)          # F (plan de masse : on l'épargne), B
F, B = 0, 1
KL = {F: pcbnew.F_Cu, B: pcbnew.B_Cu}

board = pcbnew.LoadBoard(SRC)

# grille : cellule (i, j) -> x = BX0 + j*G, y(boîte) = BY0 + i*G ; KiCad Y = Y0 + DB - y
def k2b(X, Y): return X - X0, DB - (Y - Y0)
def b2ij(x, y): return int(round((y - BY0) / G)), int(round((x - BX0) / G))
def ij2b(i, j): return BX0 + j * G, BY0 + i * G
def b2k(x, y): return VECTOR2I(FromMM(float(X0 + x)), FromMM(float(Y0 + DB - y)))

yy, xx = np.mgrid[0:NY, 0:NX]
XB = BX0 + xx * G; YB = BY0 + yy * G

# ------------------------------------------------------------------ identifiants
ids = {}
def nid(name):
    if name not in ids: ids[name] = len(ids)
    return ids[name]

occ = [np.full((NY, NX), -1, np.int32) for _ in (F, B)]
pad_any = np.zeros((NY, NX), bool)            # toutes les pastilles CMS (pas de via dedans)


def window(x0, y0, x1, y1, m=0.0):
    i0, j0 = b2ij(x0 - m, y0 - m); i1, j1 = b2ij(x1 + m, y1 + m)
    i0, j0 = max(i0, 0), max(j0, 0); i1, j1 = min(i1 + 1, NY), min(j1 + 1, NX)
    return slice(i0, i1), slice(j0, j1)


def paint_capsule(arrs, val, a, b, r):
    (ax, ay), (bx_, by_) = a, b
    si, sj = window(min(ax, bx_), min(ay, by_), max(ax, bx_), max(ay, by_), r + G)
    px, py = XB[si, sj], YB[si, sj]
    dx, dy = bx_ - ax, by_ - ay; L2 = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1) if L2 > 0 else 0
    m = np.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= r
    for arr in arrs: arr[si, sj][m] = val
    return si, sj, m


def pad_mask(p):
    """cellules dont le centre est dans la pastille (forme exacte : rect / arrondi / cercle / ovale)"""
    sh = p.GetEffectiveShape(); bb = p.GetBoundingBox()
    x0, y1 = k2b(ToMM(bb.GetLeft()), ToMM(bb.GetTop())); x1, y0 = k2b(ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
    si, sj = window(x0, y0, x1, y1, G)
    m = np.zeros((si.stop - si.start, sj.stop - sj.start), bool)
    for a in range(m.shape[0]):
        for c in range(m.shape[1]):
            x, y = XB[si.start + a, sj.start + c], YB[si.start + a, sj.start + c]
            m[a, c] = sh.Collide(b2k(x, y), 0)
    return si, sj, m


pads = []                 # (ref, num, net, layers, cx, cy, (si, sj, m))
for fp in board.GetFootprints():
    for p in fp.Pads():
        netn = p.GetNetname() or f"__nc_{fp.GetReference()}_{p.GetNumber()}"
        tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        lays = [F, B] if tht else ([B] if p.IsOnLayer(pcbnew.B_Cu) else [F])
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH: netn = "__trou"
        if netn.startswith("COIL"): netn += "_a" if fp.GetReference().startswith("C") else "_b"
        si, sj, m = pad_mask(p)
        for l in lays: occ[l][si, sj][m] = nid(netn)
        if not tht: pad_any[si, sj] |= m
        cx, cy = k2b(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
        pads.append((fp.GetReference(), p.GetNumber(), netn, lays, cx, cy, (si, sj, m)))

# spirales et amorces (déjà présentes sur la carte)
coil_centres = {int(k): tuple(v["centre"]) for k, v in GEO["bobines"].items()}
for t in board.GetTracks():
    n = t.GetNetname()
    if t.GetClass() == "PCB_VIA":
        x, y = k2b(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)); r = ToMM(t.GetWidth()) / 2
        if n.startswith("COIL"):
            name = (n + "_a") if r > 0.28 else (n + "_spirale")
        else: name = n
        paint_capsule(occ, nid(name), (x, y), (x, y), r)
    else:
        a = k2b(ToMM(t.GetStart().x), ToMM(t.GetStart().y)); b = k2b(ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
        w = ToMM(t.GetWidth()); l = F if t.GetLayer() == pcbnew.F_Cu else B
        name = n
        if n.startswith("COIL"):
            name = n + ("_spirale" if w < 0.25 else ("_a" if l == F else "_b"))
        paint_capsule([occ[l]], nid(name), a, b, w / 2)

# distance au bord (contour à encoches)
inside = (XB >= BX0) & (XB <= BX1) & (YB >= BY0) & (YB <= BY1)
for (ex, ey) in GEO["encoches"]:
    inside &= np.hypot(XB - ex, YB - ey) > GEO["r_encoche"]
dist_edge = ndimage.distance_transform_edt(inside) * G
coil_disc = np.zeros((NY, NX), bool)
for (cx, cy) in coil_centres.values(): coil_disc |= np.hypot(XB - cx, YB - cy) < 5.4
pad_novia = ndimage.distance_transform_edt(~pad_any) * G < VIA_D / 2 + 0.1
# sous le microcontrôleur, la face du dessus reste au plan de masse (les vias GND de ses broches y aboutissent)
mcu = [fp for fp in board.GetFootprints() if fp.GetReference() == "U3"][0]
mx, my = k2b(ToMM(mcu.GetPosition().x), ToMM(mcu.GetPosition().y))
F_RESERVE = (np.abs(XB - mx) < 3.2) & (np.abs(YB - my) < 3.2)
trk = [np.full((NY, NX), -1, np.int32) for _ in (F, B)]      # cuivre posé par le routeur
via_mask = np.zeros((NY, NX), bool); via_net = np.full((NY, NX), -1, np.int32)
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        x, y = k2b(ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)); i, j = b2ij(x, y)
        via_mask[i, j] = True; via_net[i, j] = -2

# ------------------------------------------------------------------ amorces réservées
# chaque pastille reçoit un couloir de sortie (dans l'axe, vers l'extérieur de son composant) réservé à son net :
# aucun autre net ne peut l'enfermer. Microcontrôleur : longueurs alternées pour pouvoir y poser des vias.
fp_centre = {fp.GetReference(): k2b(ToMM(fp.GetPosition().x), ToMM(fp.GetPosition().y)) for fp in board.GetFootprints()}
reserve = []
for (ref, num, netn, lays, cx, cy, msk) in pads:
    if netn.startswith("__") or netn == "GND" or netn.startswith("COIL") or lays != [B]: continue
    fx, fy = fp_centre[ref]; dx, dy = cx - fx, cy - fy
    if abs(dx) < 1e-6 and abs(dy) < 1e-6: continue
    ux, uy = (math.copysign(1, dx), 0.0) if abs(dx) >= abs(dy) else (0.0, math.copysign(1, dy))
    if ref == "U3": L = 1.6 if int(num) % 2 else 2.6
    elif ref == "J1":
        rang = sorted(round(q[5], 2) for q in pads if q[0] == "J1" and q[3] == [B])
        L = 1.2 if rang.index(round(cy, 2)) % 2 else 2.4
    else: L = 0.9
    # point de départ : bord de la pastille dans la direction choisie
    si, sj, m = msk; ii, jj = np.nonzero(m)
    xs = BX0 + (jj + sj.start) * G; ys = BY0 + (ii + si.start) * G
    edge_d = np.max(xs * ux + ys * uy) - (cx * ux + cy * uy)
    a = (cx + ux * edge_d, cy + uy * edge_d); b = (a[0] + ux * L, a[1] + uy * L)
    me = nid(netn)
    si2, sj2 = window(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), 0.2)
    px, py = XB[si2, sj2], YB[si2, sj2]
    ddx, ddy = b[0] - a[0], b[1] - a[1]; L2 = ddx * ddx + ddy * ddy
    t = np.clip(((px - a[0]) * ddx + (py - a[1]) * ddy) / L2, 0, 1)
    mm = np.hypot(px - (a[0] + t * ddx), py - (a[1] + t * ddy)) <= 0.1
    sub = occ[B][si2, sj2]
    mm &= (sub == -1)
    sub[mm] = me
    reserve.append((me, si2, sj2, mm))

# ------------------------------------------------------------------ nets à router
def pads_of(net):
    return [p for p in pads if p[2] == net]

WIDTH = {"SW": 0.8, "VBUS": 0.6, "GATE_H": 0.4, "GATE_L": 0.4}
for k in coil_centres: WIDTH[f"COIL{k}_a"] = 0.6; WIDTH[f"COIL{k}_b"] = 0.6; WIDTH[f"S{k}"] = 0.5

order = ["GATE_H", "GATE_L", "VBUS", "SW"] + [f"COIL{k}_{s}" for k in coil_centres for s in "ab"] + \
        [f"S{k}" for k in coil_centres] + ["3V3", "XIN", "XOUT", "USB_DM", "USB_DP"] + [f"PK{k}" for k in coil_centres] + \
        [f"EN{k}" for k in coil_centres] + ["PWM_H", "PWM_L", "NRST", "BOOT0", "SWDIO", "SWCLK", "LED", "CC1", "CC2", "LED_A"]


def terminals(net):
    """liste de terminaux : (couches, cellules (i,j) cibles, centre)"""
    out = []
    if net.startswith("COIL"):
        base, s = net.split("_"); k = int(base[4:])
        for p in pads_of(net):
            out.append((p[3], p[6], (p[4], p[5])))
        g = GEO["bobines"][str(k)]
        x, y = g["sortie_a"] if s == "a" else g["sortie_b"]
        r = 0.25 if s == "a" else 0.12
        si, sj = window(x, y, x, y, r + G)
        m = np.hypot(XB[si, sj] - x, YB[si, sj] - y) <= r
        out.append(([F, B] if s == "a" else [B], (si, sj, m), (x, y)))
        return out
    for p in pads_of(net): out.append((p[3], p[6], (p[4], p[5])))
    return out


tracks_out, vias_out, fails = [], [], []


def cost_volume(net, w):
    me = nid(net)
    vol = np.full((3, NY, NX), np.inf)
    free = []
    for l in (F, B):
        other = (occ[l] != -1) & (occ[l] != me)
        d = ndimage.distance_transform_edt(~other) * G
        ok = (d >= w / 2 + CLR + G) & (dist_edge >= w / 2 + EDGE + G / 2) & ~coil_disc
        free.append(d)
        vol[0 if l == F else 2][ok] = LAYER_COST[l]
    vok = (free[0] >= VIA_D / 2 + CLR + G) & (free[1] >= VIA_D / 2 + CLR + G) & \
          (dist_edge >= VIA_D / 2 + EDGE + G / 2) & ~pad_novia & ~coil_disc
    vok &= ndimage.distance_transform_edt(~via_mask) * G >= 0.65
    vol[1][vok] = VIA_COST
    vol[1][via_mask & (via_net == me)] = 1.0        # changer de couche sur une via existante du net
    # le cuivre déjà posé du net lui-même est bon marché à réemprunter (arbre), garde respectée
    for l in (F, B):
        z = 0 if l == F else 2
        own = (occ[l] == me) & np.isfinite(vol[z])
        vol[z][own] = 0.5
    return vol


def emit(path, net, w):
    """chemin [(z,i,j)] -> segments + vias ; marque le cuivre"""
    me = nid(net); real = net.split("_")[0] if net.startswith("COIL") else net
    pts = [(z, i, j) for (z, i, j) in path]
    # vias : passages par z = 1
    k = 0; runs = []; cur = []; prev_z = None; vstart = None
    for (z, i, j) in pts:
        if z == 1:
            if cur: runs.append(cur); cur = []
            if prev_z != 1:
                vstart = (i, j)
                if not via_mask[i, j]:
                    x, y = ij2b(i, j)
                    vias_out.append((x, y, real)); paint_capsule(occ, me, (x, y), (x, y), VIA_D / 2)
                    paint_capsule(trk, me, (x, y), (x, y), VIA_D / 2)
                    via_mask[i, j] = True; via_net[i, j] = me
            else:
                # déplacement dans la « couche via » : on relie par une courte piste sur les deux faces
                a, b = ij2b(*vstart), ij2b(i, j)
                for l in (F, B): tracks_out.append((a, b, w, l, real)); paint_capsule([occ[l]], me, a, b, w / 2)
                vstart = (i, j)
        else:
            if cur and cur[-1][0] != z: runs.append(cur); cur = []
            if prev_z == 1 and vstart is not None and not cur:
                cur.append((z, vstart[0], vstart[1]))
            cur.append((z, i, j))
        prev_z = z
    if cur: runs.append(cur)
    for run in runs:
        l = F if run[0][0] == 0 else B
        # simplification : on garde les points où la direction change
        keep = [run[0]]
        for a, b, c in zip(run, run[1:], run[2:]):
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]): keep.append(b)
        if len(run) > 1: keep.append(run[-1])
        for a, b in zip(keep, keep[1:]):
            pa, pb = ij2b(a[1], a[2]), ij2b(b[1], b[2])
            tracks_out.append((pa, pb, w, l, real)); paint_capsule([occ[l]], me, pa, pb, w / 2)
            paint_capsule([trk[l]], me, pa, pb, w / 2)
        if len(keep) == 1:   # point isolé (arrivée sur une via) : rien à tracer
            pass


OFFS = [(dz, di, dj) for dz in (-1, 0, 1) for di in (-1, 0, 1) for dj in (-1, 0, 1)
        if (dz == 0 and (di, dj) != (0, 0)) or (dz != 0 and di == 0 and dj == 0)]


def route_net(net, w, only=None):
    terms = terminals(net)
    if len(terms) < 2: return True
    vol = cost_volume(net, w)
    # cellules cibles : forcer franchissables (le cuivre du terminal lui-même)
    def cells(t):
        lays, (si, sj, m), c = t
        out = []
        ci, cj = b2ij(*c)
        for l in lays:
            z = 0 if l == F else 2
            ii, jj = np.nonzero(m)
            for a, b in zip(ii + si.start, jj + sj.start):
                if np.isfinite(vol[z, a, b]) or (a, b) == (ci, cj): out.append((z, a, b))
        return out
    if only is None:
        tree = cells(terms[0]); todo = list(range(1, len(terms)))
    else:
        todo = [i for i, t in enumerate(terms) if t[2] in only]
        tree = [c for i, t in enumerate(terms) if i not in todo for c in cells(t)]
        me = nid(net)
        for l in (F, B):
            ii, jj = np.nonzero(trk[l] == me); z = 0 if l == F else 2
            tree += [(z, a, b) for a, b in zip(ii, jj) if np.isfinite(vol[z, a, b])]
    for c in tree: vol[c] = min(vol[c], 0.5) if np.isfinite(vol[c]) else 0.5
    ok_all = True
    while todo:
        # terminal le plus proche de l'arbre
        tc = np.array([[ij2b(c[1], c[2])[0], ij2b(c[1], c[2])[1]] for c in tree[::max(1, len(tree) // 400)]])
        best = min(todo, key=lambda t: np.min(np.hypot(tc[:, 0] - terms[t][2][0], tc[:, 1] - terms[t][2][1])))
        tgt = cells(terms[best])
        v2 = vol.copy()
        for c in tgt: v2[c] = 0.5
        mcp = MCP_Geometric(v2, offsets=OFFS, fully_connected=False)
        costs, tb = mcp.find_costs(tree, tgt, find_all_ends=False)
        reached = [c for c in tgt if np.isfinite(costs[c])]
        if not reached:
            nf = int(np.isfinite(costs).sum())
            print(f"   {net}: arbre depuis {terms[0][2]} -> {nf} cellules atteignables ; cible {terms[best][2]}", flush=True)
            fails.append((net, terms[best][2])); ok_all = False; todo.remove(best); continue
        end = min(reached, key=lambda c: costs[c])
        path = mcp.traceback(end)
        n0 = len(tracks_out); emit(path, net, w)
        if os.environ.get("DEBUG"): print("     chemin", len(path), "segments", len(tracks_out) - n0, path[:3], path[-3:])
        newc = [tuple(p) for p in path] + tgt
        tree += newc
        for c in newc:
            if np.isfinite(vol[c]): vol[c] = 0.5
        # le cuivre posé reste franchissable pour la suite du même net
        todo.remove(best)
    return ok_all


# ------------------------------------------------------------------ vias de masse
if not os.environ.get("JOIN"):
    gnd = nid("GND"); vol = None; t0 = time.time()
    gnd_pads = [p for p in pads if p[2] == "GND" and p[3] == [B]]
    other = (occ[F] != -1) & (occ[F] != gnd); dF = ndimage.distance_transform_edt(~other) * G
    other = (occ[B] != -1) & (occ[B] != gnd); dB = ndimage.distance_transform_edt(~other) * G
    gfail = []
    for (ref, num, n, lays, cx, cy, (si, sj, m)) in gnd_pads:
        # via la plus proche dans un rayon de 2 mm, joignable en ligne droite sur B
        best = None
        i0, j0 = b2ij(cx, cy)
        for rr in np.arange(0.6, 2.6, 0.1):
            for a in np.arange(0, 2 * math.pi, math.pi / 16):
                x, y = cx + rr * math.cos(a), cy + rr * math.sin(a); i, j = b2ij(x, y)
                if not (0 <= i < NY and 0 <= j < NX): continue
                if dF[i, j] < VIA_D / 2 + CLR + G or dB[i, j] < VIA_D / 2 + CLR + G: continue
                if dist_edge[i, j] < VIA_D / 2 + EDGE or pad_novia[i, j] or coil_disc[i, j]: continue
                # couloir libre sur B entre la pastille et la via (largeur 0,3)
                nseg = int(rr / G) + 1; good = True
                for s in range(nseg + 1):
                    px, py = cx + (x - cx) * s / nseg, cy + (y - cy) * s / nseg; pi, pj = b2ij(px, py)
                    if dB[pi, pj] < 0.15 + CLR + G: good = False; break
                if good: best = (x, y); break
            if best: break
        if not best: gfail.append(ref + "." + num); continue
        x, y = best
        tracks_out.append(((cx, cy), (x, y), 0.3, B, "GND")); vias_out.append((x, y, "GND"))
        vi, vj = b2ij(x, y); via_mask[vi, vj] = True; via_net[vi, vj] = gnd
        paint_capsule([occ[B]], gnd, (cx, cy), (x, y), 0.15); paint_capsule(occ, gnd, (x, y), (x, y), VIA_D / 2)
        other = (occ[F] != -1) & (occ[F] != gnd)
        for l, d in ((F, None), (B, None)): pass
        dF = ndimage.distance_transform_edt(~((occ[F] != -1) & (occ[F] != gnd))) * G
        dB = ndimage.distance_transform_edt(~((occ[B] != -1) & (occ[B] != gnd))) * G
    print("vias GND manquantes :", gfail)

if os.environ.get("JOIN"):
    groupes = json.load(open(os.environ["JOIN"]))
    me = nid("GND"); w = 0.3
    vol = np.full((3, NY, NX), np.inf)
    dd = []
    for l in (F, B):
        other = (occ[l] != -1) & (occ[l] != me)
        d = ndimage.distance_transform_edt(~other) * G; dd.append(d)
        vol[0 if l == F else 2][(d >= w / 2 + CLR + G) & (dist_edge >= w / 2 + EDGE + G) & ~coil_disc] = LAYER_COST[l]
    vok = (dd[0] >= VIA_D / 2 + CLR + G) & (dd[1] >= VIA_D / 2 + CLR + G) & (dist_edge >= VIA_D / 2 + EDGE + G) & ~pad_novia & ~coil_disc
    vok &= ndimage.distance_transform_edt(~via_mask) * G >= 0.65
    vol[1][vok] = VIA_COST
    res = []
    for g in groupes:
        starts, ends = [], []
        for (X, Y) in g["graines"]:
            i, j = b2ij(*k2b(X, Y))
            for z in (0, 2):
                if np.isfinite(vol[z, i, j]): starts.append((z, i, j))
        for (X, Y) in g["principal"]:
            i, j = b2ij(*k2b(X, Y))
            for z in (0, 2): ends.append((z, i, j)); vol[z, i, j] = 0.5
        if not starts: print("pas de départ libre", g["graines"][:2]); continue
        mcp = MCP_Geometric(vol, offsets=OFFS, fully_connected=False)
        costs, tb = mcp.find_costs(starts, ends, find_all_ends=False)
        ok = [e for e in ends if np.isfinite(costs[e])]
        if not ok: print("groupe non relié", g["graines"][:2]); continue
        e = min(ok, key=lambda c: costs[c]); path = mcp.traceback(e)
        emit(path, "GND", w); print("groupe relié, longueur", len(path))
    for (a, b_, ww, l, n) in tracks_out:
        if a == b_: continue
        t = pcbnew.PCB_TRACK(board); t.SetStart(b2k(*a)); t.SetEnd(b2k(*b_)); t.SetWidth(FromMM(ww))
        t.SetLayer(KL[l]); t.SetNet(board.FindNet(n)); board.Add(t)
    for (x, y, n) in vias_out:
        v = pcbnew.PCB_VIA(board); v.SetPosition(b2k(x, y)); v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_DR))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(board.FindNet(n)); board.Add(v)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones()); board.Save(DST); sys.exit(0)

import os
if os.environ.get("ORDER"): order = os.environ["ORDER"].split(",")
PRIORITE = ["PK2", "EN1", "USB_DM", "USB_DP"]          # nets difficiles routés d'abord (issus des essais précédents)
if os.environ.get("PRIORITE"): PRIORITE = os.environ["PRIORITE"].split(",")
order = [n for n in PRIORITE if n in order] + [n for n in order if n not in PRIORITE]
t0 = time.time()
for net in order:
    if not terminals(net): continue
    w = WIDTH.get(net, 0.2)
    nfail = len(fails)
    ok = route_net(net, w)
    if not ok and w > 0.3:
        # nouvel essai plus fin pour les seuls terminaux manqués, depuis le cuivre déjà posé
        missed = [f[1] for f in fails[nfail:]]; del fails[nfail:]
        ok = route_net(net, 0.3, only=missed)
    print(f"{net:8s} w={w} {'ok' if ok else 'ÉCHEC'}  ({time.time()-t0:.0f} s)", flush=True)

# ------------------------------------------------------------------ écriture
nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()} if False else None
def kn(name): return board.FindNet(name)
for (a, b, w, l, n) in tracks_out:
    if a == b: continue
    t = pcbnew.PCB_TRACK(board); t.SetStart(b2k(*a)); t.SetEnd(b2k(*b)); t.SetWidth(FromMM(w))
    t.SetLayer(KL[l]); t.SetNet(kn(n)); board.Add(t)
for (x, y, n) in vias_out:
    v = pcbnew.PCB_VIA(board); v.SetPosition(b2k(x, y)); v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_DR))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(kn(n)); board.Add(v)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(DST)
print("pistes", len(tracks_out), "vias", len(vias_out), "échecs", fails, "GND", gfail, f"{time.time()-t0:.0f} s")
