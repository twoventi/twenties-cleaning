#!/usr/bin/env python3
"""Prova di fumo: avvia il server senza finestra, poi registra, entra, sbaglia la password,
elimina l'account e controlla che sia sparito. Controlla anche che una seconda copia non parta.
Solo libreria standard, nessun display."""
import http.client, http.server, json, os, socket, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "src", "twenties_cleaning.py")
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
tmp = tempfile.mkdtemp()
FIXTURE = os.path.join(tmp, "release.json")
env = dict(os.environ, TC_PORT=str(PORT), TC_HEADLESS="1", HOME=tmp, USERPROFILE=tmp, APPDATA=tmp, XDG_DATA_HOME=tmp,
            BROWSER="true", PYTHONUTF8="1", PYTHONIOENCODING="utf-8", TC_UPDATE_FIXTURE=FIXTURE)
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


def check(name, cond, detail=""):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        if detail:
            print(detail)
        raise SystemExit(1)


def text(raw):
    """Su Windows la pipe può essere cp1252 se l'app non è riuscita a passare a UTF-8."""
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


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
    st, drives = req("GET", "/api/drives")
    check("dischi senza account", st == 200 and isinstance(drives, list))
    st, mp = req("GET", "/api/map")
    check("mappa vuota prima dell'analisi", st == 200 and mp.get("roots") == [])
    st, settings = req("GET", "/api/settings")
    check("promemoria scarto spento", st == 200 and settings.get("schedule", {}).get("enabled") is False and settings.get("schedule", {}).get("due") is False)
    st, i18n = req("GET", "/api/i18n")
    cat = i18n.get("catalog") or {}
    check("lingue it e en", st == 200 and cat.get("it", {}).get("tagline") == "Vedi cosa pesa. Decidi tu."
          and cat.get("en", {}).get("tagline") == "See what takes space. You decide.")
    st, upd = req("POST", "/api/update_check", {}, csrf)
    check("controllo versione senza consenso e senza rete", st == 200 and upd.get("consent") is False and "latest" not in upd)
    st, lang = req("POST", "/api/lang", {"lang": "en"}, csrf)
    check("selettore inglese", st == 200 and lang.get("lang") == "en" and lang.get("tagline") == "See what takes space. You decide.")
    st, lang = req("POST", "/api/lang", {"lang": "it"}, csrf)
    check("selettore italiano", st == 200 and lang.get("lang") == "it")
    open(FIXTURE, "w", encoding="utf-8").write(json.dumps({
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/twoventi/twenties-cleaning/releases/tag/v9.9.9"}))
    st, _ = req("POST", "/api/settings", {"updates": True}, csrf)
    check("consenso aggiornamenti", st == 200)
    st, upd = req("POST", "/api/update_check", {}, csrf)
    check("versione più nuova segnalata", st == 200 and upd.get("consent") is True and upd.get("update") is True and upd.get("latest") == "9.9.9")
    open(FIXTURE, "w", encoding="utf-8").write(json.dumps({"tag_name": "v0.0.1", "html_url": "https://github.com/twoventi/twenties-cleaning/releases/tag/v0.0.1"}))
    st, upd = req("POST", "/api/update_check", {}, csrf)
    check("versione più vecchia ignorata", st == 200 and upd.get("update") is False and upd.get("current") == "1.1.0")
    st, _ = req("POST", "/api/settings", {"updates": False}, csrf)
    scan_root = os.path.join(tmp, "OneDrive")
    accent = os.path.join(scan_root, "Cartella èà")
    os.makedirs(os.path.join(accent, "cache"), exist_ok=True)
    with open(os.path.join(accent, "cache", "nota.log"), "wb") as f:
        f.write(b"x" * 4096)
    with open(os.path.join(accent, "appunti.txt"), "w", encoding="utf-8") as f:
        f.write("ciao")
    st, started = req("POST", "/api/start", {"roots": [scan_root], "dups": False, "arch": False, "minmb": 1}, csrf)
    check("analisi senza account", st == 200 and "error" not in started, str(started))
    phase = ""
    for _ in range(40):
        st, phase_body = req("GET", "/api/status")
        phase = phase_body.get("phase")
        if phase in ("done", "idle"):
            break
        time.sleep(0.25)
    check("analisi conclusa", phase == "done" and not phase_body.get("error"), str(phase_body))
    st, mp = req("GET", "/api/map")
    blob = json.dumps(mp, ensure_ascii=False)
    check("mappa con percorso accentato", st == 200 and "Cartella èà" in blob and mp.get("roots"))
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
    check("modalità senza finestra", me.get("app") == "Twenties" and me.get("version") == "1.1.0" and me.get("window") is False)
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    c.request("GET", "/auth/finish?t=not-a-real-ticket", headers={"Host": f"127.0.0.1:{PORT}"})
    rr = c.getresponse(); loc = rr.getheader("Location") or ""; rr.read()
    check("passaggio Google senza ticket rifiutato", rr.status == 302 and "google_fail" in loc)

    def once(port):
        home = tempfile.mkdtemp()
        e = dict(os.environ, TC_PORT=str(port), TC_HEADLESS="1", HOME=home, USERPROFILE=home, APPDATA=home, XDG_DATA_HOME=home,
                 BROWSER="true", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        p = subprocess.Popen([sys.executable, APP, "--headless"], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            err = p.communicate(timeout=25)[1]
        except subprocess.TimeoutExpired:
            p.kill(); p.communicate()
            raise SystemExit("una copia in più non è terminata")
        return p.returncode, text(err)

    code, err = once(PORT)
    check("seconda copia non resta accesa", code == 0 and "aperto" in err, "codice %s\n%s" % (code, err.strip()))
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
