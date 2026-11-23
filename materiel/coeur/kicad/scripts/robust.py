import numpy as np, sim_pads as S, json
C=["A_toutes_reliees","B_une_par_face","D_4_groupes_disperses","C_4_groupes_voisines"]
out={}
def row(label,**kw):
    r={}
    for c in C:
        m,_=S.run_emission((2.5,2.5),0,c,yaw=0.3,**kw); r[c]=round(m["peak_fC"],1)
    out[label]=r; print(label, r, " A/B=%.3f D/B=%.2f"%(r[C[0]]/r[C[1]], r[C[2]]/r[C[1]]))
row("base")
row("maillage fin", nsub_tri=3, nsub_board=5)
row("paroi 1.5 mm", wall=1.5)
row("pas plateau 8 mm", pitch=8.0, pad_w=7.0, ngrid=7)
row("pastilles 50% de la face", pad_scale=0.5)
row("D20 26 mm", F2F=26.0)
json.dump(out,open('/home/claude/de-mandragore/sim_robust.json','w'),indent=1)
