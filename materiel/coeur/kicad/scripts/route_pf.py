"""Routage par négociation de congestion (PathFinder) — réutilise la préparation de route_core.py.
usage : route_pf.py entree.kicad_pcb sortie.kicad_pcb [iterations]
"""
import sys, math, heapq
import numpy as np
from scipy import ndimage

SRC, DST = sys.argv[1], sys.argv[2]
ITERS = int(sys.argv[3]) if len(sys.argv) > 3 else 40
_src = open(__file__.replace("route_pf.py", "route_core.py")).read()
_cut = _src.find("# ------------------------------------------------------------------ routage")
sys.argv = [sys.argv[0], SRC, DST]
exec(_src[:_cut])          # grille, pastilles, zones interdites, fonctions utilitaires

by_net = {}
for p in pads:
    if p[2].startswith("__nc"): continue
    by_net.setdefault(p[2], []).append(p)
NETS = [n for n in by_net if n != "GND" and len(by_net[n]) >= 2]
HALF = {n: (W_PWR if n in POWER else W_SIG) / 2 for n in NETS}

# blocages durs : pastilles des autres nets (dilatées) + interdits + bord
pad_occ = {l: OCC for l, OCC in occ.items()}
def hard_block(layer, net, half):
    other = (pad_occ[layer] >= 0) & (pad_occ[layer] != net_names[net])
    d = ndimage.distance_transform_edt(~other) * G
    m = (d <= CLR + half) | (FORBID_D[layer] <= half + 0.08) | (RR > R_BOARD - 0.25 - half)
    return m

HB = {(n, l): hard_block(l, n, HALF[n]) for n in NETS for l in LAYERS}
HBV = {}
for n in NETS:
    m = np.ones((N, N), bool)
    for l in LAYERS: m &= ~hard_block(l, n, VIA_D / 2)
    HBV[n] = m & ~via_forbid & ~PAD_NOVIA & (RR < R_BOARD - 0.25 - VIA_D / 2)

hist = {l: np.zeros((N, N)) for l in LAYERS}
copper = {}      # net -> {layer: bool mask}  (cuivre routé, pistes + vias)
routes = {}      # net -> (tracks, vias)


def raster_track(mask, pts, half):
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = max(math.hypot(x1 - x0, y1 - y0), 1e-9); n = int(L / (G / 2)) + 1
        for t in np.linspace(0, 1, n + 1):
            x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t
            i, j = to_ij(x, y); r = int(math.ceil(half / G)) + 1
            sl = (slice(max(i - r, 0), i + r + 1), slice(max(j - r, 0), j + r + 1))
            mask[sl] |= np.hypot(XC[sl] - x, YC[sl] - y) <= half


def soft_cost(net, pfac):
    """coût de présence des autres nets (dilaté) + historique, par couche ; + coût pour une via"""
    out = []; vcost = np.zeros((N, N))
    half = HALF[net]
    for l in LAYERS:
        others = np.zeros((N, N), bool)
        for n2, cm in copper.items():
            if n2 != net: others |= cm[l]
        d = ndimage.distance_transform_edt(~others) * G
        pres = (d <= CLR + half).astype(float)
        presv = (d <= CLR + VIA_D / 2).astype(float)
        out.append((1.0 + hist[l]) * (1.0 + pres * pfac) - 1.0)
        vcost += (1.0 + hist[l]) * (1.0 + presv * pfac) - 1.0
    out.append(vcost)
    return out


