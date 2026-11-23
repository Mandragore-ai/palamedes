"""Routeur maze (A*) minimal pour la carte cœur du dé.

Grille 0,05 mm, couches de routage F.Cu / In2.Cu / B.Cu (In1.Cu = plan de masse).
Chaque net est routé en arbre (pastille -> arbre existant). Les pastilles GND reçoivent
une via vers le plan In1. Les obstacles (cuivre des autres nets, zones interdites, bord)
sont dilatés de (clairance + demi-largeur) par transformée de distance.
"""
import heapq, math, sys
import numpy as np
from scipy import ndimage
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

SRC = sys.argv[1]; DST = sys.argv[2]
CX = CY = 100.0
R_BOARD = 8.0
G = 0.05                       # pas de grille (mm)
N = int(round(2 * R_BOARD / G)) + 1
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
LNAME = {pcbnew.F_Cu: "F", pcbnew.In2_Cu: "In2", pcbnew.B_Cu: "B"}
CLR = 0.14          # règle DRC 0,10 mm (JLC 4 couches : 0,09 mm) + marge de discrétisation
VIA_D, VIA_DRILL = 0.45, 0.25
W_SIG, W_PWR = 0.127, 0.25
POWER = {"GND", "VBAT", "VDD", "VRECT", "COIL1", "RX_X"}
ANT_Y = -2.8
MOD_YC = -1.6
VIA_COST = 5.0
LAYER_MUL = [1.6, 1.0, 1.6]   # F, In2, B : les longues pistes vont sur In2

board = pcbnew.LoadBoard(SRC)


def to_ij(x, y):  # coordonnées locales mm -> indices
    return int(round((y + R_BOARD) / G)), int(round((x + R_BOARD) / G))


def to_xy(i, j):
    return j * G - R_BOARD, i * G - R_BOARD


yy, xx = np.mgrid[0:N, 0:N]
XC = xx * G - R_BOARD; YC = yy * G - R_BOARD
RR = np.hypot(XC, YC)

# ------------------------------------------------------------------ cuivre existant
# occupation : dict couche -> tableau d'identifiants de net (-1 libre)
net_names = {}
def nid(name):
    if name not in net_names: net_names[name] = len(net_names)
    return net_names[name]

occ = {l: np.full((N, N), -1, np.int32) for l in LAYERS}
pads = []   # (ref, num, net, layer, x, y, mask)
for fp in board.GetFootprints():
    for p in fp.Pads():
        netn = p.GetNetname()
        if not netn: netn = f"__nc_{fp.GetReference()}_{p.GetNumber()}"
        layer = pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
        bb = p.GetBoundingBox()
        x0, x1 = ToMM(bb.GetLeft()) - CX, ToMM(bb.GetRight()) - CX
        y0, y1 = ToMM(bb.GetTop()) - CY, ToMM(bb.GetBottom()) - CY
        if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
            r = ToMM(p.GetSize().x) / 2; cx_, cy_ = (x0 + x1) / 2, (y0 + y1) / 2
            m = np.hypot(XC - cx_, YC - cy_) <= r + G / 2
        else:
            e = G / 2   # le bord réel d'une pastille tombe entre deux cellules : on gonfle d'une demi-cellule
            m = (XC >= x0 - e) & (XC <= x1 + e) & (YC >= y0 - e) & (YC <= y1 + e)
        occ[layer][m] = nid(netn)
        px, py = ToMM(p.GetPosition().x) - CX, ToMM(p.GetPosition().y) - CY
        pads.append((fp.GetReference(), p.GetNumber(), netn, layer, px, py, m))

pad_union = np.zeros((N, N), bool)
for p in pads: pad_union |= p[6]
PAD_NOVIA = ndimage.distance_transform_edt(~pad_union) * G <= (VIA_D / 2 + 0.05)

# zones interdites
forbid = {l: np.zeros((N, N), bool) for l in LAYERS}
ytop_mod = MOD_YC - 4.4
for l in LAYERS:
    forbid[l] |= (YC < ytop_mod)
    forbid[l] |= (np.abs(XC) < 3.45) & (YC < MOD_YC - 1.2)
