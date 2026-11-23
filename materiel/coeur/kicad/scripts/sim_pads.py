"""Simulation électrostatique (méthode des moments / BEM) d'un D20 à pastilles capacitives
posé sur un plateau à électrodes.

Conducteurs : électrodes du plateau (grille carrée, z=0), pastilles triangulaires collées
à l'intérieur de la coque du D20, cœur électronique (cylindre = pile + circuit, masse du dé).
Milieu homogène (eps_r = 1) : on compare des configurations entre elles, les valeurs absolues
sont des ordres de grandeur.

Mode EMISSION (plateau à l'encre) : le dé, flottant (charge totale nulle), applique +1 V
sur la/les pastille(s) active(s) par rapport à sa masse. Les électrodes du plateau sont à 0 V
(récepteurs). Signal = charge induite sur chaque électrode.

Mode CLIGNOTEMENT (tablette) : le plateau mesure la capacité mutuelle Tx->Rx ; le dé
relie ou non sa/ses pastille(s) à sa masse. Signal = variation de charge sur Rx.
"""
import itertools, json, sys
import numpy as np

EPS0 = 8.854e-12 * 1e-3  # F/mm
K = 1.0 / (4 * np.pi * EPS0)

# ---------------------------------------------------------------- géométrie D20
phi = (1 + 5 ** 0.5) / 2
V = []
for a in (-1, 1):
    for b in (-1, 1):
        V += [(0, a, b * phi), (a, b * phi, 0), (b * phi, 0, a)]
V = np.array(V, float)
# faces = triplets de sommets à distance 2 (arête)
faces = []
for i, j, k in itertools.combinations(range(12), 3):
    if all(abs(np.linalg.norm(V[p] - V[q]) - 2) < 1e-9 for p, q in ((i, j), (j, k), (i, k))):
        faces.append((i, j, k))
assert len(faces) == 20
cent = np.array([V[list(f)].mean(0) for f in faces])
inr0 = np.linalg.norm(cent[0])
normals = cent / np.linalg.norm(cent, axis=1)[:, None]


def rot_to(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = a @ b
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1, -1, -1])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1 / (1 + c))


def subdiv_tri(tri, n):
    """découpe un triangle en 4^n sous-triangles"""
    tris = [tri]
    for _ in range(n):
        new = []
        for a, b, c in tris:
            ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
            new += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        tris = new
    return tris


class Mesh:
    def __init__(self):
        self.c, self.area, self.cond = [], [], []

    def add_square(self, x0, y0, w, n, z, cond):
        h = w / n
        for i in range(n):
            for j in range(n):
                self.c.append((x0 + (i + .5) * h, y0 + (j + .5) * h, z)); self.area.append(h * h); self.cond.append(cond)

    def add_tri(self, tri, n, cond):
        for a, b, c in subdiv_tri(tri, n):
            self.c.append(tuple((a + b + c) / 3)); self.area.append(0.5 * np.linalg.norm(np.cross(b - a, c - a))); self.cond.append(cond)

    def add_cyl(self, center, axis, R, H, nphi, nz, nr, cond):
        axis = axis / np.linalg.norm(axis)
        u = np.cross(axis, [1, 0, 0]);
        if np.linalg.norm(u) < 1e-6: u = np.cross(axis, [0, 1, 0])
        u /= np.linalg.norm(u); w = np.cross(axis, u)
        for i in range(nphi):
            t = 2 * np.pi * (i + .5) / nphi
            for j in range(nz):
                zz = -H / 2 + (j + .5) * H / nz
                p = center + R * (np.cos(t) * u + np.sin(t) * w) + zz * axis
                self.c.append(tuple(p)); self.area.append(2 * np.pi * R / nphi * H / nz); self.cond.append(cond)
        for s in (-1, 1):
            for k in range(nr):
                r0, r1 = R * k / nr, R * (k + 1) / nr
                m = max(1, int(round(nphi * (k + .5) / nr)))
                for i in range(m):
                    t = 2 * np.pi * (i + .5) / m; rr = (r0 + r1) / 2
                    p = center + s * H / 2 * axis + rr * (np.cos(t) * u + np.sin(t) * w)
                    self.c.append(tuple(p)); self.area.append(np.pi * (r1 ** 2 - r0 ** 2) / m); self.cond.append(cond)

    def matrix(self):
        c = np.array(self.c); a = np.array(self.area)
        d = np.linalg.norm(c[:, None, :] - c[None, :, :], axis=2)
        np.fill_diagonal(d, 1.0)
        P = K / d
        # terme propre : disque de même aire, potentiel moyen ~ (8/3π)*potentiel au centre -> on prend le centre
        R = np.sqrt(a / np.pi)
        np.fill_diagonal(P, 1 / (2 * np.pi * EPS0 * R))  # potentiel au centre d'un disque uniformément chargé
        return P


