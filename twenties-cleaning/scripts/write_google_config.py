"""Genera src/_google_config.py dai secret di GitHub Actions (variabili d'ambiente).
Se mancano, non scrive nulla e la build parte senza accesso con Google."""
import os, sys
cid, sec = os.environ.get("GOOGLE_CLIENT_ID", "").strip(), os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
if not (cid and sec):
    print("Credenziali Google non presenti: build senza accesso con Google.")
    sys.exit(0)
with open(os.path.join("src", "_google_config.py"), "w", encoding="utf-8") as f:
    f.write("CLIENT_ID = %r\nCLIENT_SECRET = %r\n" % (cid, sec))
print("Credenziali Google incorporate nella build.")