def astar_pf(net, starts, tree, soft, viamask):
    half = HALF[net]
    blk = [HB[(net, l)] for l in LAYERS]
    tgt = tree
    h = np.minimum.reduce([ndimage.distance_transform_edt(~tgt[li]) + (0 if tgt[li].any() else 1e4) for li in range(3)])
    h = np.minimum(h, 1e4)
    openh = []; g = {}; came = {}
    for s in starts:
        g[s] = 0.0; heapq.heappush(openh, (h[s[1], s[2]], s))
    while openh:
        f, cur = heapq.heappop(openh)
        li, i, j = cur; gc = g[cur]
        if f - h[i, j] > gc + 1e-6: continue
        if tgt[li][i, j] and gc > 0: return reconstruct(came, cur)
        for di, dj, c in NB:
            ni, nj = i + di, j + dj
            if not (0 <= ni < N and 0 <= nj < N): continue
            if blk[li][ni, nj] and not tgt[li][ni, nj]: continue
            ng = gc + c * (LAYER_MUL[li] + soft[li][ni, nj])
            nxt = (li, ni, nj)
            if ng < g.get(nxt, 1e18):
                g[nxt] = ng; came[nxt] = cur; heapq.heappush(openh, (ng + h[ni, nj], nxt))
        if viamask[i, j]:
            vc = VIA_COST + soft[3][i, j] * 6
            for lj in range(3):
                if lj == li: continue
                nxt = (lj, i, j); ng = gc + vc
                if ng < g.get(nxt, 1e18):
                    g[nxt] = ng; came[nxt] = cur; heapq.heappush(openh, (ng + h[i, j], nxt))
    return None


def path_to_geom(path, half):
    segs = []; vias_ = []; curl = None; pts = []
    for (li, i, j) in path:
        x, y = to_xy(i, j)
        if curl is None: curl = li
        if li != curl:
            if len(pts) > 1: segs.append((curl, simplify(pts)))
            vias_.append(pts[-1]); pts = [(x, y)]; curl = li
        else:
            pts.append((x, y))
    if len(pts) > 1: segs.append((curl, simplify(pts)))
    return segs, vias_


def route_net(net, pfac):
    half = HALF[net]
    soft = soft_cost(net, pfac)
    pl = sorted(by_net[net], key=lambda p: math.hypot(p[4], p[5]))
    tree = {li: np.zeros((N, N), bool) for li in range(3)}
    li0, m0 = pad_cells(pl[0]); tree[li0] |= m0
    cm = {l: np.zeros((N, N), bool) for l in LAYERS}
    trk, vv = [], []
    rest = pl[1:]
    ok = True
    while rest:
        allt = np.logical_or.reduce([tree[k] for k in range(3)]); ys, xs = np.nonzero(allt)
        rest.sort(key=lambda p: np.min(np.hypot(XC[ys, xs] - p[4], YC[ys, xs] - p[5])))
        p = rest.pop(0); li, m = pad_cells(p); i, j = to_ij(p[4], p[5])
        path = astar_pf(net, [(li, i, j)], tree, soft, HBV[net])
        if path is None:
            ok = False; tree[li] |= m; continue
        segs, vias_ = path_to_geom(path, half)
        for (lk, pts) in segs:
            trk.append((LAYERS[lk], pts)); raster_track(cm[LAYERS[lk]], pts, half)
            tm = np.zeros((N, N), bool); raster_track(tm, pts, G); tree[lk] |= tm
        for (x, y) in vias_:
            vv.append((x, y))
            for l in LAYERS: raster_track(cm[l], [(x, y), (x, y)], VIA_D / 2)
            for k in range(3): tree[k][to_ij(x, y)] = True
        tree[li] |= m
    copper[net] = cm; routes[net] = (trk, vv)
    return ok


def overuse():
    """cellules où le cuivre d'un net viole la clairance d'un autre"""
    total = 0; bad_nets = set()
    for l in LAYERS:
        cnt = np.zeros((N, N), np.int16)
        dil = {}
        for n, cm in copper.items():
            d = ndimage.distance_transform_edt(~cm[l]) * G
            dil[n] = d <= CLR / 2 + G / 2
            cnt += dil[n]
        ov = cnt > 1
        total += int(ov.sum())
        hist[l] += ov * 0.6
        if ov.any():
            for n in copper:
                if (dil[n] & ov).any(): bad_nets.add(n)
    return total, bad_nets