forbid[pcbnew.F_Cu] |= (np.abs(XC) < 3.45) & (YC > MOD_YC - 4.4) & (YC < MOD_YC + 4.4)
LGA_ZONE = (XC > -1.7 - 0.65) & (XC < 1.9 + 0.65) & (YC > MOD_YC - 0.92 - 0.65) & (YC < MOD_YC + 3.88 + 0.65)
via_forbid = forbid[pcbnew.In2_Cu] | forbid[pcbnew.B_Cu] | LGA_ZONE   # vias « tented » permises sous le module hors grille LGA
via_forbid |= (YC < ANT_Y) & (np.abs(XC) < 4.75)   # vias seulement sur les côtés de la bande antenne
FORBID_D = {l: ndimage.distance_transform_edt(~forbid[l]) * G for l in LAYERS}
via_forbid = (ndimage.distance_transform_edt(~via_forbid) * G <= VIA_D / 2 + 0.04)
GND_VIA_FORBID = via_forbid | (YC < ANT_Y + VIA_D / 2 + 0.1)   # pas de plan de masse au-dessus

VIA_HOLES = []
tracks = []  # (net, layer, [(x,y)...], width)
vias = []    # (net, x, y)


def blocked_mask(layer, net, half):
    """cellules interdites pour le centre d'une piste de demi-largeur half du net donné"""
    other = (occ[layer] >= 0) & (occ[layer] != net_names[net])
    d = ndimage.distance_transform_edt(~other) * G
    m = d <= (CLR + half)
    m |= FORBID_D[layer] <= half + 0.08
    m |= RR > (R_BOARD - 0.25 - half)
    return m


def via_ok_mask(net):
    half = VIA_D / 2
    m = np.ones((N, N), bool)
    for l in LAYERS:
        m &= ~blocked_mask(l, net, half)
    m &= ~(GND_VIA_FORBID if net == "GND" else via_forbid)
    m &= RR < (R_BOARD - 0.25 - half)
    if VIA_HOLES:
        hx = np.zeros((N, N), bool)
        for (vx, vy) in VIA_HOLES: hx[to_ij(vx, vy)] = True
        m &= ndimage.distance_transform_edt(~hx) * G > 0.55
    m &= ~PAD_NOVIA
    return m


def paint(layer, pts, half, net):
    """rasterise une piste (polyligne) dans occ"""
    k = net_names[net]
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = max(math.hypot(x1 - x0, y1 - y0), 1e-9)
        n = int(L / (G / 2)) + 1
        for t in np.linspace(0, 1, n + 1):
            x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t
            i, j = to_ij(x, y); r = int(math.ceil(half / G)) + 1
            sl = (slice(max(i - r, 0), i + r + 1), slice(max(j - r, 0), j + r + 1))
            sub = np.hypot(XC[sl] - x, YC[sl] - y) <= half
            occ[layer][sl][sub] = k


def paint_via(x, y, net):
    for l in LAYERS:
        paint(l, [(x, y), (x, y)], VIA_D / 2, net)


NB = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]


