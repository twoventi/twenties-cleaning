#!/usr/bin/env python3
"""Prova di fumo: avvia il server con dati temporanei, poi registra, entra, sbaglia la password,
elimina l'account e controlla che sia sparito. Solo libreria standard."""
import http.client, json, os, socket, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
tmp = tempfile.mkdtemp()
env = dict(os.environ, TC_PORT=str(PORT), HOME=tmp, USERPROFILE=tmp, APPDATA=tmp, XDG_DATA_HOME=tmp, BROWSER="true")
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "src", "twenties_cleaning.py")], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
jar = {}


def req(method, path, body=None, csrf=""):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    h = {"Host": f"127.0.0.1:{PORT}"}
    if jar:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    data = None
    if method == "POST":
        h.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{PORT}", "X-CSRF-Token": csrf})
        data = json.dumps(body)
    c.request(method, path, data, h)
    r = c.getresponse()
    t = r.read()
    for k, v in r.getheaders():
        if k.lower() == "set-cookie":
            n, val = v.split(";")[0].split("=", 1)
            if "Max-Age=0" in v:
                jar.pop(n, None)
            else:
                jar[n] = val
    return r.status, json.loads(t)


def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(1)


try:
    for _ in range(60):
        try:
            st, me = req("GET", "/api/me")
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise SystemExit("il server non si avvia")
    csrf = me["csrf"]
    check("server risponde, nessun utente", st == 200 and me["user"] is None)
    st, r = req("POST", "/api/register", {"email": "prova@example.com", "password": "correct-horse-9"}, csrf)
    check("registrazione", st == 200)
    csrf = r["csrf"]
    check("sessione attiva", req("GET", "/api/me")[1]["user"]["email"] == "prova@example.com")
    check("eliminazione con password errata rifiutata", req("POST", "/api/delete_account", {"password": "sbagliata-123"}, csrf)[0] == 401)
    check("eliminazione senza password rifiutata", req("POST", "/api/delete_account", {}, csrf)[0] == 400)
    st, r = req("POST", "/api/delete_account", {"password": "correct-horse-9"}, csrf)
    check("eliminazione account", st == 200 and r.get("ok"))
    csrf = r["csrf"]
    check("sessione chiusa dopo l'eliminazione", req("GET", "/api/me")[1]["user"] is None)
    check("accesso impossibile dopo l'eliminazione", req("POST", "/api/login", {"email": "prova@example.com", "password": "correct-horse-9"}, csrf)[0] == 401)
    print("Tutto a posto.")
finally:
    proc.terminate()
    try:
        proc.wait(10)
    except Exception:
        proc.kill()
