"""Logo « Alea Palamedis » façon manuscrit enluminé — SVG autonome (textes vectorisés, polices OFL :
UnifrakturMaguntia pour la lettre gothique, Cinzel pour la devise)."""
import math, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

F = "/home/claude/fonts/"
GOTH = TTFont(F + "fontsource-unifrakturmaguntia-5.3.0/files/unifrakturmaguntia-latin-400-normal.woff")
CINZ = TTFont(F + "fontsource-cinzel-5.3.0/files/cinzel-latin-400-normal.woff")

def text_path(font, s, x, y, size, spacing=0.0):
    gs = font.getGlyphSet(); cmap = font.getBestCmap(); upm = font["head"].unitsPerEm; k = size / upm
    pen = SVGPathPen(gs); cx = x
    for ch in s:
        g = cmap.get(ord(ch))
        if g is None: cx += size * 0.3; continue
        tp = TransformPen(pen, (k, 0, 0, -k, cx, y)); gs[g].draw(tp)
        cx += gs[g].width * k + spacing * size
    return pen.getCommands(), cx

def width(font, s, size, spacing=0.0):
    return text_path(font, s, 0, 0, size, spacing)[1]

W, H = 1080, 380
INK, RED, LAPIS, GREEN = "#2a1a0c", "#a8231a", "#1d3b8f", "#2f6b3a"
out = []
add = out.append
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Alea Palamedis — les dés connectés de Mandragore">')
add('''<defs>
 <radialGradient id="parch" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#f6ead0"/><stop offset=".7" stop-color="#ecdbb2"/><stop offset="1" stop-color="#d9c08a"/></radialGradient>
 <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7e08a"/><stop offset=".35" stop-color="#d4a62a"/><stop offset=".6" stop-color="#fbe9a6"/><stop offset="1" stop-color="#a87b12"/></linearGradient>
 <filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7"/><feColorMatrix values="0 0 0 0 .45  0 0 0 0 .33  0 0 0 0 .15  0 0 0 .10 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>
 <pattern id="diaper" width="22" height="22" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#1d3b8f"/><path d="M11 0 L22 11 L11 22 L0 11Z" fill="none" stroke="#2f55b8" stroke-width="1.2"/><circle cx="11" cy="11" r="1.6" fill="#f3e6c4" opacity=".85"/></pattern>
</defs>''')
# parchemin
add(f'<rect x="6" y="6" width="{W-12}" height="{H-12}" rx="10" fill="url(#parch)"/>')
add(f'<rect x="6" y="6" width="{W-12}" height="{H-12}" rx="10" fill="#000" filter="url(#grain)"/>')
add(f'<rect x="22" y="22" width="{W-44}" height="{H-44}" fill="none" stroke="{RED}" stroke-width="3"/>')
add(f'<rect x="30" y="30" width="{W-60}" height="{H-60}" fill="none" stroke="url(#gold)" stroke-width="1.6"/>')

# lettrine
bx, by, bs = 58, 56, 268
add(f'<rect x="{bx-8}" y="{by-8}" width="{bs+16}" height="{bs+16}" fill="url(#gold)"/>')
add(f'<rect x="{bx}" y="{by}" width="{bs}" height="{bs}" fill="url(#diaper)"/>')
add(f'<rect x="{bx+6}" y="{by+6}" width="{bs-12}" height="{bs-12}" fill="none" stroke="#f3e6c4" stroke-width="1.5" opacity=".8"/>')
# rinceaux blancs dans les coins de la lettrine
for (cx, cy, sx, sy) in ((bx+18, by+18, 1, 1), (bx+bs-18, by+18, -1, 1), (bx+18, by+bs-18, 1, -1), (bx+bs-18, by+bs-18, -1, -1)):
    add(f'<path d="M{cx} {cy} q {28*sx} {4*sy} {34*sx} {30*sy} m {-34*sx} {-30*sy} q {4*sx} {28*sy} {30*sx} {34*sy}" fill="none" stroke="#f3e6c4" stroke-width="2" stroke-linecap="round"/>')
    add(f'<circle cx="{cx+34*sx}" cy="{cy+30*sy}" r="3" fill="{RED}"/><circle cx="{cx+30*sx}" cy="{cy+34*sy}" r="3" fill="{RED}"/>')