def astar(net, half, starts, targets, allow_via=True, via_targets=False):
    """starts: liste (li, i, j) ; targets: tableau bool par couche (dict li->mask).
    via_targets : la cible est « une via posable » (pour GND)."""
    blk = [blocked_mask(l, net, half) for l in LAYERS]
    vok = via_ok_mask(net) if (allow_via or via_targets) else None
    # les cellules de départ/arrivée propres au net restent accessibles
    tgt = targets
    openh = []; g = {}; came = {}
    for s in starts:
        g[s] = 0.0; heapq.heappush(openh, (0.0, s))
    # heuristique : distance au plus proche point cible (approx. via distance transform)
    hmap = {}
    for li in range(3):
        if via_targets:
            t = vok
        else:
            t = tgt.get(li, np.zeros((N, N), bool))
        if t.any():
            hmap[li] = ndimage.distance_transform_edt(~t)
        else:
            hmap[li] = np.full((N, N), 1e4)
    h_all = np.minimum.reduce([hmap[li] + (0 if (li in tgt and tgt[li].any()) else VIA_COST) for li in range(3)]) if not via_targets else hmap[0]
    it = 0
    while openh:
        f, cur = heapq.heappop(openh)
        li, i, j = cur
        gc = g[cur]
        if f - h_all[i, j] > gc + 1e-6: continue
        it += 1
        if it > 2_000_000: return None
        if via_targets:
            if vok[i, j] and gc > 0: return reconstruct(came, cur) + [("VIA", li, i, j)]
        elif li in tgt and tgt[li][i, j]:
            return reconstruct(came, cur)
        for di, dj, c in NB:
            ni, nj = i + di, j + dj
            if not (0 <= ni < N and 0 <= nj < N): continue
            if blk[li][ni, nj] and not (li in tgt and tgt[li][ni, nj]): continue
            nxt = (li, ni, nj); ng = gc + c * LAYER_MUL[li]
            if ng < g.get(nxt, 1e18):
                g[nxt] = ng; came[nxt] = cur; heapq.heappush(openh, (ng + h_all[ni, nj], nxt))
        if allow_via and vok[i, j]:
            for lj in range(3):
                if lj == li: continue
                if blk[lj][i, j] and not (lj in tgt and tgt[lj][i, j]): continue
                nxt = (lj, i, j); ng = gc + VIA_COST
                if ng < g.get(nxt, 1e18):
                    g[nxt] = ng; came[nxt] = cur; heapq.heappush(openh, (ng + h_all[i, j], nxt))
    return None


def reconstruct(came, cur):
    path = [cur]
    while cur in came:
        cur = came[cur]; path.append(cur)
    return path[::-1]


def commit(net, half, path, tree=None):
    """transforme un chemin de cellules en pistes + vias ; met à jour l'arbre connecté"""
    segs = []; curl = None; pts = []
    vias_here = []
    for node in path:
        if node[0] == "VIA":
            _, li, i, j = node; x, y = to_xy(i, j); vias_here.append((x, y)); continue
        li, i, j = node
        x, y = to_xy(i, j)
        if curl is None: curl = li
        if li != curl:
            if len(pts) > 1: segs.append((curl, pts))
            vias_here.append(pts[-1] if pts else (x, y))
            pts = [(x, y)]; curl = li
        else:
            pts.append((x, y))
    if len(pts) > 1: segs.append((curl, pts))
    for li, pts in segs:
        pts = simplify(pts)
        tracks.append((net, LAYERS[li], pts, 2 * half)); paint(LAYERS[li], pts, half, net)
        if tree is not None:
            for (x, y) in pts_dense(pts): tree[li][to_ij(x, y)] = True
    for (x, y) in vias_here:
        if any(abs(x - a) < 1e-6 and abs(y - b) < 1e-6 for (n_, a, b) in vias): continue
        vias.append((net, x, y)); paint_via(x, y, net); VIA_HOLES.append((x, y))
        if tree is not None:
            for li in range(3): tree[li][to_ij(x, y)] = True


def pts_dense(pts):
    out = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        n = int(math.hypot(x1 - x0, y1 - y0) / (G / 2)) + 1
        out += [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in np.linspace(0, 1, n + 1)]
    return out or pts


def simplify(pts):
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[k], pts[k + 1]
        d1 = (round((b[0] - a[0]) / G), round((b[1] - a[1]) / G)); d2 = (round((c[0] - b[0]) / G), round((c[1] - b[1]) / G))
        if d1[0] * d2[1] - d1[1] * d2[0] == 0 and d1[0] * d2[0] + d1[1] * d2[1] > 0:
            continue
        out.append(b)
    out.append(pts[-1])
    return out


def pad_cells(p):
    ref, num, netn, layer, x, y, m = p
    return LAYERS.index(layer), m


# ------------------------------------------------------------------ routage
by_net = {}
for p in pads:
    if p[2].startswith("__nc"): continue
    by_net.setdefault(p[2], []).append(p)
