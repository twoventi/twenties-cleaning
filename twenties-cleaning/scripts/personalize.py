#!/usr/bin/env python3
"""Sostituisce i segnaposto con i tuoi dati in sito, README, licenza e sicurezza.
Uso:  python3 scripts/personalize.py --user mioutente --repo twenties-cleaning --name "Nome Cognome" --email tu@esempio.it"""
import argparse, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = argparse.ArgumentParser()
a.add_argument("--user", required=True, help="nome utente GitHub")
a.add_argument("--repo", required=True, help="nome del repository")
a.add_argument("--name", required=True, help="nome e cognome (o il nome con cui vuoi comparire)")
a.add_argument("--email", required=True, help="email di contatto pubblica")
x = a.parse_args()
if not re.fullmatch(r"[A-Za-z0-9-]+", x.user) or not re.fullmatch(r"[A-Za-z0-9._-]+", x.repo):
    sys.exit("Utente o repository GitHub non validi.")
if not re.fullmatch(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+", x.email):
    sys.exit("Email non valida.")
esc = lambda v: v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
files = glob.glob(os.path.join(ROOT, "docs", "*.html")) + [os.path.join(ROOT, f) for f in ("README.md", "LICENSE", "SECURITY.md")]
n = 0
for f in files:
    t = open(f, encoding="utf-8").read()
    o = t
    html = f.endswith(".html")
    t = (t.replace("{{GITHUB_USER}}", x.user).replace("{{REPO}}", x.repo)
          .replace("{{NOME}}", esc(x.name) if html else x.name).replace("{{EMAIL}}", esc(x.email) if html else x.email))
    if t != o:
        open(f, "w", encoding="utf-8").write(t)
        n += 1
left = [f for f in files if re.search(r"\{\{[A-Z_]+\}\}", open(f, encoding="utf-8").read())]
print(f"Aggiornati {n} file." + (f" ATTENZIONE, segnaposto rimasti in: {left}" if left else " Nessun segnaposto rimasto."))
print(f"Sito (dopo aver attivato GitHub Pages): https://{x.user}.github.io/{x.repo}/")