def solve(mesh, fixed, floating):
    """fixed: {cond: V}. floating: list of (set_of_conds, {cond: offset}) — groupe flottant de charge nulle.
    retourne charges par panneau."""
    P = mesh.matrix(); cond = np.array(mesh.cond); N = len(cond)
    G = len(floating)
    A = np.zeros((N + G, N + G)); rhs = np.zeros(N + G)
    A[:N, :N] = P
    for n in range(N):
        cnd = cond[n]
        if cnd in fixed:
            rhs[n] = fixed[cnd]
        else:
            for g, (conds, off) in enumerate(floating):
                if cnd in conds:
                    A[n, N + g] = -1.0; rhs[n] = off.get(cnd, 0.0); break
            else:
                raise ValueError(f"conducteur non affecté {cnd}")
    for g, (conds, _) in enumerate(floating):
        A[N + g, :N] = np.isin(cond, list(conds)).astype(float)
    x = np.linalg.solve(A, rhs)
    return x[:N], x[N:]


# ---------------------------------------------------------------- scène
def build(die_xy=(0.0, 0.0), face_down=0, F2F=22.0, wall=0.8, gap=0.1, pad_scale=0.75,
          pitch=5.0, pad_w=4.5, ngrid=10, nsub_board=3, nsub_tri=2, core=(6.5, 10.0), yaw=0.3,
          finger=False):
    m = Mesh()
    # électrodes du plateau
    half = ngrid * pitch / 2
    board_ids = []
    for i in range(ngrid):
        for j in range(ngrid):
            cid = f"B{i}_{j}"; board_ids.append((cid, -half + (i + .5) * pitch, -half + (j + .5) * pitch))
            m.add_square(-half + i * pitch + (pitch - pad_w) / 2, -half + j * pitch + (pitch - pad_w) / 2, pad_w, nsub_board, 0.0, cid)
    if finger == "finger":  # doigt de référence : cylindre Ø8 mm relié à la terre
        m.add_cyl(np.array([die_xy[0], die_xy[1], gap + 5.0]), np.array([0, 0, 1.0]), 4.0, 10.0, 16, 4, 3, "FINGER")
        return m, board_ids, None
    if finger == "none":
        return m, board_ids, None
    r_out = F2F / 2; r_in = r_out - wall
    Rm = rot_to(normals[face_down], np.array([0, 0, -1.0]))
    Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    Rt = Rz @ Rm
    center = np.array([die_xy[0], die_xy[1], gap + r_out])
    s_in = r_in / inr0
    for f, (i, j, k) in enumerate(faces):
        tri = [V[i] * s_in, V[j] * s_in, V[k] * s_in]
        cc = sum(tri) / 3
        tri = [cc + pad_scale * (p - cc) for p in tri]
        tri = [Rt @ p + center for p in tri]
        m.add_tri(tuple(np.array(t) for t in tri), nsub_tri, f"F{f}")
    R, H = core
    m.add_cyl(center, Rt @ np.array([0, 0, 1.0]), R, H, 18, 5, 3, "CORE")
    return m, board_ids, Rt


def groups4():
    tet = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], float) / 3 ** .5
    g = np.argmax(normals @ tet.T, axis=1)
    return g


def board_signal(mesh, q, board_ids):
    cond = np.array(mesh.cond)
    out = []
    for cid, x, y in board_ids:
        out.append((x, y, q[cond == cid].sum()))
    return np.array(out)


def metrics(sig, die_xy):
    x, y, s = sig[:, 0], sig[:, 1], -sig[:, 2]  # charge induite négative pour +V -> on inverse
    peak = s.max(); tot = s[s > 0].sum()
    w = np.clip(s, 0, None)
    # centroïde sur les électrodes > 20 % du pic (comme un vrai contrôleur)
    sel = s > 0.2 * peak
    cx, cy = (w[sel] * x[sel]).sum() / w[sel].sum(), (w[sel] * y[sel]).sum() / w[sel].sum()
    rad = np.sqrt((w * ((x - die_xy[0]) ** 2 + (y - die_xy[1]) ** 2)).sum() / w.sum())
    n_half = int((s > 0.5 * peak).sum())
    return dict(peak_fC=peak * 1e15, total_fC=tot * 1e15, centroid_err_mm=float(np.hypot(cx - die_xy[0], cy - die_xy[1])),
                spread_rms_mm=float(rad), n_electrodes_above_half=n_half)


def run_emission(die_xy, face_down, config, yaw=0.3, **kw):
    m, bids, Rt = build(die_xy, face_down, yaw=yaw, **kw)
    fixed = {cid: 0.0 for cid, _, _ in bids}
    pads = [f"F{f}" for f in range(20)]
    die = set(pads) | {"CORE"}
    if config == "A_toutes_reliees":
        floating = [(die, {p: 1.0 for p in pads})]
    elif config == "B_une_par_face":
        floating = [(die, {f"F{face_down}": 1.0})]  # autres pastilles reliées à la masse du dé
    elif config == "B2_une_par_face_autres_en_l_air":
        floating = [({f"F{face_down}", "CORE"}, {f"F{face_down}": 1.0})] + [({p}, {}) for p in pads if p != f"F{face_down}"]
    elif config in GROUPINGS:
        g = GROUPINGS[config](); gd = g[face_down]
        floating = [(die, {f"F{f}": 1.0 for f in range(20) if g[f] == gd})]
    else:
        raise ValueError(config)
    q, V0 = solve(m, fixed, floating)
    return metrics(board_signal(m, q, bids), die_xy), board_signal(m, q, bids)


