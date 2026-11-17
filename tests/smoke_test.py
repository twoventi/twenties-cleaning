#!/usr/bin/env python3
"""Prova di fumo: avvia il server senza finestra, poi registra, entra, sbaglia la password,
elimina l'account e controlla che sia sparito. Controlla anche che una seconda copia non parta.
Solo libreria standard, nessun display."""
import http.client, http.server, json, os, socket, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "src", "twenties_cleaning.py")
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
tmp = tempfile.mkdtemp()
env = dict(os.environ, TC_PORT=str(PORT), TC_HEADLESS="1", HOME=tmp, USERPROFILE=tmp, APPDATA=tmp, XDG_DATA_HOME=tmp, BROWSER="true")
proc = subprocess.Popen([sys.executable, APP, "--headless"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    check("modalità senza finestra", me.get("app") == "Twenties Cleaning" and bool(me.get("version")) and me.get("window") is False)
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    c.request("GET", "/auth/finish?t=not-a-real-ticket", headers={"Host": f"127.0.0.1:{PORT}"})
    rr = c.getresponse(); loc = rr.getheader("Location") or ""; rr.read()
    check("passaggio Google senza ticket rifiutato", rr.status == 302 and "google_fail" in loc)

    def once(port):
        home = tempfile.mkdtemp()
        e = dict(os.environ, TC_PORT=str(port), TC_HEADLESS="1", HOME=home, USERPROFILE=home, APPDATA=home, XDG_DATA_HOME=home, BROWSER="true")
        p = subprocess.Popen([sys.executable, APP, "--headless"], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            err = p.communicate(timeout=25)[1]
        except subprocess.TimeoutExpired:
            p.kill(); p.communicate()
            raise SystemExit("una copia in più non è terminata")
        return p.returncode, err.decode("utf-8", "replace")

    code, err = once(PORT)
    check("seconda copia non resta accesa", code == 0 and "già aperto" in err)
    check("la prima copia risponde ancora", req("GET", "/api/me")[0] == 200)

    def occupy(handler):
        sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd, port

    class Old(http.server.BaseHTTPRequestHandler):
        server_version, sys_version = "TwentiesCleaning", ""
        hits = []
        def do_GET(self):
            Old.hits.append(self.path.split("?", 1)[0])
            body = b'{"user":null,"csrf":"x","google":false,"mail":false,"platform":"linux"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass

    class Other(http.server.BaseHTTPRequestHandler):
        server_version, sys_version = "nginx", ""
        def do_GET(self):
            body = b"no"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass

    old, oport = occupy(Old)
    try:
        code, err = once(oport)
        check("versione precedente: errore chiaro", code != 0 and "versione precedente" in err)
        check("versione precedente: non mostra la sua finestra", "/api/focus" not in Old.hits)
    finally:
        old.shutdown()
    other, fport = occupy(Other)
    try:
        code, err = once(fport)
        check("porta di un altro programma: errore chiaro", code != 0 and "occupata" in err)
    finally:
        other.shutdown()
    print("Tutto a posto.")
finally:
    proc.terminate()
    try:
        proc.wait(10)
    except Exception:
        proc.kill()
        proc.wait(5)
    time.sleep(0.3)
    chk = socket.socket()
    try:
        chk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        chk.bind(("127.0.0.1", PORT))
        print("OK   porta liberata alla chiusura")
    except OSError:
        print("FAIL porta ancora occupata dopo la chiusura")
        raise SystemExit(1)
    finally:
        chk.close()
