#!/usr/bin/env python3
"""Genera icone e illustrazioni originali (nessuna immagine di terzi: nessuna licenza da gestire).
Uso: python3 scripts/make_assets.py   (serve Pillow solo per le icone PNG/ICO)"""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def icon():
    from PIL import Image, ImageDraw
    S, K = 1024, 4
    im = Image.new("RGBA", (S * K, S * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, S * K - 1, S * K - 1), radius=230 * K, fill=(17, 17, 19, 255))
    d.rectangle((250 * K, 270 * K, 774 * K, 380 * K), fill="white")      # barra della T
    d.rounded_rectangle((457 * K, 270 * K, 567 * K, 790 * K), radius=8 * K, fill="white")  # asta
    im = im.resize((S, S), Image.LANCZOS)
    im.save(os.path.join(ROOT, "assets", "icon.png"))
    im.save(os.path.join(ROOT, "assets", "icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    im.resize((180, 180), Image.LANCZOS).save(os.path.join(ROOT, "docs", "assets", "apple-touch-icon.png"))

FAV = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><title>Twenties Cleaning</title>'
       '<rect width="64" height="64" rx="14" fill="#111113"/><rect x="16" y="17" width="32" height="7" fill="#fff"/>'
       '<rect x="28.5" y="17" width="7" height="32" rx="1" fill="#fff"/></svg>')

HERO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420" role="img" aria-labelledby="t d">
<title id="t">{title}</title><desc id="d">{desc}</desc>
<style>
.win{{fill:#fff;stroke:#d2d2d7}} .tx{{font:600 15px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#1d1d1f}}
.mu{{font:500 13px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#55555b}}
.h{{font:700 24px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#1d1d1f}}
.track{{fill:#ececf0}} .bar{{transform-box:fill-box;transform-origin:left center;animation:grow 1.4s cubic-bezier(.2,.7,.2,1) both}}
.b2{{animation-delay:.15s}} .b3{{animation-delay:.3s}} .b4{{animation-delay:.45s}}
.card{{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}} .c2{{animation-delay:.5s}}
.pulse{{animation:pulse 2.4s ease-in-out 1.6s infinite;transform-box:fill-box;transform-origin:center}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.06)}}}}
@media (prefers-reduced-motion:reduce){{.bar,.card,.pulse{{animation:none}}}}
</style>
<rect x="8" y="8" width="624" height="404" rx="22" class="win"/>
<circle cx="36" cy="34" r="6" fill="#ff5f57"/><circle cx="58" cy="34" r="6" fill="#febc2e"/><circle cx="80" cy="34" r="6" fill="#28c840"/>
<text x="40" y="82" class="h">{h}</text><text x="40" y="104" class="mu">{sub}</text>
<g class="card"><rect x="40" y="126" width="560" height="168" rx="16" fill="#f5f5f7"/>
{rows}</g>
<g class="card c2 pulse"><rect x="40" y="312" width="270" height="76" rx="16" fill="#1a7f4b"/>
<text x="64" y="345" font-family="-apple-system,'Segoe UI',Helvetica,Arial,sans-serif" font-size="13" font-weight="600" fill="#fff">{free}</text>
<text x="64" y="372" font-family="-apple-system,'Segoe UI',Helvetica,Arial,sans-serif" font-size="24" font-weight="700" fill="#fff">{gb}</text></g>
<g class="card c2"><rect x="330" y="312" width="270" height="76" rx="16" fill="#f5f5f7"/>
<path d="M366 336h28l-3 30a4 4 0 0 1-4 3.600h-14a4 4 0 0 1-4-3.600z M362 330h36 M372 330v-4h16v4" fill="none" stroke="#1d1d1f" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
<text x="416" y="345" class="tx">{bin}</text><text x="416" y="368" class="mu">{bin2}</text></g>
</svg>"""

def hero(lang):
    T = {"it": dict(title="Schermata di Twenties Cleaning", desc="Finestra dell'app con barre che mostrano quanto spazio occupano giochi, download, doppioni e cache, e il totale recuperabile.",
                    h="Panoramica", sub="Cosa occupa spazio sul tuo computer", free="Spazio recuperabile", gb="48,3 GB", bin="Sempre nel Cestino", bin2="Niente è cancellato per sempre",
                    rows=[("Giochi", 62, "#7c3aed", "182 GB"), ("Download", 41, "#b45309", "120 GB"), ("Doppioni", 24, "#0b57d0", "71 GB"), ("Cache e temporanei", 15, "#1a7f4b", "44 GB")]),
         "en": dict(title="Twenties Cleaning screenshot", desc="App window with bars showing how much space games, downloads, duplicates and cache use, and the total you can recover.",
                    h="Overview", sub="What is taking up space on your computer", free="Recoverable space", gb="48.3 GB", bin="Always the Recycle Bin", bin2="Nothing is deleted for good",
                    rows=[("Games", 62, "#7c3aed", "182 GB"), ("Downloads", 41, "#b45309", "120 GB"), ("Duplicates", 24, "#0b57d0", "71 GB"), ("Cache &amp; temp files", 15, "#1a7f4b", "44 GB")])}[lang]
    rows = ""
    for i, (n, pct, col, sz) in enumerate(T.pop("rows")):
        y = 150 + i * 36
        rows += (f'<text x="64" y="{y + 14}" class="tx">{n}</text><text x="576" y="{y + 14}" text-anchor="end" class="mu">{sz}</text>'
                 f'<rect x="64" y="{y + 20}" width="512" height="8" rx="4" class="track"/>'
                 f'<rect x="64" y="{y + 20}" width="{512 * pct // 100}" height="8" rx="4" fill="{col}" class="bar b{i + 1}"/>')
    return HERO.format(rows=rows, **T)

if __name__ == "__main__":
    a = os.path.join(ROOT, "docs", "assets")
    os.makedirs(a, exist_ok=True)
    open(os.path.join(a, "favicon.svg"), "w", encoding="utf-8").write(FAV)
    for l in ("it", "en"):
        open(os.path.join(a, f"hero-{l}.svg"), "w", encoding="utf-8").write(hero(l))
    try:
        icon()
    except ImportError:
        print("Pillow non trovato: icone PNG/ICO non rigenerate")
    print("assets ok")