OCC0 = {l: occ[l].copy() for l in LAYERS}


def route_all(order, verbose=False):
    global tracks, vias
    tracks, vias = [], []
    for l in LAYERS: occ[l][:] = OCC0[l]
    failed = []
    for net in order:
        pl = by_net.get(net, [])
        if len(pl) < 2: continue
        half = (W_PWR if net in POWER else W_SIG) / 2
        pl = sorted(pl, key=lambda p: math.hypot(p[4], p[5]))
        tree = {li: np.zeros((N, N), bool) for li in range(3)}
        li0, m0 = pad_cells(pl[0]); tree[li0] |= m0
        rest = pl[1:]
        while rest:
            allt = np.logical_or.reduce([tree[k] for k in range(3)])
            ys, xs = np.nonzero(allt)
            rest.sort(key=lambda p: np.min(np.hypot(XC[ys, xs] - p[4], YC[ys, xs] - p[5])))
            p = rest.pop(0)
            li, m = pad_cells(p)
            i, j = to_ij(p[4], p[5])
            path = astar(net, half, [(li, i, j)], tree)
            w = half
            if path is None and half > W_SIG / 2:
                path = astar(net, W_SIG / 2, [(li, i, j)], tree); w = W_SIG / 2
            if path is None:
                failed.append(net); tree[li] |= m
                if verbose: print("ÉCHEC", net, p[0], p[1])
                continue
            commit(net, w, path, tree)
            tree[li] |= m
    gnd_fail = []
    for p in by_net.get("GND", []):
        li, m = pad_cells(p)
        i, j = to_ij(p[4], p[5])
        path = astar("GND", W_PWR / 2, [(li, i, j)], {}, allow_via=False, via_targets=True)
        if path is None:
            path = astar("GND", W_SIG / 2, [(li, i, j)], {}, allow_via=False, via_targets=True)
        if path is None:
            gnd_fail.append((p[0], p[1])); continue
        commit("GND", W_PWR / 2, path)
    return failed, gnd_fail


ORDER = ["SDA", "SCL", "ACC_INT", "SWDIO", "SWCLK", "LED_R", "VDD", "LED_G", "LED_B", "LED_RK", "LED_GK", "LED_BK",
         "VBAT", "CHRG", "CAP_G1", "CAP_G2", "CAP_G3", "CAP_G4",
         "VRECT", "COIL1", "RX_X", "PROG"]
import random
random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
best = None
order = list(ORDER)
NTRY = int(sys.argv[4]) if len(sys.argv) > 4 else 40
for attempt in range(NTRY):
    failed, gf = route_all(order)
    score = len(failed) * 10 + len(gf)
    if best is None or score < best[0]:
        best = (score, list(order), [t for t in tracks], [v for v in vias], failed, gf)
        print(f"essai {attempt}: score {score} échecs {sorted(set(failed))} gnd {len(gf)}", flush=True)
    if not failed and len(gf) <= 2: break
    # nouvel ordre : on part du meilleur, échecs devant + petite permutation aléatoire
    base = list(best[1]); fs = [n for n in base if n in best[4]]
    order = fs + [n for n in base if n not in best[4]]
    for _ in range(3):
        a, b = random.randrange(len(order)), random.randrange(len(order))
        order[a], order[b] = order[b], order[a]
score, order, tracks, vias, failed, gf = best
print("retenu :", score, "ordre", order)

# ------------------------------------------------------------------ écriture
netinfo = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()} if hasattr(board.GetNetInfo(), "NetsByName") else {}
def getnet(name):
    return board.FindNet(name)

for (net, layer, pts, w) in tracks:
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(CX + x0), FromMM(CY + y0))); t.SetEnd(VECTOR2I(FromMM(CX + x1), FromMM(CY + y1)))
        t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(getnet(net)); board.Add(t)
for (net, x, y) in vias:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(VECTOR2I(FromMM(CX + x), FromMM(CY + y))); v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(getnet(net)); board.Add(v)

filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
board.Save(DST)
print("pistes", len(tracks), "vias", len(vias), "échecs", failed, "gnd", gf)