def run_tablet(die_xy, face_down, config, yaw=0.3, **kw):
    """capacité mutuelle Tx->Rx : Tx = électrode sous le dé, Rx = voisine. delta entre
    pastille(s) reliée(s) à la masse du dé et pastille(s) en l'air."""
    m, bids, Rt = build(die_xy, face_down, yaw=yaw, **kw)
    # électrode la plus proche du dé = Tx, voisine en x = Rx
    d = [(np.hypot(x - die_xy[0], y - die_xy[1]), cid, x, y) for cid, x, y in bids]
    d.sort(); tx = d[0][1]; txx, txy = d[0][2], d[0][3]
    rx = min(((np.hypot(x - txx - kw.get('pitch', 5.0), y - txy), cid) for cid, x, y in bids))[1]
    pads = [f"F{f}" for f in range(20)]
    fixed = {cid: (1.0 if cid == tx else 0.0) for cid, _, _ in bids}
    def charge_rx(floating):
        q, _ = solve(m, fixed, floating); cond = np.array(m.cond)
        return q[cond == rx].sum()
    if config == "A_toutes_reliees":
        act = pads
    elif config in ("B_une_par_face",):
        act = [f"F{face_down}"]
    elif config in GROUPINGS:
        g = GROUPINGS[config](); act = [f"F{f}" for f in range(20) if g[f] == g[face_down]]
    on = [({"CORE", *act}, {})] + [({p}, {}) for p in pads if p not in act]
    off = [({"CORE"}, {})] + [({p}, {}) for p in pads]
    q_on, q_off = charge_rx(on), charge_rx(off)
    # référence : rien sur le plateau / doigt relié à la terre
    return dict(dQ_fC=(q_on - q_off) * 1e15, q_off_fC=q_off * 1e15), tx, rx


def run_tablet_ref(die_xy, **kw):
    """charge Rx sans objet et avec un doigt relié à la terre (référence de détection)"""
    out = {}
    for mode in ("none", "finger"):
        m0, bids, _ = build(die_xy, finger=mode, **kw)
        d = sorted((np.hypot(x - die_xy[0], y - die_xy[1]), cid, x, y) for cid, x, y in bids)
        tx, txx, txy = d[0][1], d[0][2], d[0][3]
        rx = min(((np.hypot(x - txx - kw.get('pitch', 5.0), y - txy), cid) for cid, x, y in bids))[1]
        fixed = {cid: (1.0 if cid == tx else 0.0) for cid, _, _ in bids}
        if mode == "finger": fixed["FINGER"] = 0.0
        q, _ = solve(m0, fixed, []); cond = np.array(m0.cond)
        out[mode] = q[cond == rx].sum() * 1e15
    return out


import functools
GROUPINGS = {"C_4_groupes_voisines": functools.lru_cache(None)(lambda: groups4_clustered()),
             "D_4_groupes_disperses": functools.lru_cache(None)(lambda: groups4_spread())}




# ---------------------------------------------------------------- groupements équilibrés
def groups4_clustered():
    """4 groupes de 5 faces voisines (calottes)"""
    from scipy.optimize import linear_sum_assignment
    tet = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], float) / 3 ** .5
    # légère rotation pour casser les égalités
    tet = tet @ rot_to(np.array([1, 1, 1.0]), np.array([1, 1.1, 0.95])).T
    cost = -(normals @ tet.T)
    r, c = linear_sum_assignment(np.repeat(cost, 5, axis=1))
    g = np.empty(20, int); g[r] = c // 5
    return g


def groups4_spread(seed=1, iters=20000):
    """4 groupes de 5 faces aussi éloignées que possible les unes des autres"""
    rng = np.random.default_rng(seed)
    D = normals @ normals.T
    g = np.repeat(np.arange(4), 5); rng.shuffle(g)
    def score(g):
        s = 0.0
        for k in range(4):
            idx = np.where(g == k)[0]; sub = D[np.ix_(idx, idx)]
            s += np.sort(sub[np.triu_indices(5, 1)])[-1] * 100 + sub[np.triu_indices(5, 1)].sum()
        return s
    best = score(g)
    for _ in range(iters):
        i, j = rng.integers(0, 20, 2)
        if g[i] == g[j]: continue
        g2 = g.copy(); g2[i], g2[j] = g2[j], g2[i]
        sc = score(g2)
        if sc <= best: g, best = g2, sc
    return g


def min_angle_in_groups(g):
    out = []
    for k in range(4):
        idx = np.where(g == k)[0]; sub = normals[idx] @ normals[idx].T
        out.append(np.degrees(np.arccos(np.clip(sub[np.triu_indices(len(idx), 1)].max(), -1, 1))))
    return min(out)


if __name__ == "__main__":
    print("groupes 4 :", np.bincount(groups4()))