order = sorted(NETS, key=lambda n: -len(by_net[n]))
pfac = 0.6
fails = set()
for it in range(ITERS):
    fails = set()
    targets = order if it == 0 else [n for n in order if n in bad or n in fails_prev]
    for n in targets:
        copper.pop(n, None)
        if not route_net(n, pfac): fails.add(n)
    ov, bad = overuse()
    print(f"itération {it}: recouvrements {ov} nets en conflit {len(bad)} échecs {sorted(fails)}", flush=True)
    fails_prev = fails
    if ov == 0 and not fails: break
    pfac = min(pfac * 1.2, 200.0)

# ---- vias de masse : routage dur une fois les signaux posés
tracks = []; vias = []
for l in LAYERS: occ[l][:] = pad_occ[l]
# légalisation : on fige les nets sans conflit, on retrace les autres en contraintes dures
ov, bad = overuse()
to_redo = [n for n in order if n in bad or n in fails]
print("légalisation de", to_redo)
for n, (trk, vv) in routes.items():
    if n in to_redo: continue
    for (l, pts) in trk:
        tracks.append((n, l, pts, 2 * HALF[n])); paint(l, pts, HALF[n], n)
    for (x, y) in vv:
        vias.append((n, x, y)); paint_via(x, y, n); VIA_HOLES.append((x, y))
leg_fail = []
for n in sorted(to_redo, key=lambda k: -len(by_net[k])):
    half = HALF[n]
    pl = sorted(by_net[n], key=lambda p: math.hypot(p[4], p[5]))
    tree = {li: np.zeros((N, N), bool) for li in range(3)}
    li0, m0 = pad_cells(pl[0]); tree[li0] |= m0
    rest = pl[1:]
    while rest:
        allt = np.logical_or.reduce([tree[k] for k in range(3)]); ys, xs = np.nonzero(allt)
        rest.sort(key=lambda p: np.min(np.hypot(XC[ys, xs] - p[4], YC[ys, xs] - p[5])))
        p = rest.pop(0); li, m = pad_cells(p); i, j = to_ij(p[4], p[5])
        path = astar(n, half, [(li, i, j)], tree)
        w = half
        if path is None and half > W_SIG / 2:
            path = astar(n, W_SIG / 2, [(li, i, j)], tree); w = W_SIG / 2
        if path is None:
            leg_fail.append((n, p[0], p[1])); tree[li] |= m; continue
        commit(n, w, path, tree); tree[li] |= m
print("échecs de légalisation :", leg_fail)
fails = set(f[0] for f in leg_fail)
gf = []
for p in by_net.get("GND", []):
    li, m = pad_cells(p); i, j = to_ij(p[4], p[5])
    path = astar("GND", W_SIG / 2, [(li, i, j)], {}, allow_via=False, via_targets=True)
    if path is None:
        # sinon : rejoindre le cuivre de masse déjà posé sur la même couche
        own = occ[LAYERS[li]] == net_names["GND"]
        tgt = {li: own & ~m}
        path = astar("GND", W_SIG / 2, [(li, i, j)], tgt, allow_via=True)
    if path is None: gf.append((p[0], p[1])); continue
    commit("GND", W_SIG / 2, path)
# vias de couture : relient les remplissages F/B au plan In1
nst = 0
for yv in np.arange(-2.2, 7.8, 0.9):
    for xv in np.arange(-7.6, 7.7, 0.9):
        if math.hypot(xv, yv) > R_BOARD - 0.6: continue
        vm = via_ok_mask("GND")
        i, j = to_ij(xv, yv)
        if vm[i, j]:
            xv, yv = float(xv), float(yv); vias.append(("GND", xv, yv)); paint_via(xv, yv, "GND"); VIA_HOLES.append((xv, yv)); nst += 1
print("vias de couture :", nst)
failed = sorted(fails)
print("vias GND manquantes :", gf)

exec(_src[_src.find("# ------------------------------------------------------------------ écriture"):].replace(
    'print("pistes", len(tracks), "vias", len(vias), "échecs", failed, "gnd", gf)',
    'print("pistes", len(tracks), "vias", len(vias), "échecs", failed, "gnd", gf, "recouvrements", ov)'))