# icosaèdre (D20) vermillon derrière la lettre
icx, icy, ir = bx + bs/2, by + bs/2 + 22, 70
hexp = [(icx + ir*math.cos(math.radians(90+60*i)), icy - ir*math.sin(math.radians(90+60*i))) for i in range(6)]
tri = [(icx + ir*0.55*math.cos(math.radians(90+120*i)), icy - ir*0.55*math.sin(math.radians(90+120*i))) for i in range(3)]
P = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
add(f'<polygon points="{P(hexp)}" fill="{RED}" opacity=".92" stroke="#f3e6c4" stroke-width="2"/>')
add(f'<polygon points="{P(tri)}" fill="none" stroke="#f3e6c4" stroke-width="2"/>')
for i, t in enumerate(tri):
    for j in (0, 1):
        h = hexp[(2*i + j*2 - 1) % 6] if False else None
for i in range(3):
    t = tri[i]
    for h in (hexp[(2*i) % 6], hexp[(2*i + 1) % 6], hexp[(2*i - 1) % 6]):
        add(f'<line x1="{t[0]:.1f}" y1="{t[1]:.1f}" x2="{h[0]:.1f}" y2="{h[1]:.1f}" stroke="#f3e6c4" stroke-width="1.6"/>')
# grande lettre A dorée
d, w = text_path(GOTH, "A", 0, 0, 300)
ax = bx + (bs - w) / 2; ay = by + bs - 36
d, _ = text_path(GOTH, "A", ax, ay, 300)
add(f'<path d="{d}" fill="{INK}" opacity=".55" transform="translate(4 4)"/>')
add(f'<path d="{d}" fill="url(#gold)" stroke="#6b4a08" stroke-width="2.2" paint-order="stroke"/>')

# texte
tx = bx + bs + 34
d, x_end = text_path(GOTH, "lea", tx, 176, 150)
add(f'<path d="{d}" fill="{INK}"/>')
d, x2 = text_path(GOTH, "Palamedis", tx, 300, 132)
add(f'<path d="{d}" fill="{RED}"/>')
# devise, centrée sous le texte, en Cinzel
motto = "LES DÉS CONNECTÉS DE MANDRAGORE"
mw = width(CINZ, motto, 25, 0.12)
mx = max(tx + (max(x_end, x2) - tx - mw) / 2, bx + bs + 50)
d, _ = text_path(CINZ, motto, mx, 340, 25, 0.12)
add(f'<path d="{d}" fill="{INK}" opacity=".85"/>')
# fleurons de part et d'autre de la devise
for fx in (mx - 26, mx + mw + 14):
    add(f'<path d="M{fx} 332 l6 -7 l6 7 l-6 7 z" fill="{RED}"/>')

# rinceau végétal (feuilles de lierre) le long de la marge droite
vx = max(x_end, x2) + 62
if vx < W - 40:
    add(f'<path d="M{vx} 70 C {vx+40} 120, {vx-30} 180, {vx+10} 230 S {vx+40} 300, {vx} 330" fill="none" stroke="{GREEN}" stroke-width="3"/>')
    for (lx, ly, s) in ((vx+22, 105, 1), (vx-12, 165, -1), (vx+18, 228, 1), (vx-8, 290, -1)):
        add(f'<path d="M{lx} {ly} q {14*s} -16 {28*s} 0 q {-14*s} 16 {-28*s} 0z" fill="{GREEN}" opacity=".9"/>')
        add(f'<circle cx="{lx+30*s}" cy="{ly}" r="4.5" fill="url(#gold)"/>')
add('</svg>')
open(sys.argv[1] if len(sys.argv) > 1 else "logo.svg", "w").write("\n".join(out))
print("ok", x_end, x2)
