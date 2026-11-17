#!/usr/bin/env python3
"""Genera icone e illustrazioni originali (nessuna immagine di terzi: nessuna licenza da gestire).
Uso: python3 scripts/make_assets.py   (serve Pillow solo per le icone PNG/ICO)"""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def icon():
    """Il logo (assets/logo.svg, icon.png, icon.ico, icon.icns) è già disegnato.
    Questo script non lo sostituisce: rigenera solo le illustrazioni del sito."""
    return

FAV = None

HERO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420" role="img" aria-labelledby="t d">
<title id="t">{title}</title><desc id="d">{desc}</desc>
<style>
.win{{fill:#FFFCF7;stroke:#D9CDB8}} .tx{{font:600 15px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#111114}}
.mu{{font:500 13px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#5C574E}}
.h{{font:700 24px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#111114}}
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
<g class="card c2 pulse"><rect x="40" y="312" width="270" height="76" rx="16" fill="#0F6E6B"/>
<text x="64" y="345" font-family="-apple-system,'Segoe UI',Helvetica,Arial,sans-serif" font-size="13" font-weight="600" fill="#fff">{free}</text>
<text x="64" y="372" font-family="-apple-system,'Segoe UI',Helvetica,Arial,sans-serif" font-size="24" font-weight="700" fill="#fff">{gb}</text></g>
<g class="card c2"><rect x="330" y="312" width="270" height="76" rx="16" fill="#f5f5f7"/>
<path d="M366 336h28l-3 30a4 4 0 0 1-4 3.600h-14a4 4 0 0 1-4-3.600z M362 330h36 M372 330v-4h16v4" fill="none" stroke="#111114" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
<text x="416" y="345" class="tx">{bin}</text><text x="416" y="368" class="mu">{bin2}</text></g>
</svg>"""

def hero(lang):
    T = {"it": dict(title="Schermata di Twenties", desc="Finestra dell'app: le etichette dicono perché una cartella pesa, e lo Scarto è una stima, non un ordine di cancellare.",
                    h="Vedi cosa pesa", sub="Decidi tu", free="Stima dello Scarto", gb="48,3 GB", bin="Sempre nel Cestino", bin2="Niente è cancellato per sempre",
                    rows=[("Giochi", 62, "#0F6E6B", "182 GB"), ("Documenti", 41, "#111114", "120 GB"), ("Doppioni", 24, "#1F6F6C", "71 GB"), ("Scarto", 15, "#C2410C", "44 GB")]),
         "en": dict(title="Twenties screenshot", desc="App window: labels say why a folder takes space, and Discard is an estimate, not an order to delete.",
                    h="See what takes space", sub="You decide", free="Discard estimate", gb="48.3 GB", bin="Always the Trash", bin2="Nothing is deleted for good",
                    rows=[("Games", 62, "#0F6E6B", "182 GB"), ("Documents", 41, "#111114", "120 GB"), ("Duplicates", 24, "#1F6F6C", "71 GB"), ("Discard", 15, "#C2410C", "44 GB")])}[lang]
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
    for l in ("it", "en"):
        open(os.path.join(a, f"hero-{l}.svg"), "w", encoding="utf-8").write(hero(l))
    try:
        icon()
    except ImportError:
        print("Pillow non trovato: icone PNG/ICO non rigenerate")
    print("assets ok")
