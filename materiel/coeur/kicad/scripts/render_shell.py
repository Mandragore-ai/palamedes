import sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
D = "/home/claude/de-mandragore/shell"
views = [("D20_coque_assemblee.stl", "Coque assemblée", (20, 35)),
         ("D20_coque_bas.stl", "Moitié basse (vue de dessus)", (65, 20)),
         ("D20_coque_haut.stl", "Moitié haute (vue de dessus, retournée)", (65, 20))]
fig = plt.figure(figsize=(15, 5.2))
light = np.array([0.4, -0.5, 0.75]); light /= np.linalg.norm(light)
for k, (f, title, (el, az)) in enumerate(views):
    m = trimesh.load(f"{D}/{f}")
    m.apply_translation(-m.bounding_box.centroid)
    ax = fig.add_subplot(1, 3, k + 1, projection="3d")
    tris = m.triangles; n = m.face_normals
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    cols = np.c_[0.55 * shade, 0.62 * shade, 0.80 * shade, np.ones(len(shade))]
    pc = Poly3DCollection(tris, facecolors=cols, edgecolors="none"); ax.add_collection3d(pc)
    r = 12.5; ax.set_xlim(-r, r); ax.set_ylim(-r, r); ax.set_zlim(-r, r); ax.set_box_aspect((1, 1, 1))
    ax.view_init(el, az); ax.set_axis_off(); ax.set_title(title, fontsize=11)
plt.tight_layout(); plt.savefig(f"{D}/apercu_coque.png", dpi=110, facecolor="white")
print("ok")
