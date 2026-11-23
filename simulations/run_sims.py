import json, time, numpy as np, sim_pads as S
CONFIGS = ["A_toutes_reliees", "B_une_par_face", "B2_une_par_face_autres_en_l_air", "C_4_groupes_voisines", "D_4_groupes_disperses"]
rng = np.random.default_rng(7)
cases = [((2.5, 2.5), 0, 0.3), ((0.0, 0.0), 5, 1.1), ((1.3, 3.6), 11, 2.0), ((3.9, 0.8), 17, 0.7)]
res = {c: [] for c in CONFIGS}; maps = {}
t = time.time()
for (xy, fd, yaw) in cases:
    for c in CONFIGS:
        m, sig = S.run_emission(xy, fd, c, yaw=yaw)
        res[c].append(m)
        if xy == (2.5, 2.5): maps[c] = sig.tolist()
print("emission done", round(time.time() - t, 1), "s")
summary = {}
for c in CONFIGS:
    r = res[c]
    summary[c] = {k: float(np.mean([x[k] for x in r])) for k in r[0]}
    summary[c]["centroid_err_max_mm"] = float(max(x["centroid_err_mm"] for x in r))
for c in CONFIGS: print(c, {k: round(v, 2) for k, v in summary[c].items()})
# tablette
tab = {c: [] for c in ["A_toutes_reliees", "B_une_par_face", "C_4_groupes_voisines", "D_4_groupes_disperses"]}
for (xy, fd, yaw) in cases:
    for c in tab:
        m, tx, rx = S.run_tablet(xy, fd, c, yaw=yaw)
        tab[c].append(m)
refs = [S.run_tablet_ref(xy) for (xy, _, _) in cases]
q_none = np.mean([r["none"] for r in refs]); q_f = np.mean([r["finger"] for r in refs])
print("tablette: Rx sans objet", round(q_none, 2), "fC ; doigt", round(q_f, 2), "fC ; effet doigt", round(q_f - q_none, 2))
tabsum = {}
for c in tab:
    dq = float(np.mean([x["dQ_fC"] for x in tab[c]]))
    tabsum[c] = {"dQ_fC": dq, "pct_doigt": 100 * dq / (q_f - q_none)}
    print(c, {k: round(v, 3) for k, v in tabsum[c].items()})
json.dump({"emission": summary, "emission_raw": res, "maps_centered": maps, "tablet": tabsum,
           "tablet_ref": {"none_fC": q_none, "finger_fC": q_f}}, open("/home/claude/de-mandragore/sim_results.json", "w"), indent=1)
