#!/usr/bin/env python3
"""Twenties Cleaning - analizza lo spazio del PC / Mac: cartelle, giochi, doppioni, archivi gia' estratti.
Python 3.8+ e pywebview per la finestra (se manca, si apre il browser). Elimina solo su tua conferma e solo verso il Cestino.
Avvio:  python3 src/twenties_cleaning.py   -> finestra dell'app (accesso con account).
Windows, macOS e Linux. Vedi LEGGIMI per Google, HTTPS e posta."""
import os, re, sys, json, time, stat, heapq, string, shutil, zipfile, tarfile, hashlib, secrets, threading, subprocess, webbrowser
import errno, socket, sqlite3, hmac, base64, ssl, smtplib, traceback, urllib.request, urllib.parse, urllib.error
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try:  # credenziali Google incorporate dalla build ufficiale (file generato da GitHub Actions, mai nel repository)
    import _google_config as _GC
except Exception:
    _GC = None

sys.setrecursionlimit(5000)
GAME, JUNK, LOW, MID, HIGH = "Gioco", "Scarto", "Importanza bassa", "Importanza media", "Importanza elevata"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
MINFOLDER, TOPN, YEAR = 100 << 20, 400, 365 * 86400
WINDIR = os.environ.get("SystemRoot", "").lower() or "?"
if IS_WIN:
    SYS = (WINDIR,)
    SKIPDIRS = ()
    SYSDIRS = {WINDIR}
elif IS_MAC:
    SYS = ("/system", "/usr", "/bin", "/sbin", "/private/var/db", "/library/apple", "/cores", "/dev")
    SKIPDIRS = ("/System/Volumes", "/Volumes", "/dev", "/private/var/vm", "/cores", "/.Spotlight-V100", "/.fseventsd")
    SYSDIRS = {"/system", "/usr", "/bin", "/sbin", "/private"}
else:
    SYS = ("/usr", "/bin", "/sbin", "/lib", "/proc", "/sys", "/dev", "/run", "/snap")
    SKIPDIRS = ("/proc", "/sys", "/dev", "/run")
    SYSDIRS = set()
SYSF = SYS if (IS_WIN or IS_MAC) else ()
PROGDIRS = {os.environ.get(k, "").lower() for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData")} - {""}
if IS_MAC:
    PROGDIRS = {"/applications"}
PROGMSG = ("programma installato (si rimuove trascinando l'app nel Cestino)" if IS_MAC
           else "programma installato (si rimuove dalle Impostazioni)")

JUNK_DIRS = {"temp", "tmp", "cache", "caches", ".cache", "__pycache__", "node_modules", "crashpad", "code cache",
             "gpucache", "$recycle.bin", ".trash", ".trashes", "softwaredistribution", "windows.old", "$windows.~bt",
             "$patchcache$", "crashdumps", "inetcache", "logs", "thumbnails", "shadercache", "d3dscache", "deriveddata",
             ".fseventsd", ".spotlight-v100", ".documentrevisions-v100"}
JUNK_EXT = {".tmp", ".temp", ".log", ".bak", ".old", ".dmp", ".cache", ".crdownload", ".part", ".swp", ".etl", ".chk"}
INSTALLER_EXT = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"}
HIGH_EXT = {".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".txt", ".md", ".tex", ".psd",
            ".ai", ".indd", ".dwg", ".blend", ".kdbx", ".pst", ".sqlite", ".db", ".py", ".js", ".ts", ".java", ".cs",
            ".cpp", ".c", ".h", ".go", ".rs", ".pem", ".key", ".jpg", ".jpeg", ".png", ".heic", ".raw", ".cr2",
            ".nef", ".arw", ".dng", ".pages", ".numbers", ".keynote", ".sketch", ".heif"}
DISK_EXT = {".iso", ".vmdk", ".vdi", ".vhd", ".vhdx", ".img", ".qcow2", ".ova"}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".mp3", ".wav", ".flac", ".m4a", ".aac",
             ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
IGNORE_FILES = {"pagefile.sys", "hiberfil.sys", "swapfile.sys"}
GAME_FILES = {"steam_api.dll", "steam_api64.dll", "unityplayer.dll", "unitycrashhandler64.exe", "unitycrashhandler32.exe",
              "gameassembly.dll", "galaxy64.dll", "eossdk-win64-shipping.dll", "easyanticheat.exe", "data.win",
              "ue4prerequisitesinstaller.exe", "ueprereqsetup_x64.exe"}
GAME_DIRS = {"monobleedingedge", "il2cpp_data", "easyanticheat", "battleye"}
GAME_RE = re.compile(r"^(.*?[\\/](?:steamapps[\\/]common|epic games|gog games|gog galaxy[\\/]games|riot games|"
                     r"ubisoft game launcher[\\/]games|ea games|origin games|xboxgames|games)[\\/][^\\/]+)", re.I)
NOTGAME = {"launcher", "directxredist", "epic online services", "ubisoft game launcher", "steamworks shared"}

S = {"owner": None, "phase": "idle", "count": 0, "current": "", "done": 0, "total": 0, "stop": False, "error": "", "res": None, "denied": 0}
C = {"groots": set(), "anc": set()}


def ecat(x):
    return 0 if x in JUNK_EXT else 1 if x in HIGH_EXT else 2 if x in MEDIA_EXT else 3 if x in DISK_EXT else 4


def marker_root(d):
    i = d.lower().rfind(os.sep + "binaries")
    r = os.path.dirname(d[:i]) if i > 0 else d
    return r if os.path.dirname(r) != r else d


def walk(roots, minb):
    dirs, markers, sizes, top, archs, n = {}, set(), {}, [], [], 0
    stack = list(roots)
    while stack and not S["stop"]:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            S["denied"] += 1
            continue
        st, names, subs = [0, 0, 0, 0, 0, 0, 0], set(), set()
        nodup = d.lower().startswith(SYS)
        with it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    s = e.stat(follow_symlinks=False)
                    if getattr(s, "st_file_attributes", 0) & 0x400:
                        continue
                    nm = e.name.lower()
                    if stat.S_ISDIR(s.st_mode):
                        subs.add(nm)
                        if e.path not in SKIPDIRS:
                            stack.append(e.path)
                        continue
                    if not stat.S_ISREG(s.st_mode) or nm in IGNORE_FILES:
                        continue
                    sz = s.st_size
                    ext = os.path.splitext(nm)[1]
                    st[ecat(ext)] += sz
                    if ext in ARCH_EXT or VOL_RE.match(ext):
                        archs.append((e.path, sz, s.st_mtime))
                    st[6] += 1
                    st[5] = max(st[5], s.st_mtime)
                    names.add(nm)
                    n += 1
                    item = (sz, e.path, s.st_mtime)
                    if len(top) < TOPN:
                        heapq.heappush(top, item)
                    elif sz > top[0][0]:
                        heapq.heapreplace(top, item)
                    if sz >= minb and not nodup and s.st_nlink < 2:
                        sizes.setdefault(sz, []).append(e.path)
                except OSError:
                    continue
        dirs[d] = st
        if names & GAME_FILES or subs & GAME_DIRS:
            markers.add(marker_root(d))
        S["count"], S["current"] = n, d
    return dirs, markers, sizes, top, archs


def special(p):
    low, base = p.lower(), os.path.basename(p).lower()
    if p in C["groots"]:
        return GAME, "gioco rilevato (cartella di launcher o file del motore di gioco)"
    if base in JUNK_DIRS:
        return JUNK, "cache, temporanei o log: di solito eliminabili"
    if low in SYSDIRS or base == "system volume information":
        return HIGH, "sistema: non toccare"
    if os.path.dirname(low) in PROGDIRS and p not in C["anc"]:
        return MID, PROGMSG
    return None


def by_content(p, t):
    tot, old = sum(t[:5]) or 1, time.time() - t[5] > 2 * YEAR
    if t[0] >= .5 * tot:
        return JUNK, "prevalentemente file temporanei, log o backup"
    if t[1] >= .3 * tot:
        return HIGH, "documenti, foto o progetti personali"
    if os.path.basename(p).lower() == "downloads":
        return LOW, "cartella Download: spesso roba riscaricabile, controlla"
    if t[3] >= .5 * tot:
        return LOW, "immagini disco, ISO o macchine virtuali"
    if t[2] >= .5 * tot:
        return (LOW, "video/audio/archivi non toccati da 2+ anni") if old else (MID, "video, audio o archivi")
    return (LOW, "contenuto misto, non toccato da 2+ anni") if old else (MID, "contenuto misto, usato di recente")


def report(p, out, tot, kids):
    t = tot[p]
    size = sum(t[:5])
    if size < MINFOLDER:
        return
    sp = special(p)
    sub = [(sum(tot[c][:5]), c) for c in kids.get(p, ())]
    big = [c for s, c in sub if s >= MINFOLDER]
    spread = size - sum(s for s, c in sub if s >= MINFOLDER)
    if sp or ((not big or spread >= .4 * size) and p not in C["anc"]):
        cat, why = sp or by_content(p, t)
        out.append({"path": p, "name": os.path.basename(p) or p, "size": size, "files": t[6], "mtime": t[5],
                    "cat": cat, "why": why})
    else:
        for c in big:
            report(c, out, tot, kids)


def fclass(path, mtime):
    q = os.path.dirname(path)
    while True:
        if q in C["groots"]:
            return GAME, "file di un gioco"
        nq = os.path.dirname(q)
        if nq == q:
            break
        q = nq
    low = path.lower()
    parts, ext = set(re.split(r"[\\/]", low)), os.path.splitext(low)[1]
    old = time.time() - mtime > 2 * YEAR
    if parts & JUNK_DIRS or ext in JUNK_EXT:
        return JUNK, "temporaneo, cache, log o backup"
    if ext in INSTALLER_EXT and parts & {"downloads", "download"}:
        return JUNK, "installer scaricato, riscaricabile"
    if SYSF and low.startswith(SYSF):
        return HIGH, "file di sistema"
    if ext in HIGH_EXT:
        return HIGH, "documento, foto o progetto personale"
    if ext in DISK_EXT:
        return LOW, "immagine disco/ISO, di solito riscaricabile"
    if ext in MEDIA_EXT:
        return (LOW, "media/archivio vecchio o in Download") if old or parts & {"downloads"} else (MID, "video, audio o archivio")
    return (LOW, "tipo sconosciuto, non modificato da 2+ anni") if old else (MID, "tipo sconosciuto, usato di recente")


def build(dirs, markers, top):
    tot, kids = {p: list(v) for p, v in dirs.items()}, {}
    for p in sorted(dirs, key=lambda x: x.count(os.sep), reverse=True):
        par = os.path.dirname(p)
        if par != p and par in tot:
            kids.setdefault(par, []).append(p)
            a, b = tot[par], tot[p]
            for i in (0, 1, 2, 3, 4, 6):
                a[i] += b[i]
            a[5] = max(a[5], b[5])
    groots = set(markers)
    for d in dirs:
        m = GAME_RE.match(d)
        if m and os.path.basename(m.group(1)).lower() not in NOTGAME:
            groots.add(m.group(1))
    anc = set()
    for r in groots:
        q = os.path.dirname(r)
        while q not in anc:
            anc.add(q)
            nq = os.path.dirname(q)
            if nq == q:
                break
            q = nq
    C["groots"], C["anc"] = groots, anc
    folders = []
    for r in [p for p in tot if os.path.dirname(p) == p or os.path.dirname(p) not in tot]:
        report(r, folders, tot, kids)
    folders = sorted(folders, key=lambda x: -x["size"])[:300]
    files = []
    for sz, p, m in sorted(top, reverse=True):
        c, w = fclass(p, m)
        files.append({"path": p, "name": os.path.basename(p), "size": sz, "mtime": m, "files": None, "cat": c, "why": w})
    totals = {}
    for f in folders:
        totals[f["cat"]] = totals.get(f["cat"], 0) + f["size"]
    return {"folders": folders, "files": files, "totals": totals}


def hsh(path, size, full):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        if full:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
        else:
            h.update(f.read(65536))
            if size > 131072:
                f.seek(-65536, 2)
                h.update(f.read(65536))
    return h.digest()


def find_dups(sizes):
    groups = [(sz, p) for sz, p in sizes.items() if len(p) > 1]
    S.update(phase="dups", total=sum(len(p) for _, p in groups), done=0)
    res = []
    for sz, paths in sorted(groups, reverse=True):
        if S["stop"]:
            break
        part = {}
        for p in paths:
            try:
                part.setdefault(hsh(p, sz, False), []).append(p)
            except OSError:
                pass
            S["done"] += 1
        for g in part.values():
            if len(g) < 2:
                continue
            full = {}
            for p in g:
                try:
                    full.setdefault(hsh(p, sz, True), []).append(p)
                except OSError:
                    pass
            for h in full.values():
                if len(h) > 1:
                    ps = sorted(h)
                    mt = [os.path.getmtime(x) if os.path.exists(x) else 0 for x in ps]
                    res.append({"size": sz, "paths": ps, "mt": mt, "wasted": sz * (len(h) - 1)})
    return sorted(res, key=lambda g: -g["wasted"])[:300]


VOL_RE = re.compile(r"\.r\d\d$")
ARCH_EXT = {".rar", ".zip", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
NW = {"creationflags": 0x08000000} if IS_WIN else {}
_TOOL = []


def tool():
    """Cerca 7-Zip o UnRAR (servono solo per leggere il contenuto di RAR/7z)."""
    if not _TOOL:
        found = None
        for kind, n in [("7z", "7z"), ("7z", "7zz"), ("7z", "7za"), ("unrar", "unrar"), ("unrar", "UnRAR")]:
            x = shutil.which(n)
            if x:
                found = (kind, x)
                break
        if not found and IS_WIN:
            for pf in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
                for kind, rel in (("7z", r"7-Zip\7z.exe"), ("unrar", r"WinRAR\UnRAR.exe")):
                    x = os.path.join(pf, rel)
                    if pf and os.path.isfile(x):
                        found = (kind, x)
                        break
                if found:
                    break
        _TOOL.append(found)
    return _TOOL[0]


def list_cmd(p):
    t = tool()
    if not t:
        return None
    kind, exe = t
    try:
        if kind == "7z":
            for extra in (["-sccUTF-8"], []):
                r = subprocess.run([exe, "l", "-slt", "-ba"] + extra + [p], capture_output=True, timeout=120, **NW)
                if r.returncode in (0, 1):
                    break
            else:
                return None
            kp, ks, kd, sep = "Path", "Size", "Folder", " = "
        else:
            r = subprocess.run([exe, "lt", "-idq", p], capture_output=True, timeout=120, **NW)
            if r.returncode != 0:
                return None
            kp, ks, kd, sep = "Name", "Size", "Type", ": "
        ents, cur = [], {}
        for line in r.stdout.decode("utf-8", "replace").splitlines() + [""]:
            if not line.strip():
                isdir = cur.get(kd, "") in ("+", "Directory") or cur.get("Attributes", "")[:1] == "D"
                if cur.get(kp) and not isdir:
                    ents.append((cur[kp], int(cur.get(ks) or 0)))
                cur = {}
            elif sep in line:
                k, v = line.strip().split(sep, 1)
                cur[k.strip()] = v.strip()
        return ents or None
    except Exception:
        return None


def list_archive(p):
    low = p.lower()
    try:
        if low.endswith(".zip"):
            with zipfile.ZipFile(p) as z:
                return [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()] or None
        if low.endswith((".tar", ".gz", ".tgz", ".bz2", ".xz")):
            if os.path.getsize(p) > 1 << 30:
                return None
            with tarfile.open(p) as t:
                return [(m.name, m.size) for m in t if m.isfile()] or None
    except Exception:
        pass
    return list_cmd(p) if low.endswith((".rar", ".7z", ".zip")) else None


def verify(entries, bases):
    ents = []
    for n, s in entries:
        n = n.replace("\\", "/").strip("/")
        if n and ".." not in n.split("/") and not re.match(r"^[A-Za-z]:", n):
            ents.append((n, s))
    if not ents:
        return 0, bases[0], 0
    sample, best = ents[::max(1, len(ents) // 1500)], (0, bases[0])
    for b in bases:
        ok = 0
        for n, s in sample:
            try:
                if os.path.getsize(os.path.join(b, *n.split("/"))) == s:
                    ok += 1
            except OSError:
                pass
        if ok / len(sample) > best[0]:
            best = (ok / len(sample), b)
    return best[0], best[1], len(ents)


def find_archives(archs):
    mains = []
    for p, sz, mt in archs:
        d, nm = os.path.split(p)
        m = re.search(r"\.part0*(\d+)\.rar$", nm.lower())
        if d.lower().startswith(SYS) or VOL_RE.search(nm.lower()) or (m and int(m.group(1)) != 1) or sz < 1 << 20:
            continue
        mains.append((p, sz, mt))
    mains = sorted(mains, key=lambda a: -a[1])[:400]
    S.update(phase="arch", done=0, total=len(mains))
    out, cache, t0 = [], {}, time.time()
    for p, sz, mt in mains:
        if S["stop"] or time.time() - t0 > 300:
            break
        S["done"] += 1
        d, nm = os.path.split(p)
        stem = re.sub(r"(\.part0*1)?(\.tar)?\.[^.]+$", "", nm, flags=re.I)
        if d not in cache:
            try:
                cache[d] = os.listdir(d)
            except OSError:
                cache[d] = []
        vols = [[p, sz]]
        if nm.lower().endswith(".rar"):
            pat = re.compile(re.escape(stem) + r"(\.part\d+\.rar|\.r\d\d)", re.I)
            for f in cache[d]:
                if f != nm and pat.fullmatch(f):
                    try:
                        vols.append([os.path.join(d, f), os.path.getsize(os.path.join(d, f))])
                    except OSError:
                        pass
        bases = [d, os.path.join(d, stem)]
        ents = list_archive(p)
        if ents:
            ratio, where, n = verify(ents, bases)
            if ratio >= .98:
                lvl, why = "ok", f"Tutti i {n} file dell'archivio sono già presenti in: {where}"
            elif ratio >= .6:
                lvl, why = "part", f"Estratto solo in parte ({ratio:.0%}) in: {where}. Controlla prima di eliminare"
            else:
                continue
        elif nm.lower().endswith((".rar", ".7z", ".zip")) and os.path.isdir(bases[1]):
            try:
                with os.scandir(bases[1]) as it:
                    if next(it, None) is None:
                        continue
            except OSError:
                continue
            lvl, n, where = "guess", 0, bases[1]
            why = "Esiste una cartella con lo stesso nome, ma non riesco a leggere l'archivio (installa 7-Zip o WinRAR): verifica a mano"
        else:
            continue
        out.append({"path": p, "name": nm, "size": sum(v[1] for v in vols), "vols": vols, "level": lvl, "why": why,
                    "where": where, "files": n, "mtime": mt})
    return sorted(out, key=lambda a: (a["level"] != "ok", -a["size"]))


def run(roots, dups, arch, minmb):
    try:
        dirs, markers, sizes, top, archs = walk(roots, minmb << 20)
        S["phase"] = "agg"
        res = build(dirs, markers, top)
        res["dups"] = find_dups(sizes) if dups and not S["stop"] else []
        res["wasted"] = sum(g["wasted"] for g in res["dups"])
        res["archives"] = find_archives(archs) if arch and not S["stop"] else []
        res["arch_total"] = sum(a["size"] for a in res["archives"] if a["level"] == "ok")
        res["disks"], res["denied"], res["tool"] = drives(), S["denied"], bool(tool())
        C["ok"] = {f["path"]: f["size"] for f in res["files"]}
        for g in res["dups"]:
            for p in g["paths"]:
                C["ok"][p] = g["size"]
        for a in res["archives"]:
            for p, s in a["vols"]:
                C["ok"][p] = s
        S["res"] = res
    except Exception:
        traceback.print_exc()
        S["error"] = "Errore interno durante l'analisi"
    S["phase"] = "done"


def drives():
    roots = ["/"]
    if IS_WIN:
        import ctypes
        roots = [f"{L}:\\" for L in string.ascii_uppercase
                 if os.path.exists(f"{L}:\\") and ctypes.windll.kernel32.GetDriveTypeW(f"{L}:\\") == 3]
    elif IS_MAC:
        try:
            roots += [p for p in (os.path.join("/Volumes", n) for n in sorted(os.listdir("/Volumes")))
                      if os.path.ismount(p) and not os.path.islink(p)]
        except OSError:
            pass
    out = []
    for r in roots:
        try:
            u = shutil.disk_usage(r)
            out.append({"path": r, "total": u.total, "used": u.used, "free": u.free})
        except OSError:
            out.append({"path": r, "total": 0, "used": 0, "free": 0})
    return out


def reveal(p):
    """Mostra nel file manager. Solo percorsi assoluti esistenti; nessuna shell, argomenti in lista."""
    if not os.path.isabs(p) or "\0" in p or not os.path.exists(p):
        return
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(p)] if os.path.isfile(p) else ["explorer", os.path.normpath(p)])
    elif IS_MAC:
        subprocess.Popen(["open", "-R", "--", p])
    else:
        subprocess.Popen(["xdg-open", p if os.path.isdir(p) else os.path.dirname(p)])


def trash_many(paths):
    """Sposta nel Cestino (recuperabile). Se il Cestino non e' disponibile NON elimina nulla."""
    if not paths:
        return
    try:
        if IS_WIN:
            ps = ("Add-Type -AssemblyName Microsoft.VisualBasic;$i=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
                  "foreach($p in $i){try{[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,'OnlyErrorDialogs','SendToRecycleBin')}catch{}}")
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           input=json.dumps(paths).encode(), capture_output=True, timeout=900, **NW)
        elif IS_MAC:
            scr = ['on run argv', 'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)', 'end run']
            for p in paths:
                subprocess.run(["osascript"] + [x for l in scr for x in ("-e", l)] + [p], capture_output=True, timeout=120)
        else:
            exe = shutil.which("gio") and ["gio", "trash"] or shutil.which("trash-put") and ["trash-put"]
            for p in paths:
                if exe:
                    subprocess.run(exe + [p], capture_output=True, timeout=120)
    except Exception:
        pass


def prune(done):
    r, ds = S["res"], set(done)
    r["files"] = [f for f in r["files"] if f["path"] not in ds]
    r["archives"] = [a for a in r["archives"] if a["path"] not in ds]
    gs = []
    for g in r["dups"]:
        k = [i for i, p in enumerate(g["paths"]) if p not in ds]
        if len(k) > 1:
            g["paths"], g["mt"] = [g["paths"][i] for i in k], [g["mt"][i] for i in k]
            g["wasted"] = g["size"] * (len(k) - 1)
            gs.append(g)
    r["dups"], r["wasted"] = gs, sum(g["wasted"] for g in gs)
    r["arch_total"] = sum(a["size"] for a in r["archives"] if a["level"] == "ok")
    for p in ds:
        C["ok"].pop(p, None)


def do_trash(paths):
    ok, bad, req = [], [], []
    for p in paths:
        sz = C["ok"].get(p)
        try:
            if sz is None:
                bad.append([p, "non autorizzato"])
            elif os.path.islink(p):
                bad.append([p, "collegamento simbolico: non toccato"])
            elif not os.path.isfile(p) or os.path.getsize(p) != sz:
                bad.append([p, "il file è cambiato o non esiste più"])
            else:
                req.append(p)
        except OSError as e:
            bad.append([p, str(e)])
    rs = set(req)
    for g in S["res"]["dups"]:  # sicurezza: di un gruppo di doppioni resta sempre almeno una copia
        if set(g["paths"]) <= rs:
            for p in g["paths"]:
                rs.discard(p)
                bad.append([p, "tenuta almeno una copia di sicurezza"])
    trash_many(sorted(rs))
    done = [p for p in sorted(rs) if not os.path.exists(p)]
    bad += [[p, "Cestino non disponibile o operazione non riuscita"] for p in sorted(rs) if os.path.exists(p)]
    freed = sum(C["ok"].get(p, 0) for p in done)
    prune(done)
    return {"done": done, "failed": bad, "freed": freed}


# ====================================================================================
#  Account, sicurezza e server web (solo 127.0.0.1)
# ====================================================================================
APP = "Twenties Cleaning"
VERSION = "1.0.3"
HOST = "127.0.0.1"
PLATFORM = "win" if IS_WIN else "mac" if IS_MAC else "linux"
PORT, SCHEME, BASE, TLS_ON = 8765, "http", "", False
SN, PN = "tc_s", "tc_p"            # nomi cookie (con HTTPS diventano __Host-...)
IDLE, ABSOLUTE, RESET_TTL = 2 * 3600, 24 * 3600, 15 * 60
KEY = secrets.token_bytes(32)      # chiave HMAC dei token CSRF (solo in memoria)
SC_N = 1 << 15                     # costo scrypt (~32 MB di RAM per hash)
PWSEM = threading.BoundedSemaphore(4)
DBL, CON = threading.Lock(), None
G_ID = G_SECRET = ""
OAUTH, OAL = {}, threading.Lock()
HANDOFF, HL = {}, threading.Lock()  # ticket monouso: il browser di sistema non condivide i cookie con la finestra
WINDOW, WINDOW_MODE = None, False
MODE = "window"                     # window | browser | headless
DONE_PAGE = '<!doctype html><meta charset="utf-8"><title>Twenties Cleaning</title><body><h2>%s</h2><p>%s</p></body>'
TOKRE, PRERE = re.compile(r"[A-Za-z0-9_-]{43}"), re.compile(r"[A-Za-z0-9_-]{32}")
TIKRE = re.compile(r"[A-Za-z0-9_-]{16,80}")
EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+")
COMMON = {"password", "password1", "password123", "1234567890", "12345678910", "qwertyuiop", "iloveyou123",
          "passwordpassword", "letmein1234", "administrator", "0123456789", "qwerty12345", "twentiescleaning"}
RUNNING = ("scan", "agg", "dups", "arch")
START_LOCK = threading.Lock()


def quiet_streams():
    """In un'app senza terminale (PyInstaller --windowed su Windows) stdout/stderr sono None: print() andrebbe in errore.
    I messaggi sono in italiano: forzo UTF-8, altrimenti su Windows la console (cp1252) storpia le lettere accentate."""
    for n in ("stdout", "stderr"):
        stream = getattr(sys, n)
        if stream is None:
            setattr(sys, n, open(os.devnull, "w", encoding="utf-8"))
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def log_to_file(d):
    """App impacchettata: i messaggi vanno in un file di log nella cartella dati (solo sul tuo computer)."""
    if not getattr(sys, "frozen", False):
        return
    p = os.path.join(d, "app.log")
    try:
        if os.path.getsize(p) > 1 << 20:
            os.replace(p, p + ".old")
    except OSError:
        pass
    try:
        sys.stdout = sys.stderr = open(p, "a", encoding="utf-8", buffering=1)
    except OSError:
        pass


def data_dir():
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif IS_MAC:
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, "TwentiesCleaning")
    os.makedirs(d, exist_ok=True)
    if not IS_WIN:
        os.chmod(d, 0o700)
    return d


def load_env(d):
    """Segreti (Google, SMTP) solo da variabili d'ambiente o dal file .env nella cartella dati, mai nel codice."""
    p = os.path.join(d, ".env")
    if not os.path.isfile(p):
        return
    if not IS_WIN:
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------- database (query sempre parametrizzate)
def init_db(path):
    global CON
    CON = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    CON.row_factory = sqlite3.Row
    CON.execute("PRAGMA foreign_keys=ON")
    CON.execute("PRAGMA journal_mode=WAL")
    CON.execute("PRAGMA secure_delete=ON")
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, pw TEXT,
        google_sub TEXT UNIQUE, name TEXT, created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created INTEGER NOT NULL, last INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resets(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);""")
    if not IS_WIN:
        os.chmod(path, 0o600)
    now = int(time.time())
    dbx("DELETE FROM sessions WHERE last<? OR created<?", (now - IDLE, now - ABSOLUTE))
    dbx("DELETE FROM resets WHERE expires<? OR used=1", (now,))


def dbx(sql, a=()):
    with DBL:
        cur = CON.execute(sql, a)
        return cur.fetchall(), cur.rowcount, cur.lastrowid


# ---------------------------------------------------------------- password (scrypt + sale casuale)
def hash_pw(pw):
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=SC_N, r=8, p=1, maxmem=128 << 20, dklen=32)
    return f"scrypt${SC_N}${salt.hex()}${h.hex()}"


def check_pw(pw, stored):
    try:
        _, n, salt, h = stored.split("$")
        n = int(n)
        if n > 1 << 17:
            return False
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=n, r=8, p=1, maxmem=256 << 20, dklen=32)
        return hmac.compare_digest(calc, bytes.fromhex(h))
    except Exception:
        return False


DUMMY = None  # hash finto: stesso tempo di calcolo anche se l'email non esiste


def eq(a, b):
    return hmac.compare_digest(str(a).encode(), str(b).encode())


def norm_email(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if len(v) <= 254 and EMAIL_RE.fullmatch(v) else None


def pw_error(pw, email=""):
    if not isinstance(pw, str):
        return "Password non valida."
    if len(pw) < 10:
        return "La password deve avere almeno 10 caratteri."
    if len(pw) > 128:
        return "La password può avere al massimo 128 caratteri."
    if pw.lower() in COMMON or len(set(pw)) < 4 or (email and pw.lower() == email):
        return "Password troppo semplice. Scegline una più originale."
    return None


def clean_name(v):
    return re.sub(r"[\x00-\x1f\x7f<>]", "", str(v or ""))[:80].strip() or None


# ---------------------------------------------------------------- rate limiting (finestra scorrevole in memoria)
class Limiter:
    def __init__(self):
        self.h, self.l = {}, threading.Lock()

    def count(self, key, window):
        now = time.time()
        with self.l:
            q = [t for t in self.h.get(key, ()) if now - t < window]
            self.h[key] = q
            return len(q)

    def add(self, key):
        with self.l:
            self.h.setdefault(key, []).append(time.time())
            if len(self.h) > 5000:
                cut = time.time() - 3600
                self.h = {k: v for k, v in self.h.items() if v and v[-1] > cut}

    def clear(self, key):
        with self.l:
            self.h.pop(key, None)


RL = Limiter()


def csrf_for(binding):
    return hmac.new(KEY, binding.encode(), hashlib.sha256).hexdigest()


def new_session(uid):
    tok, now = secrets.token_urlsafe(32), int(time.time())
    sid = hashlib.sha256(tok.encode()).hexdigest()
    dbx("INSERT INTO sessions(id,user_id,created,last) VALUES(?,?,?,?)", (sid, uid, now, now))
    dbx("DELETE FROM sessions WHERE user_id=? AND id NOT IN (SELECT id FROM sessions WHERE user_id=? ORDER BY created DESC LIMIT 10)", (uid, uid))
    return tok, sid


def send_mail(to, link):
    host = os.environ.get("SMTP_HOST")
    if host:
        try:
            m = EmailMessage()
            m["Subject"], m["To"] = f"Reimposta la password - {APP}", to
            m["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "noreply@localhost"
            m.set_content(f"Hai chiesto di reimpostare la password di {APP}.\n\nApri questo link (valido 15 minuti, utilizzabile una sola volta):\n{link}\n\nSe non sei stato tu, ignora questo messaggio.")
            port, ctx = int(os.environ.get("SMTP_PORT", "587")), ssl.create_default_context()
            srv = smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) if port == 465 else smtplib.SMTP(host, port, timeout=15)
            with srv:
                if port != 465:
                    srv.starttls(context=ctx)
                if os.environ.get("SMTP_USER"):
                    srv.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
                srv.send_message(m)
            return
        except Exception as e:
            print("Invio email non riuscito:", type(e).__name__)
    try:
        if sys.stdout.isatty():  # solo in un vero terminale, mai in un file di log
            print(f"\n[{APP}] Link per reimpostare la password di {to} (valido 15 minuti, monouso):\n{link}\n")
    except Exception:
        pass


def google_exchange(code, verifier, nonce):
    body = urllib.parse.urlencode({"code": code, "client_id": G_ID, "client_secret": G_SECRET, "grant_type": "authorization_code",
                                   "redirect_uri": f"{BASE}/auth/google/callback", "code_verifier": verifier}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as r:
        tok = json.loads(r.read(1 << 20))
    seg = tok["id_token"].split(".")[1]
    c = json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))
    aud = c.get("aud")
    if (c.get("iss") not in ("https://accounts.google.com", "accounts.google.com") or G_ID not in (aud if isinstance(aud, list) else [aud])
            or float(c.get("exp", 0)) < time.time() or not eq(c.get("nonce", ""), nonce)
            or str(c.get("email_verified")).lower() != "true" or not c.get("sub")):
        raise ValueError("id_token non valido")
    em = norm_email(c.get("email"))
    if not em:
        raise ValueError("email non valida")
    return {"sub": str(c["sub"])[:64], "email": em, "name": clean_name(c.get("name"))}


def google_user(g):
    rows, _, _ = dbx("SELECT id FROM users WHERE google_sub=?", (g["sub"],))
    if rows:
        return rows[0]["id"]
    rows, _, _ = dbx("SELECT id FROM users WHERE email=?", (g["email"],))
    if rows:  # email già presente (mai verificata): Google ne prova il possesso, quindi la password vecchia viene rimossa
        uid = rows[0]["id"]
        dbx("UPDATE users SET google_sub=?, pw=NULL, name=COALESCE(name,?) WHERE id=?", (g["sub"], g["name"], uid))
        dbx("DELETE FROM sessions WHERE user_id=?", (uid,))
        dbx("DELETE FROM resets WHERE user_id=?", (uid,))
        return uid
    return dbx("INSERT INTO users(email,google_sub,name,created) VALUES(?,?,?,?)", (g["email"], g["sub"], g["name"], int(time.time())))[2]


def allowed_paths():
    r, ok = S["res"] or {}, set(C.get("ok", {}))
    for k in ("folders", "files"):
        ok |= {x["path"] for x in r.get(k, [])}
    for a in r.get("archives", []):
        ok |= {a["path"], a["where"]}
    return ok


class H(BaseHTTPRequestHandler):
    server_version, sys_version, timeout = "TwentiesCleaning", "", 30

    def log_message(self, *a):
        pass

    # ---------- risposte
    def send(self, code, body, ctype="application/json", cookies=(), headers=(), nonce=None):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        csp = ("default-src 'none'; frame-ancestors 'none'" if not nonce else
               f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; style-src-attr 'unsafe-inline'; "
               "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")
        for k, v in (("Content-Security-Policy", csp), ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
                     ("Referrer-Policy", "no-referrer"), ("Cross-Origin-Opener-Policy", "same-origin"),
                     ("Cross-Origin-Resource-Policy", "same-origin"),
                     ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")):
            self.send_header(k, v)
        if TLS_ON:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for c in cookies:
            self.send_header("Set-Cookie", c)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    def jout(self, obj, code=200, cookies=(), headers=()):
        self.send(code, json.dumps(obj), cookies=cookies, headers=headers)

    def err(self, code, msg, **kw):
        self.jout({"error": msg}, code, **kw)

    def redirect(self, loc, cookies=()):
        self.send(302, b"", "text/plain", cookies=cookies, headers=[("Location", loc)])

    def mk(self, name, val, age=None):
        s = f"{name}={val}; Path=/; HttpOnly; SameSite=Lax" + (f"; Max-Age={age}" if age is not None else "")
        return s + ("; Secure" if TLS_ON else "")

    # ---------- richiesta
    def jar(self):
        try:
            return {k: m.value for k, m in SimpleCookie(self.headers.get("Cookie", "")).items()}
        except Exception:
            return {}

    def host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def origin_ok(self):
        return (self.headers.get("Origin") == f"{SCHEME}://127.0.0.1:{PORT}"
                and self.headers.get("Sec-Fetch-Site") in (None, "same-origin")
                and self.headers.get("Host") == f"127.0.0.1:{PORT}")

    def pre(self):
        p = self.jar().get(PN, "")
        return p if PRERE.fullmatch(p) else ""

    def pre_cookie(self):
        p = self.pre()
        return (p, []) if p else (lambda n: (n, [self.mk(PN, n, 30 * 86400)]))(secrets.token_urlsafe(24))

    def session(self):
        if hasattr(self, "_sess"):
            return self._sess
        self._sess, tok = None, self.jar().get(SN, "")
        if TOKRE.fullmatch(tok):
            sid, now = hashlib.sha256(tok.encode()).hexdigest(), int(time.time())
            rows, _, _ = dbx("SELECT s.created, s.last, u.id, u.email, u.name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?", (sid,))
            if rows:
                r = rows[0]
                if now - r["last"] > IDLE or now - r["created"] > ABSOLUTE:
                    dbx("DELETE FROM sessions WHERE id=?", (sid,))
                else:
                    if now - r["last"] > 60:
                        dbx("UPDATE sessions SET last=? WHERE id=?", (now, sid))
                    self._sess = {"sid": sid, "uid": r["id"], "email": r["email"], "name": r["name"]}
        return self._sess

    def binding(self):
        s = self.session()
        return ("s:" + s["sid"]) if s else ("p:" + self.pre() if self.pre() else None)

    def body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("lunghezza")
        if n < 0 or n > 2 << 20:
            raise OverflowError
        d = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(d, dict):
            raise ValueError("json")
        return d

    def other(self):
        self.send(405, b"", "text/plain", headers=[("Allow", "GET, POST")])

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = other  # nessun CORS: le altre origini non possono leggere né scrivere

    # ---------- GET
    def do_GET(self):
        try:
            if not self.host_ok():
                return self.err(403, "Host non consentito")
            u = urllib.parse.urlsplit(self.path)
            p, qs = u.path, urllib.parse.parse_qs(u.query)
            if self.headers.get("Host", "").split(":")[0] != "127.0.0.1" and p in ("/", "/reset", "/auth/google", "/auth/google/callback", "/auth/finish"):
                return self.redirect(BASE + p + ("?" + u.query if u.query else ""))
            ip, s = self.client_address[0], self.session()
            if p in ("/", "/reset"):
                _, ck = self.pre_cookie()
                nonce = secrets.token_urlsafe(16)
                return self.send(200, PAGE.replace("__NONCE__", nonce), "text/html", cookies=ck, nonce=nonce)
            if p == "/api/me":
                pre, ck = self.pre_cookie()
                b = ("s:" + s["sid"]) if s else "p:" + pre
                return self.jout({"user": {"email": s["email"], "name": s["name"]} if s else None, "csrf": csrf_for(b),
                                  "google": bool(G_ID and G_SECRET), "mail": bool(os.environ.get("SMTP_HOST")),
                                  "platform": PLATFORM, "app": APP, "version": VERSION, "window": WINDOW_MODE}, cookies=ck)
            if p == "/api/focus":  # una seconda copia della STESSA versione chiede di riportare in primo piano la finestra
                self.raise_window()
                return self.jout({"app": APP, "version": VERSION, "window": WINDOW_MODE})
            if p == "/auth/google":
                return self.google_start(ip, (qs.get("t") or [""])[0])
            if p == "/auth/google/callback":
                return self.google_cb(qs)
            if p == "/auth/finish":
                return self.auth_finish((qs.get("t") or [""])[0])
            if p in ("/api/drives", "/api/status", "/api/results"):
                if not s:
                    return self.err(401, "Accesso richiesto")
                mine = S["owner"] == s["uid"]
                if p == "/api/drives":
                    return self.jout(drives())
                if p == "/api/status":
                    r = {k: v for k, v in S.items() if k not in ("res", "owner")} if mine else {"phase": "idle"}
                    r["has_res"] = bool(mine and S["res"])
                    return self.jout(r)
                return self.jout(S["res"] if mine and S["res"] else {})
            self.err(404, "Non trovato")
        except Exception:
            traceback.print_exc()
            self.err(500, "Errore interno")

    # ---------- Google
    def raise_window(self):
        if WINDOW is None:
            return
        try:
            ready = WINDOW.events.shown.is_set()
        except Exception:
            ready = False
        if not ready:
            return
        for fn in ("restore", "show"):
            try:
                getattr(WINDOW, fn)()
            except Exception:
                pass

    def google_start(self, ip, ticket=""):
        if not (G_ID and G_SECRET):
            return self.redirect("/?e=google_off")
        if RL.count("g:" + ip, 600) >= 20:
            return self.redirect("/?e=rate")
        RL.add("g:" + ip)
        pre, ck = self.pre_cookie()
        st, ver, nonce, now = secrets.token_urlsafe(24), secrets.token_urlsafe(48), secrets.token_urlsafe(16), time.time()
        with HL:
            bound = ticket if (WINDOW_MODE and TIKRE.fullmatch(ticket or "") and ticket in HANDOFF and HANDOFF[ticket][0] is None) else ""
        with OAL:
            for k in [k for k, v in OAUTH.items() if v[3] < now]:
                del OAUTH[k]
            if len(OAUTH) > 200:
                OAUTH.clear()
            OAUTH[st] = (ver, nonce, pre, now + 600, bound)  # il ticket lega questo state OAuth al passaggio verso la finestra
        ch = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
        q = urllib.parse.urlencode({"client_id": G_ID, "redirect_uri": f"{BASE}/auth/google/callback", "response_type": "code",
                                    "scope": "openid email profile", "state": st, "nonce": nonce, "code_challenge": ch,
                                    "code_challenge_method": "S256", "prompt": "select_account"})
        self.redirect("https://accounts.google.com/o/oauth2/v2/auth?" + q, ck)

    def google_cb(self, qs):
        st, code = (qs.get("state") or [""])[0], (qs.get("code") or [""])[0]
        with OAL:
            ent = OAUTH.pop(st, None)
        tk = ent[4] if ent and len(ent) > 4 else ""

        def fail():
            if tk:
                with HL:
                    if tk in HANDOFF:
                        HANDOFF[tk] = ["fail", time.time() + 300]
                return self.send(200, DONE_PAGE % ("Accesso non riuscito", "Torna a Twenties Cleaning e riprova."), "text/html")
            return self.redirect("/?e=google_fail")
        if not ent or ent[3] < time.time() or not self.pre() or not eq(ent[2], self.pre()) or qs.get("error") or not code or len(code) > 2048:
            return fail()
        try:
            uid = google_user(google_exchange(code, ent[0], ent[1]))
        except Exception as e:
            print("Accesso Google non riuscito:", type(e).__name__)
            if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
                print("Certificati SSL mancanti. Su Mac con Python di python.org esegui 'Install Certificates.command'.")
            return fail()
        old = self.session()
        if old:
            dbx("DELETE FROM sessions WHERE id=?", (old["sid"],))
        tok, _ = new_session(uid)
        if tk:  # la sessione non resta nel browser: la finestra la ritira una sola volta con /auth/finish
            with HL:
                if tk in HANDOFF:
                    HANDOFF[tk] = [tok, time.time() + 120]
                    return self.send(200, DONE_PAGE % ("Accesso completato", "Puoi chiudere questa scheda e tornare a Twenties Cleaning."), "text/html")
        self.redirect("/", [self.mk(SN, tok)])

    def auth_finish(self, ticket):
        """Consegna la sessione alla finestra. Il ticket è monouso e nasce insieme allo state OAuth."""
        if not TIKRE.fullmatch(ticket or ""):
            return self.redirect("/?e=google_fail")
        with HL:
            v = HANDOFF.pop(ticket, None)
        if not v or v[1] < time.time() or not v[0] or v[0] == "fail":
            return self.redirect("/?e=google_fail")
        self.redirect("/", [self.mk(SN, v[0])])

    def p_gbegin(self, d, ip):
        if not (G_ID and G_SECRET):
            return self.err(400, "Accesso con Google non disponibile")
        if not WINDOW_MODE:  # nel browser i cookie sono già i suoi: Google si apre nella stessa finestra
            return self.jout({"same": True})
        now = time.time()
        with HL:
            for k in [k for k, v in HANDOFF.items() if v[1] < now]:
                del HANDOFF[k]
            if len(HANDOFF) > 20:
                HANDOFF.clear()
            tk = secrets.token_urlsafe(24)
            HANDOFF[tk] = [None, now + 300]
        try:
            webbrowser.open(f"{BASE}/auth/google?t={tk}")
        except Exception:
            with HL:
                HANDOFF.pop(tk, None)
            return self.err(500, "Non riesco ad aprire il browser")
        self.jout({"ticket": tk})

    def p_gpoll(self, d, ip):
        tk = str(d.get("ticket", ""))[:80]
        if not TIKRE.fullmatch(tk):
            return self.err(410, "Accesso scaduto")
        with HL:
            v = HANDOFF.get(tk)
            if not v or v[1] < time.time():
                HANDOFF.pop(tk, None)
                v = None
            elif v[0] == "fail":
                HANDOFF.pop(tk, None)
        if not v:
            return self.err(410, "Accesso scaduto")
        if v[0] == "fail":
            return self.err(400, "Accesso non riuscito")
        if v[0]:
            return self.jout({"ready": True})  # il cookie arriva con la navigazione a /auth/finish, non da qui
        self.jout({"wait": True})

    # ---------- POST
    def do_POST(self):
        try:
            if not self.host_ok() or not self.origin_ok():
                return self.err(403, "Richiesta non consentita")
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self.err(415, "Formato non supportato")
            try:
                d = self.body()
            except OverflowError:
                return self.err(413, "Richiesta troppo grande")
            except ValueError:
                return self.err(400, "Richiesta non valida")
            p, s, ip = self.urlpath(), self.session(), self.client_address[0]
            b = self.binding()
            if not b or not eq(self.headers.get("X-CSRF-Token", ""), csrf_for(b)):
                return self.err(403, "Sessione di sicurezza non valida: ricarica la pagina")
            pub = {"/api/register": self.p_register, "/api/login": self.p_login, "/api/forgot": self.p_forgot, "/api/reset": self.p_reset,
                   "/api/google_begin": self.p_gbegin, "/api/google_poll": self.p_gpoll}
            if p in pub:
                if RL.count("pub:" + ip, 60) >= 60:
                    return self.err(429, "Troppe richieste. Riprova tra poco.", headers=[("Retry-After", "60")])
                RL.add("pub:" + ip)
                return pub[p](d, ip)
            if not s:
                return self.err(401, "Accesso richiesto")
            if RL.count("api:" + s["sid"], 60) >= 240:
                return self.err(429, "Troppe richieste. Riprova tra poco.", headers=[("Retry-After", "30")])
            RL.add("api:" + s["sid"])
            fn = {"/api/logout": self.p_logout, "/api/start": self.p_start, "/api/stop": self.p_stop, "/api/reveal": self.p_reveal,
                  "/api/trash": self.p_trash, "/api/quit": self.p_quit, "/api/delete_account": self.p_delete}.get(p)
            if not fn:
                return self.err(404, "Non trovato")
            fn(d, s)
        except Exception:
            traceback.print_exc()
            self.err(500, "Errore interno")

    def urlpath(self):
        return urllib.parse.urlsplit(self.path).path

    def start_session(self, uid, user):
        old = self.session()
        if old:
            dbx("DELETE FROM sessions WHERE id=?", (old["sid"],))
        tok, sid = new_session(uid)
        self.jout({"user": user, "csrf": csrf_for("s:" + sid)}, cookies=[self.mk(SN, tok)])

    def p_register(self, d, ip):
        if RL.count("reg:" + ip, 3600) >= 10:
            return self.err(429, "Troppe registrazioni. Riprova più tardi.", headers=[("Retry-After", "3600")])
        RL.add("reg:" + ip)
        em, pw = norm_email(d.get("email")), d.get("password")
        if not em:
            return self.err(400, "Inserisci un'email valida.")
        e = pw_error(pw, em)
        if e:
            return self.err(400, e)
        with PWSEM:
            h = hash_pw(pw)
        try:
            uid = dbx("INSERT INTO users(email,pw,created) VALUES(?,?,?)", (em, h, int(time.time())))[2]
        except sqlite3.IntegrityError:
            return self.err(400, "Impossibile creare l'account con questi dati.")
        self.start_session(uid, {"email": em, "name": None})

    def p_login(self, d, ip):
        em, pw = norm_email(d.get("email")), d.get("password")
        pw = pw if isinstance(pw, str) and len(pw) <= 128 else ""
        ka, ki = "l:a:" + (em or ""), "l:i:" + ip
        if RL.count(ki, 900) >= 30 or RL.count(ka, 900) >= 5:
            return self.err(429, "Troppi tentativi. Riprova tra qualche minuto.", headers=[("Retry-After", "900")])
        rows = dbx("SELECT id, pw, name FROM users WHERE email=?", (em,))[0] if em else []
        with PWSEM:
            good = check_pw(pw, rows[0]["pw"] if rows and rows[0]["pw"] else DUMMY)
        if not (rows and rows[0]["pw"] and good):
            RL.add(ka)
            RL.add(ki)
            return self.err(401, "Email o password non corretti.")
        RL.clear(ka)
        self.start_session(rows[0]["id"], {"email": em, "name": rows[0]["name"]})

    def p_forgot(self, d, ip):
        em = norm_email(d.get("email"))
        if RL.count("f:i:" + ip, 3600) >= 10 or (em and RL.count("f:a:" + em, 3600) >= 3):
            return self.err(429, "Troppe richieste. Riprova più tardi.", headers=[("Retry-After", "3600")])
        RL.add("f:i:" + ip)
        if em:
            RL.add("f:a:" + em)
            rows = dbx("SELECT id FROM users WHERE email=?", (em,))[0]
            if rows:
                tok = secrets.token_urlsafe(32)
                dbx("DELETE FROM resets WHERE user_id=?", (rows[0]["id"],))
                dbx("INSERT INTO resets(id,user_id,expires) VALUES(?,?,?)", (hashlib.sha256(tok.encode()).hexdigest(), rows[0]["id"], int(time.time()) + RESET_TTL))
                threading.Thread(target=send_mail, args=(em, f"{BASE}/reset?token={tok}"), daemon=True).start()
        self.jout({"ok": True})  # stessa risposta se l'email esiste o no

    def p_reset(self, d, ip):
        tok, pw = d.get("token"), d.get("password")
        if RL.count("r:" + ip, 900) >= 10:
            return self.err(429, "Troppi tentativi. Riprova più tardi.", headers=[("Retry-After", "900")])
        RL.add("r:" + ip)
        if not isinstance(tok, str) or not TOKRE.fullmatch(tok):
            return self.err(400, "Link non valido o scaduto. Richiedine uno nuovo.")
        e = pw_error(pw)
        if e:
            return self.err(400, e)
        tid, now = hashlib.sha256(tok.encode()).hexdigest(), int(time.time())
        rows = dbx("SELECT user_id FROM resets WHERE id=? AND used=0 AND expires>?", (tid, now))[0]
        if not rows:
            return self.err(400, "Link non valido o scaduto. Richiedine uno nuovo.")
        with PWSEM:
            h = hash_pw(pw)
        if dbx("UPDATE resets SET used=1 WHERE id=? AND used=0 AND expires>?", (tid, now))[1] != 1:  # monouso anche con richieste simultanee
            return self.err(400, "Link non valido o scaduto. Richiedine uno nuovo.")
        uid = rows[0]["user_id"]
        dbx("UPDATE users SET pw=? WHERE id=?", (h, uid))
        dbx("DELETE FROM sessions WHERE user_id=?", (uid,))   # tutte le sessioni aperte vengono chiuse
        dbx("DELETE FROM resets WHERE user_id=?", (uid,))
        self.jout({"ok": True})

    def p_logout(self, d, s):
        dbx("DELETE FROM sessions WHERE id=?", (s["sid"],))
        pre, ck = self.pre_cookie()
        self.jout({"ok": True, "csrf": csrf_for("p:" + pre)}, cookies=ck + [self.mk(SN, "", 0)])

    def p_start(self, d, s):
        roots = d.get("roots")
        if not isinstance(roots, list) or not roots or len(roots) > 64 or not all(isinstance(x, str) and 0 < len(x) < 4096 and "\0" not in x for x in roots):
            return self.err(400, "Cartelle non valide.")
        roots = [os.path.normpath(x) for x in roots if os.path.isabs(x) and os.path.isdir(x)]
        try:
            mb = min(max(1, int(d.get("minmb", 5))), 100000)
        except (TypeError, ValueError):
            return self.err(400, "Dimensione minima non valida.")
        if not roots:
            return self.err(400, "Nessuna cartella valida selezionata.")
        with START_LOCK:
            if S["phase"] in RUNNING:
                return self.err(409, "Analisi già in corso." if S["owner"] == s["uid"] else "Un'altra sessione sta analizzando il computer. Riprova tra poco.")
            S.update(owner=s["uid"], phase="scan", count=0, current="", done=0, total=0, stop=False, error="", res=None, denied=0)
        threading.Thread(target=run, args=(roots, bool(d.get("dups")), bool(d.get("arch")), mb), daemon=True).start()
        self.jout({})

    def p_stop(self, d, s):
        if S["owner"] == s["uid"]:
            S["stop"] = True
        self.jout({})

    def p_reveal(self, d, s):
        p = d.get("path")
        if S["owner"] == s["uid"] and isinstance(p, str) and p in allowed_paths():
            reveal(p)
        self.jout({})

    def p_trash(self, d, s):
        paths = d.get("paths")
        if S["owner"] != s["uid"] or not S["res"] or S["phase"] != "done":
            return self.err(403, "Nessun risultato disponibile.")
        if not isinstance(paths, list) or len(paths) > 2000 or not all(isinstance(x, str) and len(x) < 4096 for x in paths):
            return self.err(400, "Selezione non valida.")
        self.jout(do_trash(paths))

    def p_delete(self, d, s):
        """Elimina per sempre l'account e i dati collegati (sessioni, link di reset). Con password: serve per confermare."""
        uid, pw = s["uid"], d.get("password")
        ka = "d:" + str(uid)
        if RL.count(ka, 900) >= 5:
            return self.err(429, "Troppi tentativi. Riprova tra qualche minuto.", headers=[("Retry-After", "900")])
        rows = dbx("SELECT pw FROM users WHERE id=?", (uid,))[0]
        if rows and rows[0]["pw"]:
            if not isinstance(pw, str) or not pw or len(pw) > 128:
                return self.err(400, "Inserisci la password per confermare.")
            with PWSEM:
                good = check_pw(pw, rows[0]["pw"])
            if not good:
                RL.add(ka)
                return self.err(401, "Password non corretta.")
        dbx("DELETE FROM users WHERE id=?", (uid,))  # sessioni e reset spariscono con ON DELETE CASCADE
        dbx("PRAGMA wal_checkpoint(TRUNCATE)")
        if S["owner"] == uid:
            S["stop"], S["owner"] = True, None
            if S["phase"] not in RUNNING:
                S.update(phase="idle", res=None)
            C["ok"] = {}
        pre, ck = self.pre_cookie()
        self.jout({"ok": True, "csrf": csrf_for("p:" + pre)}, cookies=ck + [self.mk(SN, "", 0)])

    def p_quit(self, d, s):
        self.jout({})
        if WINDOW is not None:
            threading.Thread(target=WINDOW.destroy, daemon=True).start()
        threading.Thread(target=self.server.shutdown, daemon=True).start()


PAGE = r"""<!doctype html><html lang="it" data-th="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="light dark"><title>Twenties Cleaning</title>
<script nonce="__NONCE__">try{document.documentElement.dataset.th=localStorage.getItem("tc_th")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light")}catch(e){}</script>
<style nonce="__NONCE__">
:root{--bg:#f5f5f7;--card:#fff;--ink:#000;--inv:#fff;--mu:#6e6e73;--line:rgba(0,0,0,.1);--fill:rgba(0,0,0,.05);--fill2:rgba(0,0,0,.09);--sh:0 1px 2px rgba(0,0,0,.04),0 12px 40px rgba(0,0,0,.06);--f:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue",Inter,"Segoe UI",system-ui,sans-serif}
[data-th=dark]{--bg:#000;--card:#1c1c1e;--ink:#f5f5f7;--inv:#000;--mu:#98989d;--line:rgba(255,255,255,.14);--fill:rgba(255,255,255,.08);--fill2:rgba(255,255,255,.14);--sh:none}
*{box-sizing:border-box}[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.47 var(--f);letter-spacing:-.011em;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;padding-bottom:100px;transition:background-color .24s ease,color .24s ease}
button,input,select{font:inherit;color:inherit;letter-spacing:inherit}
h1,h2,h3{letter-spacing:-.03em;margin:0}
a{color:var(--ink)}
.logo{width:34px;height:34px;border-radius:10px;background:var(--ink);color:var(--inv);display:grid;place-items:center;font-weight:700;font-size:17px;letter-spacing:0}
/* intro */
.intro{position:fixed;inset:0;background:#000;color:#fff;z-index:100;display:flex;flex-direction:column;padding:env(safe-area-inset-top) 24px calc(env(safe-area-inset-bottom) + 28px)}
.intro .skip{align-self:flex-end;margin-top:22px;background:none;border:0;color:#98989d;cursor:pointer;font-size:15px;padding:8px}
.slides{flex:1;display:grid;place-items:center;position:relative}
.slide{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;opacity:0;transform:translateY(10px) scale(.985);transition:opacity .28s cubic-bezier(.22,1,.36,1),transform .28s cubic-bezier(.22,1,.36,1);pointer-events:none;padding:0 12px}
.slide.on{opacity:1;transform:none;pointer-events:auto}
.slide .mark{width:84px;height:84px;border-radius:24px;background:#fff;color:#000;display:grid;place-items:center;font-size:44px;font-weight:700;margin-bottom:34px;letter-spacing:0}
.slide svg{width:84px;height:84px;margin-bottom:34px;stroke:#fff;fill:none;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}
.slide h1,.slide h2{font-size:clamp(40px,9vw,76px);line-height:1.03;font-weight:700;background:linear-gradient(180deg,#fff 30%,#86868b);-webkit-background-clip:text;background-clip:text;color:transparent;padding-bottom:.12em}
.slide p{color:#a1a1a6;font-size:clamp(17px,2.4vw,22px);max-width:520px;margin:20px 0 0;line-height:1.4}
.foot{display:flex;flex-direction:column;align-items:center;gap:22px}
.dots{display:flex;gap:8px}.dots i{width:7px;height:7px;border-radius:9px;background:#3a3a3c;transition:width .22s cubic-bezier(.22,1,.36,1),background .22s ease}.dots i.on{background:#fff;width:22px}
.intro .pri{background:#fff;color:#000;min-width:220px}
/* bottoni */
.btn{background:var(--fill);border:0;border-radius:980px;padding:8px 16px;cursor:pointer;font-size:14px;font-weight:500;transition:background .2s ease,color .2s ease,opacity .2s ease,transform .18s cubic-bezier(.22,1,.36,1)}.btn:hover{background:var(--fill2)}.btn:active{transform:scale(.98)}.btn:disabled{opacity:.4;cursor:default;transform:none}
.pri{background:var(--ink);color:var(--inv);border:0;border-radius:980px;padding:12px 28px;cursor:pointer;font-weight:600;font-size:16px;transition:transform .18s cubic-bezier(.22,1,.36,1),opacity .2s ease,background .2s ease}.pri:hover{opacity:.86}.pri:active{transform:scale(.98)}.pri:disabled{opacity:.4;cursor:default;transform:none}
.wide{width:100%;display:block}
.chip{border:1px solid var(--line);border-radius:980px;padding:6px 14px;cursor:pointer;color:var(--mu);background:none;font-size:14px;transition:background .2s ease,color .2s ease,border-color .2s ease,transform .18s cubic-bezier(.22,1,.36,1);user-select:none}.chip:hover{background:var(--fill)}.chip:active{transform:scale(.98)}
.chip.on,.chip:has(input:checked){background:var(--ink);color:var(--inv);border-color:var(--ink)}.chip input{display:none}.chip small{opacity:.7}
input[type=text],input[type=email],input[type=password],input[type=number],select{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;outline:0;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}
[data-th=dark] input[type=text],[data-th=dark] input[type=email],[data-th=dark] input[type=password],[data-th=dark] input[type=number],[data-th=dark] select{background:var(--fill)}
input:focus,select:focus{border-color:var(--ink);box-shadow:0 0 0 4px var(--fill2)}
input[type=checkbox]{accent-color:var(--ink);width:17px;height:17px}
/* accesso */
#auth{min-height:100vh;display:flex;align-items:flex-start;justify-content:center;padding:32px 20px}
.auth-wrap{width:min(1120px,100%);margin:auto;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,400px) minmax(0,1fr);gap:16px;align-items:stretch}
.bento{display:flex;flex-direction:column;gap:12px;justify-content:center;min-width:0}
.acard{width:100%;background:var(--card);border:1px solid var(--line);border-radius:28px;padding:36px 32px;box-shadow:var(--sh);text-align:center;animation:micro .26s cubic-bezier(.22,1,.36,1) backwards}
@keyframes micro{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:none}}
@keyframes micro-x{from{opacity:0;transform:translate(-50%,8px) scale(.985)}to{opacity:1;transform:translate(-50%,0) scale(1)}}
@keyframes soft{from{opacity:.45}to{opacity:1}}
.soft{animation:soft .2s cubic-bezier(.22,1,.36,1)}
.fcard{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:16px 16px 18px;box-shadow:var(--sh);text-align:left;animation:micro .26s cubic-bezier(.22,1,.36,1) backwards;transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .22s ease,background-color .24s ease,border-color .24s ease}
.fcard:hover{transform:translateY(-1px)}
.fcard .ic{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:var(--ink);color:var(--inv);margin-bottom:10px}
.fcard .ic svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.fcard h3{font-size:16px;font-weight:600;letter-spacing:-.02em}.fcard p{margin:6px 0 0;color:var(--mu);font-size:13.5px;line-height:1.4}
.bento .lg{flex:1.4;min-height:210px;padding:22px}.bento .lg h3{font-size:22px}.bento .lg p{font-size:15px}
.bento .md{flex:1.05;min-height:150px}.bento .sm{flex:.82;min-height:112px}
.bento.left .fcard:nth-child(1){animation-delay:.04s}.bento.left .fcard:nth-child(2){animation-delay:.12s}.bento.left .fcard:nth-child(3){animation-delay:.2s}
.bento.right .fcard:nth-child(1){animation-delay:.08s}.bento.right .fcard:nth-child(2){animation-delay:.16s}.bento.right .fcard:nth-child(3){animation-delay:.24s}
@media(max-width:980px){
 .auth-wrap{display:flex;flex-direction:column;max-width:560px}
 .auth-wrap .acard{order:1}
 .bento{order:2;display:grid;grid-template-columns:1fr 1fr;align-content:start}
 .bento.right{order:3}
 .bento .lg,.bento .md,.bento .sm{min-height:0;flex:none}
 .bento .lg{grid-column:1 / -1}
}
@media(max-width:640px){.bento{grid-template-columns:1fr}}
.acard .logo{margin:0 auto 22px;width:52px;height:52px;border-radius:15px;font-size:26px}
.acard h1{font-size:30px;font-weight:700}.sub{color:var(--mu);margin:8px 0 24px}
.acard form{display:grid;gap:12px}.acard input{width:100%;font-size:16px}
.seg{display:grid;grid-template-columns:1fr 1fr;background:var(--fill);border-radius:12px;padding:3px;margin-bottom:18px}
.seg button{background:none;border:0;border-radius:10px;padding:8px;cursor:pointer;color:var(--mu);font-weight:500;transition:background .2s ease,color .2s ease,box-shadow .2s ease,transform .18s cubic-bezier(.22,1,.36,1)}.seg button:active{transform:scale(.98)}.seg button.on{background:var(--card);color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.15)}
[data-th=dark] .seg button.on{background:#3a3a3c}
.fe{min-height:18px;font-size:13px;text-align:left;color:var(--ink);font-weight:500}.fe.ok{color:var(--mu)}
.or{display:flex;align-items:center;gap:12px;color:var(--mu);font-size:13px;margin:18px 0}.or:before,.or:after{content:"";flex:1;height:1px;background:var(--line)}
.gbtn{display:flex;align-items:center;justify-content:center;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:980px;padding:12px;cursor:pointer;font-weight:500;font-size:15px;transition:background .2s ease,transform .18s cubic-bezier(.22,1,.36,1),opacity .2s ease}.gbtn:hover{background:var(--fill)}.gbtn:active{transform:scale(.98)}.gbtn:disabled{opacity:.45;cursor:default;transform:none}.gbtn svg{width:18px;height:18px}
.hint{color:var(--mu);font-size:12.5px;margin:10px 0 0}.links{margin-top:18px;font-size:14px;display:flex;justify-content:center;gap:18px}.links a{color:var(--mu)}
/* app */
header{display:flex;align-items:center;gap:12px;padding:12px 24px;position:sticky;top:0;z-index:5;flex-wrap:wrap;row-gap:8px;background:color-mix(in srgb,var(--bg) 72%,transparent);-webkit-backdrop-filter:saturate(180%) blur(22px);backdrop-filter:saturate(180%) blur(22px);border-bottom:1px solid var(--line);transition:background-color .24s ease,border-color .24s ease}
header b{font-size:17px;letter-spacing:-.02em}header .sp{flex:1}#who{color:var(--mu);font-size:13px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
main{max-width:1180px;margin:0 auto;padding:28px 20px}
#app main{min-height:calc(100vh - 78px);position:relative}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:26px;margin-bottom:16px;box-shadow:var(--sh);transition:background-color .24s ease,border-color .24s ease,box-shadow .22s ease,transform .18s cubic-bezier(.22,1,.36,1),color .24s ease}
.card:hover{transform:translateY(-1px)}
.dash{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.85fr);gap:16px;align-items:start}
.dash > .card,.dash > #prog{margin-bottom:0}
.span2{grid-column:1 / -1}
.stack{display:grid;gap:16px}.stack>.card{margin-bottom:0}
.card h3{font-size:18px;font-weight:600}
@media(max-width:900px){.dash{grid-template-columns:1fr}header .btn{padding:6px 10px;font-size:13px}}
.hero-panel h2{font-size:clamp(32px,4vw,46px);line-height:1.05}
.hero-top{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;flex-wrap:wrap}
.eyebrow{color:var(--mu);font-size:13px;font-weight:600;letter-spacing:.01em;margin:0 0 6px}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}
.metric{background:var(--fill);border-radius:16px;padding:14px 16px}
.metric b{display:block;font-size:22px;letter-spacing:-.03em;margin-top:2px}
.metric small{color:var(--mu)}
@media(max-width:640px){.metrics{grid-template-columns:1fr}}
.drive-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.dcard{display:grid;grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:"ck name pct" "ck meta pct" "bar bar bar";gap:2px 14px;align-items:center;padding:16px 18px;border:1px solid var(--line);border-radius:18px;background:var(--card);cursor:pointer;text-align:left;transition:transform .18s cubic-bezier(.22,1,.36,1),border-color .2s ease,box-shadow .2s ease,background-color .24s ease}
.dcard:hover{transform:translateY(-1px)}
.dcard:active{transform:scale(.985)}
.dcard:has(input:checked){border-color:var(--ink);box-shadow:0 0 0 1px var(--ink)}
.dcard input{grid-area:ck}.dcard b{grid-area:name;word-break:break-all}.dcard small{grid-area:meta;color:var(--mu)}
.dcard .pct{grid-area:pct;font-size:22px;font-weight:600;letter-spacing:-.03em}.dcard .bar{grid-area:bar;margin-top:8px}
.kv{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--line);font-size:13.5px}
.kv span{color:var(--mu)}.kv b{font-weight:600;text-align:right}
.optgrid{display:grid;gap:10px}
.opt{border:1px solid var(--line);border-radius:16px;padding:12px 14px;background:var(--fill);transition:background-color .2s ease,border-color .2s ease}
.opt .r{margin-top:10px}
.mini-bento{display:grid;grid-template-columns:1.35fr 1fr .85fr;grid-auto-rows:minmax(100px,auto);gap:12px}
.mini-bento .fcard{animation:none}
.mini-bento .fcard:hover{transform:translateY(-1px)}
.mini-bento .lg{grid-row:span 2;min-height:220px}
.mini-bento .md{min-height:148px}.mini-bento .sm{min-height:100px}
@media(max-width:800px){.mini-bento{grid-template-columns:1fr}.mini-bento .lg{grid-row:auto;min-height:0}}
.statgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}
@media(max-width:900px){.statgrid{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.statgrid{grid-template-columns:1fr}}
.split{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(240px,.8fr);gap:16px;margin-bottom:16px}
@media(max-width:820px){.split{grid-template-columns:1fr}}
.split .card,.statgrid .k{margin-bottom:0}
button.k{display:block;width:100%;text-align:left;cursor:pointer;font:inherit;color:inherit}
.catrow{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;align-items:center;margin-top:12px}
.catrow b{font-size:13px;justify-self:end}.catrow .bar{grid-column:1 / -1;margin:0}
.qacts{display:grid;gap:8px}
.qbtn{display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;text-align:left;background:var(--fill);border:0;border-radius:14px;padding:12px 14px;cursor:pointer;font-weight:600;transition:background .2s ease,transform .18s cubic-bezier(.22,1,.36,1)}
.qbtn:hover{background:var(--fill2)}.qbtn:active{transform:scale(.985)}
.qbtn small{color:var(--mu);font-weight:500}
.sk{position:relative;overflow:hidden;background:var(--fill2);border-radius:16px}
.sk::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 18%,rgba(255,255,255,.55) 50%,transparent 82%);transform:translateX(-100%);animation:shimmer 1.5s ease-in-out infinite}
[data-th=dark] .sk::after{background:linear-gradient(100deg,transparent 18%,rgba(255,255,255,.16) 50%,transparent 82%)}
@keyframes shimmer{to{transform:translateX(100%)}}
.sk-metric{height:72px;border-radius:16px}.sk-drive{height:112px;border-radius:18px}
.sk-hero{height:148px;border-radius:28px}.sk-stat{height:108px;border-radius:22px}
.sk-line{height:68px;margin-top:10px}.sk-line.short{width:72%}
.sk-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px}
@media(max-width:820px){.sk-stats{grid-template-columns:1fr 1fr}}
.sk-wrap{margin-top:16px}
.leaving{opacity:0!important;pointer-events:none;transition:opacity .22s cubic-bezier(.22,1,.36,1),transform .22s cubic-bezier(.22,1,.36,1)}
#auth.leaving,#app.leaving,#intro.leaving,#modal.leaving,#drv.leaving,#disksum.leaving,#view.leaving{transform:translateY(6px) scale(.985)}
#scan.leaving,#res.leaving{position:absolute;z-index:4;left:20px;right:20px;top:28px;transform:translateY(6px) scale(.985)}
#toast.leaving,#act.leaving{transform:translate(-50%,8px) scale(.985)}
.in:not(#toast):not(#act):not(#app):not(#view):not(#drv):not(#disksum):not(#scan):not(#res):not(#auth){animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#disksum.in>*{animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#disksum.in>*:nth-child(2){animation-delay:.05s}#disksum.in>*:nth-child(3){animation-delay:.1s}
.k,.grp{transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .22s ease,background-color .24s ease,border-color .24s ease}
.k:hover,.grp:hover{transform:translateY(-1px)}
#toast.in,#act.in{animation:micro-x .24s cubic-bezier(.22,1,.36,1) backwards}
#app.in > header{animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#app.in .hero-panel{animation:micro .26s cubic-bezier(.22,1,.36,1) .02s backwards}
#app.in .drives-card{animation:micro .26s cubic-bezier(.22,1,.36,1) .07s backwards}
#app.in .status-card{animation:micro .26s cubic-bezier(.22,1,.36,1) .12s backwards}
#app.in .quick-card{animation:micro .26s cubic-bezier(.22,1,.36,1) .17s backwards}
#app.in .about-card{animation:micro .26s cubic-bezier(.22,1,.36,1) .22s backwards}
#drv.in .dcard{animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#drv.in .dcard:nth-child(2){animation-delay:.04s}#drv.in .dcard:nth-child(3){animation-delay:.08s}
#drv.in .dcard:nth-child(4){animation-delay:.12s}#drv.in .dcard:nth-child(5){animation-delay:.16s}
#drv.in .dcard:nth-child(n+6){animation-delay:.2s}
#view.in > *{animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#view.in > *:nth-child(2){animation-delay:.04s}#view.in > *:nth-child(3){animation-delay:.08s}
#view.in > *:nth-child(4){animation-delay:.12s}#view.in > *:nth-child(5){animation-delay:.16s}
#view.in > *:nth-child(n+6){animation-delay:.2s}
#modal{opacity:1;transition:opacity .22s cubic-bezier(.22,1,.36,1)}
#modal.leaving{opacity:0}
h2{font-size:26px;font-weight:700}.s{color:var(--mu);margin:6px 0 16px}
.r{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.r+.r{margin-top:12px}
.bar{height:6px;background:var(--fill2);border-radius:6px;overflow:hidden;margin-top:7px}.bar i{display:block;height:100%;width:0;background:var(--ink);border-radius:6px;transition:width .26s cubic-bezier(.22,1,.36,1)}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.st{font-size:13px;padding:4px 12px;border-radius:980px;color:var(--mu);background:var(--fill);transition:background .22s ease,color .22s ease}.st.on{background:var(--ink);color:var(--inv)}
.lay{display:grid;grid-template-columns:220px 1fr;gap:24px}@media(max-width:820px){.lay{grid-template-columns:1fr}.nav{flex-direction:row!important;flex-wrap:wrap;position:static!important}}
.nav{display:flex;flex-direction:column;gap:2px;align-self:start;position:sticky;top:76px}
.nv{display:flex;justify-content:space-between;gap:8px;text-align:left;background:none;border:0;color:var(--mu);padding:10px 14px;border-radius:12px;cursor:pointer;font-weight:500;transition:background .2s ease,color .2s ease,transform .18s cubic-bezier(.22,1,.36,1)}.nv:hover{background:var(--fill)}.nv:active{transform:scale(.98)}.nv.on{background:var(--ink);color:var(--inv)}
.nv em{font-style:normal;font-size:12px;opacity:.7}
.hero{background:var(--ink);color:var(--inv);border-radius:28px;padding:36px 32px;margin-bottom:16px}.hero small{opacity:.65;font-size:14px}.hero big{font-size:clamp(48px,8vw,84px);font-weight:700;display:block;line-height:1.02;letter-spacing:-.045em;margin:6px 0 10px}.hero p{opacity:.65;margin:0;max-width:620px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-bottom:16px}
.k{border:1px solid var(--line);border-radius:22px;padding:20px;background:var(--card);box-shadow:var(--sh)}.k b{font-size:28px;display:block;letter-spacing:-.03em;margin-bottom:12px}.k small{color:var(--mu);display:block;margin-bottom:2px}
.row{display:grid;grid-template-columns:28px 160px 1fr 140px 90px;gap:14px;align-items:center;padding:14px 4px;border-top:1px solid var(--line)}.row.nc{grid-template-columns:160px 1fr 140px 90px}
@media(max-width:820px){.row,.row.nc{grid-template-columns:1fr}}
.pill{font-size:12px;font-weight:600;padding:3px 11px;border-radius:980px;justify-self:start;white-space:nowrap;border:1px solid transparent;display:inline-block}
.p-g{border:1px dashed var(--ink)}.p-s{background:var(--ink);color:var(--inv)}.p-l{background:var(--fill2)}.p-m{border-color:var(--ink)}.p-h{background:var(--fill);border-color:var(--line)}
.nm small{display:block;color:var(--mu);word-break:break-all}.nm b{word-break:break-all;font-weight:600}
.grp{border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin-bottom:10px}.cp{display:grid;grid-template-columns:24px 1fr auto;gap:10px;align-items:center;margin-top:9px;color:var(--mu);word-break:break-all}
.warn{background:var(--fill);border-radius:16px;padding:14px 18px;margin-bottom:14px}
.leg{display:grid;gap:10px}.leg div{display:flex;gap:12px;align-items:center;color:var(--mu)}
#act{position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom) + 20px);transform:translateX(-50%);background:var(--ink);color:var(--inv);border-radius:980px;padding:10px 12px 10px 24px;display:flex;gap:14px;align-items:center;box-shadow:0 14px 50px rgba(0,0,0,.35);z-index:9;white-space:nowrap;transition:opacity .22s cubic-bezier(.22,1,.36,1),transform .22s cubic-bezier(.22,1,.36,1)}
#act .btn{background:color-mix(in srgb,var(--inv) 18%,transparent);color:var(--inv)}#act .dng{background:var(--inv);color:var(--ink);border:0;border-radius:980px;padding:9px 18px;cursor:pointer;font-weight:600;transition:transform .18s cubic-bezier(.22,1,.36,1),opacity .2s ease}#act .dng:hover{opacity:.88}#act .dng:active{transform:scale(.98)}
#toast{position:fixed;left:50%;top:70px;transform:translateX(-50%);background:var(--ink);color:var(--inv);border-radius:16px;padding:12px 20px;z-index:200;max-width:min(440px,92vw);box-shadow:0 14px 50px rgba(0,0,0,.3)}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.45);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);z-index:150;display:grid;place-items:center;padding:20px}
.sheet{background:var(--card);border-radius:24px;padding:28px;max-width:400px;width:100%;box-shadow:0 30px 80px rgba(0,0,0,.35);animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}.sheet h3{font-size:20px}.sheet p{color:var(--mu);white-space:pre-line;margin:10px 0 22px}.sb{display:flex;gap:10px;justify-content:flex-end}.sb .pri{padding:10px 22px;font-size:15px}
#app.in .mini-bento .fcard{animation:micro .24s cubic-bezier(.22,1,.36,1) backwards}
#app.in .mini-bento .fcard:nth-child(1){animation-delay:.04s}#app.in .mini-bento .fcard:nth-child(2){animation-delay:.08s}
#app.in .mini-bento .fcard:nth-child(3){animation-delay:.12s}#app.in .mini-bento .fcard:nth-child(4){animation-delay:.16s}
#app.in .mini-bento .fcard:nth-child(5){animation-delay:.2s}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>
<div id=intro class=intro hidden>
 <button class=skip id=skip>Salta</button>
 <div class=slides>
  <div class="slide on"><div class=mark>T</div><h1>Twenties<br>Cleaning</h1><p>Lo spazio del tuo computer, finalmente in ordine.</p></div>
  <div class=slide><svg viewBox="0 0 48 48"><path d="M3 24s7.5-13 21-13 21 13 21 13-7.5 13-21 13S3 24 3 24z"/><circle cx="24" cy="24" r="6"/></svg><h2>Vedi tutto.<br>Non tocchi niente.</h2><p>L'analisi è in sola lettura. Trova cache, doppioni e archivi già estratti senza modificare nulla.</p></div>
  <div class=slide><svg viewBox="0 0 48 48"><path d="M8 13h32M18 13V8h12v5M12 13l2 28h20l2-28M20 20v14M28 20v14"/></svg><h2>Poi decidi tu.</h2><p>Ogni file va nel Cestino solo dopo la tua conferma. Resta sempre recuperabile.</p></div>
 </div>
 <div class=foot><div class=dots id=dots></div><button class=pri id=nx>Continua</button></div>
</div>
<div id=auth hidden></div>
<div id=app hidden>
<header><div class=logo>T</div><b>Twenties Cleaning</b><span class=sp></span><span id=who></span>
<button class=btn id=again hidden>Nuova analisi</button><button class=btn id=th title="Tema chiaro/scuro" aria-label="Tema">Tema</button><button class=btn id=out>Esci dall'account</button><button class=btn id=del>Elimina account</button><button class=btn id=quit>Chiudi app</button></header>
<main>
<div id=scan>
<div class=dash>
 <section class="card hero-panel span2">
  <div class=hero-top>
   <div><p class=eyebrow id=greet>Il tuo computer</p><h2>Analizza lo spazio</h2><p class=s>Scegli i dischi da controllare. L'analisi è in sola lettura: non modifica e non cancella nulla.</p></div>
   <button class=pri id=go>Avvia analisi</button>
  </div>
  <div class=metrics id=disksum><div class="sk sk-metric"></div><div class="sk sk-metric"></div><div class="sk sk-metric"></div></div>
 </section>
 <section class="card drives-card">
  <h3>Dischi</h3><p class=s id=pick>Lettura dei dischi di questo computer…</p>
  <div class=drive-grid id=drv><div class="sk sk-drive"></div><div class="sk sk-drive"></div><div class="sk sk-drive"></div></div>
 </section>
 <div class=stack>
  <section class="card status-card"><h3>Stato del sistema</h3><div id=sys style="margin-top:8px"></div></section>
  <section class="card quick-card">
   <h3>Azioni rapide</h3><p class=s>Opzioni dell'analisi. I doppioni partono dalla dimensione che indichi.</p>
   <div class=optgrid>
    <div class=opt><label class=chip><input type=checkbox id=dups checked>Cerca doppioni</label><div class=r><span class=s style="margin:0">solo file da</span><input type=number id=minmb value=5 min=1 style="width:84px"><span class=s style="margin:0">MB in su</span></div></div>
    <div class=opt><label class=chip><input type=checkbox id=arch checked>Cerca archivi già estratti</label><p class=s style="margin:8px 0 0">RAR, ZIP, 7z e TAR il cui contenuto è già sul disco.</p></div>
    <div class=opt><input type=text id=custom placeholder="Cartella specifica da aggiungere (facoltativo)" style="width:100%"></div>
   </div>
  </section>
 </div>
 <section class="card about-card span2">
  <h3>Cosa controlla l'analisi</h3><p class=s>Solo ciò che il programma sa fare. Nessun dato inventato.</p>
  <div class=mini-bento>
   <article class="fcard lg"><div class=ic><svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg></div><h3>Cartelle</h3><p>Raggruppa le cartelle da almeno 100 MB e le etichetta in base al contenuto: gioco, scarto o importanza.</p></article>
   <article class="fcard md"><div class=ic><svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg></div><h3>File grandi</h3><p>Elenca fino a 400 file più pesanti, con una spiegazione per ciascuno.</p></article>
   <article class="fcard sm"><div class=ic><svg viewBox="0 0 24 24"><rect x="3" y="8" width="18" height="10" rx="2"/><path d="M8 8V6h8v2"/></svg></div><h3>Giochi</h3><p>Riconosce Steam, Epic, GOG, Riot, Ubisoft, EA e Xbox.</p></article>
   <article class="fcard md"><div class=ic><svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 0 1 2-2h10"/></svg></div><h3>Doppioni</h3><p>Confronta il contenuto e tiene sempre almeno una copia. Soglia iniziale: 5 MB.</p></article>
   <article class="fcard sm"><div class=ic><svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/></svg></div><h3>Archivi</h3><p>ZIP e TAR sempre. RAR e 7z se trovi 7-Zip o UnRAR.</p></article>
  </div>
 </section>
 <div id=prog class="card span2" hidden aria-busy=true>
  <h3>Analisi in corso</h3><p class=s>Il controllo continua in background: questa finestra resta utilizzabile.</p>
  <div class=steps id=steps></div>
  <div id=msg class=s style="word-break:break-all;margin:0"></div>
  <div class=bar id=bar hidden><i></i></div>
  <div class=sk-wrap aria-hidden=true>
   <div class="sk sk-hero"></div>
   <div class=sk-stats><div class="sk sk-stat"></div><div class="sk sk-stat"></div><div class="sk sk-stat"></div><div class="sk sk-stat"></div></div>
   <div class="sk sk-line"></div><div class="sk sk-line"></div><div class="sk sk-line short"></div>
  </div>
 </div>
</div>
</div>
<div id=res hidden><div class=lay><nav class=nav id=nav></nav><section id=view></section></div></div>
</main>
<div id=act hidden></div></div>
<div id=modal hidden></div><div id=toast hidden></div>
<script nonce="__NONCE__">
"use strict";
function outside(u){try{const x=new URL(String(u),location.href);return (x.protocol==="http:"||x.protocol==="https:")&&x.host!==location.host}catch(e){return false}}
document.addEventListener("click",e=>{let n=e.target;while(n&&n!==document){if(n.tagName==="A"&&n.href)break;n=n.parentNode}if(!n||n===document||!outside(n.href))return;const api=window.pywebview&&window.pywebview.api;if(!api||!api.open_external)return;e.preventDefault();e.stopPropagation();api.open_external(n.href)},true);
const _open=window.open;window.open=function(u){const api=window.pywebview&&window.pywebview.api;if(outside(u)&&api&&api.open_external){api.open_external(String(u));return null}return _open?_open.apply(window,arguments):null};
const CATS=["Gioco","Scarto","Importanza bassa","Importanza media","Importanza elevata"];
const PC={"Gioco":"p-g","Scarto":"p-s","Importanza bassa":"p-l","Importanza media":"p-m","Importanza elevata":"p-h"};
const LEG={"Gioco":"File di giochi. Non toccarli: se non servono, disinstalla dal launcher.","Scarto":"Cache, temporanei, log: di solito eliminabili.","Importanza bassa":"Roba vecchia o riscaricabile (ISO, vecchi video, installer).","Importanza media":"Contenuti recenti e programmi installati.","Importanza elevata":"Documenti, foto, progetti e sistema: da conservare."};
const LV={ok:["Già estratto","p-s"],part:["Estratto in parte","p-m"],guess:["Da verificare","p-g"]};
const NAV=[["home","Panoramica"],["folders","Cartelle"],["games","Giochi"],["files","File grandi"],["dups","Doppioni"],["arch","Archivi già estratti"]];
const STEPS={scan:"1 · Lettura dei dischi",agg:"2 · Calcolo cartelle",dups:"3 · Ricerca doppioni",arch:"4 · Verifica archivi"};
const INTRO={folders:"Le cartelle che occupano più spazio. Una cartella piena di file piccoli compare come un'unica voce, con il peso totale.",games:"I giochi trovati e lo spazio che occupano.",files:"I singoli file più pesanti. Puoi selezionarli e spostarli nel Cestino.",dups:"Gruppi di file identici. Per sicurezza di ogni gruppo resta sempre almeno una copia.",arch:"Archivi di cui ho verificato che il contenuto è già stato estratto: l'archivio è un doppione e si può eliminare."};
const EMSG={google_off:"L'accesso con Google non è configurato.",google_fail:"Accesso con Google non riuscito. Riprova.",rate:"Troppi tentativi. Riprova tra qualche minuto."};
const GSVG='<svg viewBox="0 0 24 24"><text x="12" y="18" text-anchor="middle" font-size="19" font-weight="700" fill="currentColor" font-family="Arial,sans-serif">G</text></svg>';
const OSN={mac:{perm:"Per includere le cartelle protette, concedi l'Accesso completo al disco a Twenties Cleaning (o al Terminale, se la avvii da script) in Impostazioni di Sistema › Privacy e sicurezza, poi riavvia l'app.",tool:"Per leggere i file RAR e 7z installa <b>7-Zip</b> (da Terminale: brew install sevenzip). ZIP e TAR vengono verificati comunque.",show:"Mostra nel Finder"},win:{perm:"Avvia il programma come Amministratore per includerle.",tool:"Per verificare il contenuto dei file RAR e 7z installa <b>7-Zip</b> o <b>WinRAR</b>. Gli archivi ZIP e TAR vengono verificati comunque.",show:"Mostra"},linux:{perm:"Avvia il programma con i permessi adeguati per includerle.",tool:"Per verificare i file RAR e 7z installa <b>7-Zip</b>. ZIP e TAR vengono verificati comunque.",show:"Mostra"}};
let ME=null,CSRF="",GOOGLE=false,MAIL=false,PLAT="linux",RT="",AMODE="login",FLASH=null,scanned=null;
let R=null,tab="home",filt="Tutti",q="",sortk="size",sel=new Set(),running=false,timer,AM={},SZ={};
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"'`]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;","`":"&#96;"}[c]));
const fmt=n=>{const u=["B","KB","MB","GB","TB"];let i=0;while(n>=1024&&i<4){n/=1024;i++}return (i?n.toFixed(1):n)+" "+u[i]};
const pill=(t,c)=>`<span class="pill ${c}">${esc(t)}</span>`;
const dt=t=>t?new Date(t*1000).toLocaleDateString("it"):"";
const MOTION=220,REDUCE=()=>matchMedia("(prefers-reduced-motion: reduce)").matches;
function hideAnimated(el,fn){
 if(!el||el.hidden){fn&&fn();return}
 if(REDUCE()){el.hidden=true;el.classList.remove("leaving");fn&&fn();return}
 const token=(el._tok=(el._tok||0)+1);
 el.classList.add("leaving");
 setTimeout(()=>{if(el._tok!==token)return;el.hidden=true;el.classList.remove("leaving");fn&&fn()},MOTION)}
function showIn(el){if(!el||REDUCE())return;el.classList.remove("in");void el.offsetWidth;el.classList.add("in")}
function setText(el,text){if(!el||el.textContent===text)return;el.textContent=text;if(REDUCE())return;el.classList.remove("soft");void el.offsetWidth;el.classList.add("soft")}
const IC={
 eye:'<svg viewBox="0 0 24 24"><path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/></svg>',
 copy:'<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 0 1 2-2h10"/></svg>',
 box:'<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/></svg>',
 trash:'<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13"/></svg>',
 lock:'<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
 tag:'<svg viewBox="0 0 24 24"><path d="M3 12V4h8l10 10-8 8L3 12z"/><circle cx="8" cy="8" r="1.2" fill="currentColor" stroke="none"/></svg>'};
const FEATURES={
 left:[["lg",IC.eye,"Vede tutto, non tocca niente","L'analisi è in sola lettura: cartelle, file grandi e giochi, senza modificare nulla sul disco."],["sm",IC.copy,"Doppioni verificati","Confronta il contenuto dei file e lascia sempre almeno una copia."],["sm",IC.box,"Archivi già estratti","Controlla ZIP, TAR, RAR e 7z il cui contenuto è già presente."]],
 right:[["md",IC.trash,"Solo nel Cestino","Si sposta solo ciò che selezioni, e solo dopo una conferma. Resta recuperabile."],["md",IC.lock,"Resta sul computer","Funziona in locale, su questo PC. I file non vengono inviati da nessuna parte."],["sm",IC.tag,"Etichette chiare","Gioco, scarto, importanza bassa, media o elevata."]]};
function fcard(sz,icon,title,desc){return `<article class="fcard ${sz}"><div class=ic>${icon}</div><h3>${esc(title)}</h3><p>${esc(desc)}</p></article>`}
function side(list){return list.map(x=>fcard(x[0],x[1],x[2],x[3])).join("")}
function toast(h,ms=6000){const t=$("#toast");clearTimeout(t._t);t.textContent=h;t._tok=(t._tok||0)+1;t.hidden=false;t.classList.remove("leaving");showIn(t);t._t=setTimeout(()=>hideAnimated(t),ms)}
async function api(u,b){
 const o=b===undefined?{credentials:"same-origin"}:{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRF-Token":CSRF},body:JSON.stringify(b)};
 let r,j;try{r=await fetch(u,o);j=await r.json()}catch(e){return{error:"Connessione al programma non riuscita.",_s:0}}
 if(j&&typeof j==="object")j._s=r.status;
 if(r.status===401&&ME&&u!=="/api/login"){ME=null;stopPoll();showAuth("login");toast("Sessione scaduta. Accedi di nuovo.")}
 return j}
async function googleGo(){const r=await api("/api/google_begin",{});
 if(!r||r.error){toast(r&&r.error?r.error:"Accesso con Google non disponibile");return}
 if(r.same){location.href="/auth/google";return}
 toast("Completa l'accesso nel browser, poi torna qui…",300000);
 for(let i=0;i<150;i++){await new Promise(z=>setTimeout(z,2000));const q=await api("/api/google_poll",{ticket:r.ticket});
  if(q&&q.ready){location.replace("/auth/finish?t="+encodeURIComponent(r.ticket));return}
  if(q&&q.error){toast("Accesso con Google non riuscito. Riprova.");return}}
 toast("Tempo scaduto. Riprova.")}
function ask(title,body,ok){return new Promise(res=>{const m=$("#modal");m.innerHTML=`<div class=sheet role=dialog aria-modal=true><h3>${esc(title)}</h3><p>${esc(body)}</p><div class=sb><button type=button class=btn data-m=0>Annulla</button><button type=button class=pri data-m=1>${esc(ok)}</button></div></div>`;m._tok=(m._tok||0)+1;m.hidden=false;m.classList.remove("leaving");const done=v=>hideAnimated(m,()=>{m.innerHTML="";m.onclick=null;res(v)});m.onclick=e=>{const b=e.target.closest("[data-m]");if(b)done(b.dataset.m==="1");else if(e.target===m)done(false)};m.querySelector(".pri").focus()})}
/* intro */
let si=0;const SL=[...document.querySelectorAll(".slide")];
function slide(n){si=n;SL.forEach((s,i)=>s.classList.toggle("on",i===n));const dots=$("#dots");if(dots.childElementCount!==SL.length)dots.innerHTML=SL.map(()=>"<i></i>").join("");[...dots.children].forEach((d,i)=>d.classList.toggle("on",i===n));setText($("#nx"),n===SL.length-1?"Inizia":"Continua")}
function endIntro(){try{localStorage.setItem("tc_intro","1")}catch(e){}hideAnimated($("#intro"),()=>route())}
$("#nx").onclick=()=>si<SL.length-1?slide(si+1):endIntro();$("#skip").onclick=endIntro;
/* accesso */
function fe(m,ok){const e=$("#fe");if(e){e.textContent=m||"";e.className="fe"+(ok?" ok":"")}}
function showAuth(mode,after){
 const swap=mode!==AMODE&&!$("#auth").hidden&&$("#auth").innerHTML;
 AMODE=mode;$("#intro").hidden=true;
 const paint=()=>{
  $("#app").hidden=true;$("#app").classList.remove("leaving");$("#app")._tok=($("#app")._tok||0)+1;
  const A=$("#auth");A.hidden=false;A.classList.remove("leaving");
  const T={login:["Bentornato.","Accedi per continuare."],register:["Crea il tuo account.","Bastano un'email e una password."],forgot:["Password dimenticata?","Inserisci la tua email. Ti invieremo un link che scade tra 15 minuti."],reset:["Nuova password.","Scegline una di almeno 10 caratteri."]}[mode];
  const lr=mode==="login"||mode==="register";
  A.innerHTML=`<div class=auth-wrap><div class="bento left">${side(FEATURES.left)}</div><div class=acard><div class=logo>T</div><h1>${T[0]}</h1><p class=sub>${T[1]}</p>
 ${lr?`<div class=seg><button type=button data-am=login class="${mode==="login"?"on":""}">Accedi</button><button type=button data-am=register class="${mode==="register"?"on":""}">Crea account</button></div>`:""}
 <form id=af novalidate>${mode!=="reset"?`<input type=email id=em placeholder="Email" autocomplete=email maxlength=254 required>`:""}${mode!=="forgot"?`<input type=password id=pw placeholder="Password" autocomplete="${mode==="login"?"current-password":"new-password"}" maxlength=128 required>`:""}
 <div id=fe class=fe role=alert></div><button class="pri wide" id=sb type=submit>${{login:"Accedi",register:"Crea account",forgot:"Invia link",reset:"Aggiorna password"}[mode]}</button></form>
 ${lr?`<div class=or><span>oppure</span></div><button type=button class="gbtn wide" id=gg ${GOOGLE?"":"disabled"}>${GSVG}Continua con Google</button>${GOOGLE?"":`<p class=hint>L'accesso con Google non è ancora configurato su questo computer.</p>`}`:""}
 <div class=links>${mode==="login"?`<a href="#" data-am=forgot>Password dimenticata?</a>`:""}${mode==="forgot"||mode==="reset"?`<a href="#" data-am=login>Torna all'accesso</a>`:""}<a href="#" id=reintro>Introduzione</a></div></div><div class="bento right">${side(FEATURES.right)}</div></div>`;
  if(FLASH){fe(FLASH);FLASH=null}const f=$("#em")||$("#pw");f&&f.focus();after&&after()};
 if(!$("#app").hidden)hideAnimated($("#app"),paint);
 else if(swap)hideAnimated($("#auth"),()=>{paint()});
 else paint()}
function route(){ME?enterApp():showAuth(RT?"reset":"login")}
document.addEventListener("submit",async e=>{
 if(e.target.id!=="af")return;e.preventDefault();
 const em=$("#em")?$("#em").value.trim():"",pw=$("#pw")?$("#pw").value:"",b=$("#sb");b.disabled=true;fe("");let r;
 if(AMODE==="forgot")r=await api("/api/forgot",{email:em});else if(AMODE==="reset")r=await api("/api/reset",{token:RT,password:pw});else r=await api(AMODE==="login"?"/api/login":"/api/register",{email:em,password:pw});
 b.disabled=false;if(r.error)return fe(r.error);
 if(AMODE==="forgot")fe(MAIL?"Se esiste un account con questa email, il link è stato inviato. Scade tra 15 minuti.":"Questo programma non invia email, quindi la password non si può recuperare da qui. Per ripartire elimina la cartella dei dati dell'app (la guida dice dove si trova) e crea un nuovo account: i tuoi file non vengono toccati.",true);
 else if(AMODE==="reset"){RT="";showAuth("login",()=>fe("Password aggiornata. Ora puoi accedere.",true))}
 else{ME=r.user;CSRF=r.csrf;enterApp()}});
/* app */
function resetUI(){R=null;sel.clear();tab="home";filt="Tutti";q="";running=false;scanned=null;$("#scan").hidden=false;$("#scan").classList.remove("leaving");$("#res").hidden=true;$("#again").hidden=true;$("#prog").hidden=true;$("#act").hidden=true;setText($("#go"),"Avvia analisi")}
function driveCard(x){const pct=x.total?Math.min(100,Math.round(x.used/x.total*100)):0;return `<label class=dcard><input type=checkbox checked value="${esc(x.path)}"><b>${esc(x.path)}</b><small>${fmt(x.used)} usati · ${fmt(x.free)} liberi su ${fmt(x.total)}</small><span class=pct>${pct}%</span><div class=bar><i style="width:${pct}%"></i></div></label>`}
function crossReplace(el,html,done){const apply=()=>{if(!el)return;el.innerHTML=html;el.classList.remove("leaving");showIn(el);done&&done()};if(!el)return;if(REDUCE()){apply();return}el.classList.add("leaving");setTimeout(apply,180)}
function updatePick(){const el=$("#pick");if(!el)return;const all=document.querySelectorAll("#drv input").length,n=document.querySelectorAll("#drv input:checked").length;el.textContent=all?(n+" di "+all+" "+(all===1?"disco selezionato":"dischi selezionati")):"Nessun disco rilevato su questo computer."}
function paintStatus(){
 const el=$("#sys");if(!el)return;
 const plat={mac:"macOS",win:"Windows",linux:"Linux"}[PLAT]||PLAT;
 const rows=[["Piattaforma",plat],["Connessione","Solo questo computer (127.0.0.1)"],["Account",ME?(ME.name?ME.name+" · "+ME.email:ME.email):"—"],["Accesso Google",GOOGLE?"Configurato":"Non configurato"],["Email per la password",MAIL?"Server di posta configurato":"Non configurato"],["Analisi",running?"In corso":(R&&R.folders?"Risultati pronti":"In attesa")]];
 if(scanned!=null)rows.push(["File letti in questa sessione",scanned.toLocaleString("it")]);
 if(R&&R.folders){rows.push(["Cartelle non accessibili",(R.denied||0).toLocaleString("it")]);rows.push(["Lettura RAR e 7z",R.tool?"Disponibile":"Non disponibile"])}
 const html=rows.map(([k,v])=>`<div class=kv><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
 if(el.dataset.h!==html){el.dataset.h=html;el.innerHTML=html}}
function hello(){const h=new Date().getHours(),p=h<5?"Buonanotte":h<12?"Buongiorno":h<18?"Buon pomeriggio":"Buonasera",g=$("#greet");if(g)g.textContent=ME&&ME.name?p+", "+ME.name:p}
async function loadDrives(){
 const d=await api("/api/drives");if(!Array.isArray(d))return;
 const html=d.length?d.map(driveCard).join(""):`<p class=s>Nessun disco rilevato su questo computer.</p>`;
 const used=d.reduce((a,x)=>a+(x.used||0),0),total=d.reduce((a,x)=>a+(x.total||0),0),free=d.reduce((a,x)=>a+(x.free||0),0);
 const sum=`<div class=metric><small>Spazio usato</small><b>${fmt(used)}</b></div><div class=metric><small>Spazio libero</small><b>${fmt(free)}</b></div><div class=metric><small>Capacità</small><b>${fmt(total)}</b><small>${d.length} ${d.length===1?"disco":"dischi"}</small></div>`;
 crossReplace($("#drv"),html,updatePick);crossReplace($("#disksum"),sum)}
async function enterApp(){
 const open=async()=>{
  $("#auth").hidden=true;$("#auth").classList.remove("leaving");$("#intro").hidden=true;$("#app").hidden=false;showIn($("#app"));
  $("#who").textContent=ME?(ME.name?ME.name+" · "+ME.email:ME.email):"";resetUI();hello();paintStatus();
  const drives=loadDrives();
  const s=await api("/api/status");
  if(s.phase==="done"&&s.has_res){R=await api("/api/results");if(R&&R.folders){idx();render()}}
  else if(["scan","agg","dups","arch"].includes(s.phase)){running=true;setText($("#go"),"Ferma");$("#prog").hidden=false;showIn($("#prog"));timer=setInterval(poll,600);poll()}
  paintStatus();await drives};
 if(!$("#auth").hidden)hideAnimated($("#auth"),()=>{open()});else open()}
function stopPoll(){clearInterval(timer);running=false}
function list(){
 let L=tab==="folders"?R.folders:tab==="games"?R.folders.filter(x=>x.cat==="Gioco"):tab==="files"?R.files:R.archives;
 if(tab==="folders"||tab==="files")L=L.filter(x=>filt==="Tutti"||x.cat===filt);
 if(q)L=L.filter(x=>x.path.toLowerCase().includes(q));
 return [...L].sort((a,b)=>sortk==="name"?a.name.localeCompare(b.name):sortk==="date"?(a.mtime||0)-(b.mtime||0):b.size-a.size)}
function row(x,mx){
 const isA=tab==="arch",ck=tab==="files"||isA,pl=isA?pill(...LV[x.level]):pill(x.cat,PC[x.cat]);
 const why=isA?x.why+(x.vols.length>1?` · ${x.vols.length} parti`:""):x.why+(x.files!=null?" · "+x.files.toLocaleString("it")+" file":"");
 return `<div class="row ${ck?"":"nc"}">${ck?`<input type=checkbox data-s="${esc(x.path)}" ${sel.has(x.path)?"checked":""}>`:""}${pl}<div class=nm><b>${esc(x.name)}</b><small>${esc(x.path)}</small><small>${esc(why)}${x.mtime?" · modificato il "+dt(x.mtime):""}</small></div><div>${fmt(x.size)}<div class=bar><i style="width:${Math.max(2,x.size/mx*100)}%"></i></div></div><button class=btn data-p="${esc(x.path)}">${OSN[PLAT].show}</button></div>`}
function home(){
 const tot=R.totals||{},rec=(tot["Scarto"]||0)+(R.wasted||0)+(R.arch_total||0),O=OSN[PLAT];
 const folders=R.folders||[],files=R.files||[],dups=R.dups||[],arch=R.archives||[],games=folders.filter(x=>x.cat==="Gioco"),disks=R.disks||[];
 const used=disks.reduce((a,d)=>a+(d.used||0),0),total=disks.reduce((a,d)=>a+(d.total||0),0),free=disks.reduce((a,d)=>a+(d.free||0),0);
 const catSum=CATS.reduce((a,c)=>a+(tot[c]||0),0);
 let h=`<div class=hero><small>Spazio recuperabile stimato</small><big>${fmt(rec)}</big><p>Somma delle cartelle di scarto, delle copie doppie e degli archivi già estratti. Nulla viene eliminato senza la tua conferma e tutto va nel Cestino.</p></div>`;
 if(R.denied)h+=`<div class=warn><b>${R.denied.toLocaleString("it")}</b> cartelle non erano accessibili e sono state saltate. ${O.perm}</div>`;
 if(!R.tool)h+=`<div class=warn>${O.tool}</div>`;
 const stats=[["Cartelle elencate",folders.length.toLocaleString("it"),"folders"],["File grandi",files.length.toLocaleString("it"),"files"],["Giochi",games.length.toLocaleString("it"),"games"],["Gruppi di doppioni",dups.length.toLocaleString("it"),"dups"],["Archivi già estratti",arch.length.toLocaleString("it"),"arch"],["Copie in più",fmt(R.wasted||0),"dups"],["Scarto",fmt(tot["Scarto"]||0),"folders|Scarto"],["Spazio libero sui dischi",fmt(free),""]];
 h+=`<div class=statgrid>`+stats.map(([l,n,go])=>go?`<button type=button class=k data-go="${go}"><small>${esc(l)}</small><b>${n}</b></button>`:`<div class=k><small>${esc(l)}</small><b>${n}</b></div>`).join("")+`</div>`;
 h+=`<div class=split><div class=card><h2>Per categoria</h2><p class=s>Peso delle cartelle elencate, non dell'intero disco.</p>`+CATS.map(c=>{const v=tot[c]||0,p=catSum?v/catSum*100:0;return `<div class=catrow>${pill(c,PC[c])}<b>${fmt(v)}</b><div class=bar><i style="width:${p.toFixed(1)}%"></i></div></div>`}).join("")+`</div>`;
 h+=`<div class=card><h2>Azioni rapide</h2><p class=s>Apri una sezione dei risultati di questa analisi.</p><div class=qacts>
 <button type=button class=qbtn data-go="folders|Scarto">Rivedi scarti<small>${fmt(tot["Scarto"]||0)}</small></button>
 <button type=button class=qbtn data-go="dups">Rivedi doppioni<small>${fmt(R.wasted||0)}</small></button>
 <button type=button class=qbtn data-go="arch">Rivedi archivi<small>${fmt(R.arch_total||0)}</small></button>
 <button type=button class=qbtn data-go="games">Vedi giochi<small>${fmt(tot["Gioco"]||0)}</small></button>
 <button type=button class=qbtn data-go="files">File grandi<small>${files.length.toLocaleString("it")}</small></button>
 </div></div></div>`;
 if(folders.length){const top=folders.slice(0,4),mx=top[0].size||1;h+=`<div class=card><h2>Cartelle più pesanti</h2><p class=s>Le più grandi trovate in questa analisi.</p>`+top.map(x=>`<div class="row nc">${pill(x.cat,PC[x.cat])}<div class=nm><b>${esc(x.name)}</b><small>${esc(x.path)}</small></div><div>${fmt(x.size)}<div class=bar><i style="width:${Math.max(2,x.size/mx*100)}%"></i></div></div><button type=button class=btn data-p="${esc(x.path)}">${O.show}</button></div>`).join("")+`<div class=r style="margin-top:12px"><button type=button class=btn data-go="folders">Tutte le cartelle</button></div></div>`}
 h+=`<div class=card><h2>Dischi</h2><p class=s>${fmt(used)} usati · ${fmt(free)} liberi · ${fmt(total)} di capacità, sui dischi letti.</p>`+(disks.length?disks.map(d=>`<p class=s style="margin:14px 0 0">${esc(d.path)} · ${fmt(d.used)} usati di ${fmt(d.total)} · liberi ${fmt(d.free)}</p><div class=bar><i style="width:${d.total?d.used/d.total*100:0}%"></i></div>`).join(""):`<p class=s>Nessun disco nel risultato.</p>`)+`</div>`;
 h+=`<div class=card><h2>Come leggere le etichette</h2><div class="leg" style="margin-top:14px">`+CATS.map(c=>`<div>${pill(c,PC[c])} ${esc(LEG[c])}</div>`).join("")+`</div></div>`;
 if(scanned!=null)h+=`<p class=s>File letti in questa sessione: ${scanned.toLocaleString("it")}.</p>`;
 return h}
function render(){
 if(!R||!R.folders)return;
 const n={folders:R.folders.length,games:R.folders.filter(x=>x.cat==="Gioco").length,files:R.files.length,dups:R.dups.length,arch:R.archives.length};
 const navHtml=NAV.map(([k,t])=>`<button type=button class="nv ${k===tab?"on":""}" data-t="${k}">${t}${n[k]!=null?`<em>${n[k]}</em>`:""}</button>`).join("");
 const nav=$("#nav");if(nav.dataset.h!==navHtml){nav.dataset.h=navHtml;nav.innerHTML=navHtml}
 let h="";
 if(tab==="home")h=home();
 else{
  h=`<div class=card><h2>${NAV.find(x=>x[0]===tab)[1]}</h2><p class=s>${INTRO[tab]}</p>`;
  if(tab==="arch"&&!R.archives.length)h+=`<p class=s>Nessun archivio già estratto trovato.</p>`;
  h+=`<div class=r><input type=text id=q placeholder="Cerca per nome o percorso…" value="${esc(q)}" style="flex:1;min-width:200px"><select id=so><option value=size ${sortk==="size"?"selected":""}>Più grandi prima</option><option value=name ${sortk==="name"?"selected":""}>Nome</option><option value=date ${sortk==="date"?"selected":""}>Più vecchi prima</option></select><button class=btn id=csv>Esporta CSV</button>`;
  if(tab==="arch")h+=`<button class=btn id=selok>Seleziona i già estratti</button>`;
  if(tab==="dups")h+=`<button class=btn id=keep>Tieni solo la copia più vecchia</button>`;
  h+=`</div>`;
  if(tab==="folders"||tab==="files")h+=`<div class=r>`+["Tutti",...CATS].map(c=>`<button class="chip ${c===filt?"on":""}" data-f="${esc(c)}">${esc(c)}</button>`).join("")+`</div>`;
  if(tab==="dups"){
   const G=R.dups.filter(g=>!q||g.paths.some(p=>p.toLowerCase().includes(q)));
   h+=`<p class=s style="margin-top:16px">Recuperabile eliminando le copie: <b>${fmt(R.wasted)}</b></p>`+(G.length?G.map(g=>`<div class=grp><b>${g.paths.length} copie × ${fmt(g.size)}</b> · spreco ${fmt(g.wasted)}${g.paths.map(p=>`<div class=cp><input type=checkbox data-s="${esc(p)}" ${sel.has(p)?"checked":""}><span>${esc(p)}</span><button class=btn data-p="${esc(p)}">${OSN[PLAT].show}</button></div>`).join("")}</div>`).join(""):"<p class=s>Nessun doppione trovato (o ricerca disattivata).</p>");
  }else{const L=list(),mx=Math.max(1,...L.map(x=>x.size));h+=`<div style="margin-top:14px">`+(L.length?L.map(x=>row(x,mx)).join(""):"<p class=s>Niente da mostrare con questi filtri.</p>")+`</div>`}
  h+=`</div>`}
 const typing=document.activeElement&&document.activeElement.id==="q";
 const paint=()=>{
  $("#again").hidden=false;$("#res").hidden=false;$("#view").innerHTML=h;
  if(typing){const e=$("#q");if(e){e.focus();e.setSelectionRange(e.value.length,e.value.length)}}
  else showIn($("#view"));
  act();paintStatus()};
 if($("#res").hidden){
  if($("#scan").classList.contains("leaving")){$("#view")._pending=h;return}
  hideAnimated($("#scan"),()=>{$("#prog").hidden=true;if($("#view")._pending){h=$("#view")._pending;$("#view")._pending="";paint()}});
  try{window.scrollTo(0,0)}catch(e){}
  paint();
 }else paint()}
function act(){
 const a=$("#act");if(!sel.size){if(!a.hidden)hideAnimated(a);return}
 let s=0;sel.forEach(p=>s+=AM[p]?AM[p].size:(SZ[p]||0));
 const was=a.hidden;a._tok=(a._tok||0)+1;a.hidden=false;a.classList.remove("leaving");
 a.innerHTML=`<span><b>${sel.size}</b> selezionati · <b>${fmt(s)}</b></span><button type=button class=btn id=clr>Deseleziona</button><button type=button class=dng id=del>Sposta nel Cestino</button>`;
 if(was)showIn(a)}
async function trash(){
 const paths=[];sel.forEach(p=>{if(AM[p])AM[p].vols.forEach(v=>paths.push(v[0]));else paths.push(p)});
 if(!await ask("Spostare nel Cestino?",`${paths.length} file verranno spostati nel Cestino.\nPotrai recuperarli da lì. Di ogni gruppo di doppioni resta sempre almeno una copia.`,"Sposta nel Cestino"))return;
 toast("Sposto nel Cestino… può richiedere qualche istante.",60000);
 const r=await api("/api/trash",{paths});
 if(r.error){toast("Errore: "+r.error);return}
 sel.clear();R=await api("/api/results");idx();render();
 toast(`Spostati ${r.done.length} file · liberati ${fmt(r.freed)}`+(r.failed.length?` · ${r.failed.length} non spostati: ${r.failed[0][1]}`:""),9000)}
function idx(){AM={};SZ={};R.files.forEach(f=>SZ[f.path]=f.size);R.archives.forEach(a=>AM[a.path]=a);R.dups.forEach(g=>g.paths.forEach(p=>SZ[p]=g.size))}
const cell=v=>{let s=String(v);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'};
document.addEventListener("click",async e=>{
 const g=id=>e.target.closest(id),p=g("[data-p]"),f=g("[data-f]"),t=g("[data-t]"),o=g("[data-go]"),am=g("[data-am]");
 if(am){e.preventDefault();return showAuth(am.dataset.am)}
 if(g("#reintro")){e.preventDefault();hideAnimated($("#auth"),()=>{$("#intro").hidden=false;slide(0)})}
 if(g("#gg")&&GOOGLE){googleGo()}
 if(p)api("/api/reveal",{path:p.dataset.p});
 if(f){filt=f.dataset.f;render()}
 if(t){tab=t.dataset.t;q="";render()}
 if(o){const[a,b]=o.dataset.go.split("|");tab=a;filt=b||"Tutti";q="";render()}
 if(g("#clr")){sel.clear();render()}
 if(g("#act #del"))trash();
 if(g("#selok")){R.archives.filter(a=>a.level==="ok").forEach(a=>sel.add(a.path));render()}
 if(g("#keep")){R.dups.forEach(d=>{const k=d.mt.indexOf(Math.min(...d.mt));d.paths.forEach((x,i)=>i!==k&&sel.add(x))});render()}
 if(g("#csv")){
  const rows=tab==="dups"?R.dups.flatMap(d=>d.paths.map(x=>[d.size,d.paths.length,x])):list().map(x=>[x.cat||x.level,x.size,x.path,x.why]);
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\ufeff"+rows.map(r=>r.map(cell).join(";")).join("\n")],{type:"text/csv"}));a.download="twenties_cleaning.csv";a.click()}});
document.addEventListener("change",e=>{
 if(e.target.dataset.s){e.target.checked?sel.add(e.target.dataset.s):sel.delete(e.target.dataset.s);act()}
 if(e.target.id==="so"){sortk=e.target.value;render()}
 if(e.target.closest&&e.target.closest("#drv"))updatePick()});
document.addEventListener("input",e=>{if(e.target.id==="q"){q=e.target.value.toLowerCase();render()}});
$("#th").onclick=()=>{const h=document.documentElement,n=h.dataset.th==="dark"?"light":"dark";h.dataset.th=n;try{localStorage.setItem("tc_th",n)}catch(e){}};
$("#again").onclick=()=>{if($("#scan").hidden){$("#scan").hidden=false;showIn($("#scan"))}hideAnimated($("#res"),()=>{$("#again").hidden=true})};
$("#out").onclick=async()=>{const r=await api("/api/logout",{});stopPoll();ME=null;if(r.csrf)CSRF=r.csrf;resetUI();showAuth("login")};
$("#del").onclick=()=>{
 const m=$("#modal");
 m.innerHTML=`<div class=sheet role=dialog aria-modal=true aria-labelledby=dh><h3 id=dh>Eliminare account e dati?</h3><p>Verranno cancellati per sempre il tuo account e i dati di accesso salvati su questo computer. I file del computer non vengono toccati.</p><input type=password id=dpw placeholder="Password (se l'account ne ha una)" autocomplete=current-password maxlength=128 aria-label="Password per confermare"><div id=de class=fe role=alert></div><div class=sb><button type=button class=btn id=dn>Annulla</button><button type=button class=pri id=dy>Elimina tutto</button></div></div>`;
 m._tok=(m._tok||0)+1;m.hidden=false;m.classList.remove("leaving");const close=()=>hideAnimated(m,()=>{m.innerHTML=""});
 $("#dpw").focus();$("#dn").onclick=close;
 $("#dy").onclick=async()=>{const b=$("#dy");b.disabled=true;const r=await api("/api/delete_account",{password:$("#dpw").value});b.disabled=false;
  if(r.error){$("#de").textContent=r.error;return}
  close();stopPoll();ME=null;if(r.csrf)CSRF=r.csrf;resetUI();showAuth("login",()=>fe("Account e dati eliminati.",true))};
};
$("#quit").onclick=async()=>{if(await ask("Chiudere Twenties Cleaning?","Il programma verrà chiuso. Per riaprirlo dovrai avviarlo di nuovo.","Chiudi")){await api("/api/quit",{});document.body.innerHTML='<main><div class=card><h2>Programma chiuso</h2><p class=s>Puoi chiudere questa scheda.</p></div></main>'}};
async function poll(){
 const s=await api("/api/status");if(!s||s.error)return;
 const stepsHtml=Object.entries(STEPS).map(([k,v])=>`<span class="st ${k===s.phase?"on":""}">${v}</span>`).join("");
 const steps=$("#steps");if(steps&&steps.dataset.h!==stepsHtml){steps.dataset.h=stepsHtml;steps.innerHTML=stepsHtml}
 const b=$("#bar"),m=$("#msg");
 if((s.phase==="scan"||s.phase==="done")&&typeof s.count==="number")scanned=s.count;
 if(s.phase==="scan"){if(b)b.hidden=true;if(m)m.textContent=(s.count||0).toLocaleString("it")+" file letti · "+(s.current||"")}
 else if(s.phase==="agg"){if(b)b.hidden=true;if(m)m.textContent="Calcolo le cartelle…"}
 else if(s.phase==="dups"||s.phase==="arch"){if(b){b.hidden=false;b.className="bar";if(b.firstChild)b.firstChild.style.width=(s.done/Math.max(1,s.total)*100)+"%"}if(m)m.textContent=(s.done||0).toLocaleString("it")+" / "+(s.total||0).toLocaleString("it")+" elementi controllati"}
 paintStatus();
 if(s.phase==="done"||s.phase==="idle"){
  stopPoll();setText($("#go"),"Avvia analisi");
  if(s.error){$("#prog").hidden=true;toast("Errore: "+s.error);return}
  if(s.phase==="done"){R=await api("/api/results");sel.clear();tab="home";if(R&&R.folders){idx();render()}else $("#prog").hidden=true}
  else $("#prog").hidden=true}}
$("#go").onclick=async()=>{
 if(running){await api("/api/stop",{});setText($("#go"),"Interrompo…");return}
 const roots=[...document.querySelectorAll("#drv input:checked")].map(i=>i.value),c=$("#custom").value.trim();if(c)roots.push(c);
 if(!roots.length)return toast("Seleziona almeno un disco o scrivi una cartella.");
 const r=await api("/api/start",{roots,dups:$("#dups").checked,arch:$("#arch").checked,minmb:+$("#minmb").value||5});
 if(r.error)return toast(r.error);
 running=true;scanned=0;setText($("#go"),"Ferma");$("#prog").hidden=false;showIn($("#prog"));paintStatus();
 try{$("#prog").scrollIntoView({behavior:REDUCE()?"auto":"smooth",block:"nearest"})}catch(e){}
 timer=setInterval(poll,600);poll()};
(async()=>{
 const m=await api("/api/me");CSRF=m.csrf||"";ME=m.user||null;GOOGLE=!!m.google;MAIL=!!m.mail;PLAT=OSN[m.platform]?m.platform:"linux";
 const p=new URLSearchParams(location.search);
 if(location.pathname==="/reset"){RT=(p.get("token")||"").slice(0,100);history.replaceState(null,"","/")}
 else if(p.get("e")){FLASH=EMSG[p.get("e")]||null;history.replaceState(null,"","/")}
 let seen=false;try{seen=localStorage.getItem("tc_intro")==="1"}catch(e){}
 if(!seen&&!ME&&!RT){$("#intro").hidden=false;slide(0)}else route()})();
</script></body></html>
"""


def env_on(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def launch_mode(argv):
    args = set(argv[1:])
    if "--headless" in args or env_on("TC_HEADLESS"):
        return "headless"
    if "--browser" in args or env_on("TC_BROWSER"):
        return "browser"
    return "window"


def console_visible():
    if getattr(sys, "frozen", False):
        return False
    try:
        return sys.stderr is not None and sys.stderr.isatty()
    except Exception:
        return False


def notify(msg, error=True):
    """Messaggio visibile anche nell'eseguibile senza terminale (--windowed)."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass
    if MODE == "headless" or console_visible():
        return
    try:
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, APP, 0x00000010 if error else 0x00000040)
        elif IS_MAC:
            parts = []
            for line in msg.split("\n"):
                parts.append('"' + line.replace("\\", "\\\\").replace('"', '\\"') + '"')
            text = " & return & ".join(parts)
            icon = "caution" if error else "note"
            subprocess.run(["osascript", "-e", f'display dialog {text} with title "{APP}" buttons {{"OK"}} default button 1 with icon {icon}'],
                           check=False, timeout=120)
        else:
            subprocess.run(["zenity", "--error" if error else "--info", "--no-wrap", "--title", APP, "--text", msg],
                           check=False, timeout=120)
    except Exception:
        pass


def give_up(code, msg):
    notify(msg, error=code != 0)
    raise SystemExit(code)


def port_is_open(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def addr_in_use(exc):
    n, w = getattr(exc, "errno", None), getattr(exc, "winerror", None)
    return n in (errno.EADDRINUSE, 98, 48, 10048) or w in (10048,)


def local_opener():
    """Le richieste a 127.0.0.1 non devono passare da un proxy di sistema."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def identify(port):
    """Chi risponde sulla porta: la nostra versione, una copia precedente, o qualcos'altro."""
    try:
        req = urllib.request.Request(f"http://{HOST}:{port}/api/me", headers={"Accept": "application/json"})
        with local_opener().open(req, timeout=2) as r:
            server, raw, code = r.headers.get("Server", ""), r.read(65536), r.status
    except urllib.error.HTTPError as e:
        server, raw, code = e.headers.get("Server", ""), e.read(65536), e.code
    except Exception:
        return "other", None
    if not str(server).startswith("TwentiesCleaning"):
        return "other", None
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        data = None
    if code == 200 and isinstance(data, dict) and data.get("app") == APP and data.get("version") == VERSION:
        return "ours", data
    return "old", data


def finish_because_busy(kind, info, port):
    """Non avviare una seconda copia: o si porta avanti quella giusta, o si spiega l'errore."""
    if kind == "ours":
        try:
            local_opener().open(f"http://{HOST}:{port}/api/focus", timeout=3).read()
        except Exception:
            pass
        print(f"{APP} è già aperto: porto in primo piano la finestra esistente.", file=sys.stderr, flush=True)
        if MODE != "headless" and not (info or {}).get("window"):
            try:
                webbrowser.open(f"http://{HOST}:{port}/")
            except Exception:
                pass
        raise SystemExit(0)
    if kind == "old":
        give_up(1, (
            f"Twenties Cleaning non si è avviato.\n\n"
            f"La porta {port} è già usata da una versione precedente del programma, ancora aperta su questo computer. "
            f"Se ne aprissi un'altra vedresti la schermata vecchia.\n\n"
            f"Chiudi quella copia (dalla barra delle applicazioni, oppure da Gestione attività su Windows "
            f"o Monitoraggio Attività su Mac) e riapri Twenties Cleaning."
        ))
    give_up(1, (
        f"Twenties Cleaning non si è avviato.\n\n"
        f"La porta {port} è occupata da un altro programma. Chiudilo e riprova. "
        f"Non ho avviato una seconda copia."
    ))


def app_icon():
    roots = []
    if getattr(sys, "frozen", False):
        me = getattr(sys, "_MEIPASS", "")
        if me:
            roots.append(me)
        roots.append(os.path.dirname(sys.executable))
    here = os.path.dirname(os.path.abspath(__file__))
    roots += [os.path.dirname(here), here]
    names = ("assets/icon.ico", "icon.ico") if IS_WIN else ("assets/icon.png", "assets/icon.icns", "icon.png", "icon.icns")
    for root in roots:
        for name in names:
            p = os.path.join(root, name)
            if os.path.isfile(p):
                return p
    return None


def open_in_browser(url):
    """Link esterni (e il consenso Google) nel browser di sistema, mai nella finestra dell'app."""
    try:
        u = urllib.parse.urlsplit(str(url))
        port = u.port
    except Exception:
        return
    if u.scheme not in ("http", "https") or not u.hostname:
        return
    if u.hostname.lower() in ("127.0.0.1", "localhost") and (port or (443 if u.scheme == "https" else 80)) == PORT:
        return
    try:
        webbrowser.open(u.geturl())
    except Exception:
        pass


class DesktopBridge:
    def open_external(self, url):
        open_in_browser(url)


def stop_server(srv, th=None):
    try:
        srv.shutdown()
    except Exception:
        pass
    try:
        srv.server_close()
    except Exception:
        pass
    if th is not None and th.is_alive():
        th.join(3)


def run_window(srv, th, folder):
    """True se l'utente ha chiuso la finestra (il server è già spento). False se bisogna usare il browser."""
    global WINDOW, WINDOW_MODE
    shown = {"ok": False}
    try:
        import webview
    except Exception as e:
        print("Finestra non disponibile:", type(e).__name__, e, file=sys.stderr, flush=True)
        return False
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass
    icon = app_icon()
    try:
        WINDOW = webview.create_window(APP, BASE + "/", js_api=DesktopBridge(), width=1280, height=820,
                                       min_size=(900, 640), background_color="#f5f5f7")
        WINDOW_MODE = True

        def on_shown():
            shown["ok"] = True

        WINDOW.events.shown += on_shown
        storage = os.path.join(folder, "webview")
        os.makedirs(storage, exist_ok=True)
        if not IS_WIN:
            try:
                os.chmod(storage, 0o700)
            except OSError:
                pass
        kw = {"private_mode": False, "storage_path": storage, "http_server": False}
        if icon:
            kw["icon"] = icon
        webview.start(**kw)
    except Exception as e:
        print("Finestra non disponibile:", type(e).__name__, e, file=sys.stderr, flush=True)
        closed = shown["ok"]
        WINDOW, WINDOW_MODE = None, False
        if closed:  # l'utente aveva già la finestra: chiudere non deve riaprire il browser
            stop_server(srv, th)
            return True
        return False
    if not shown["ok"]:
        print("La finestra non si è aperta.", file=sys.stderr, flush=True)
        WINDOW, WINDOW_MODE = None, False
        return False
    WINDOW, WINDOW_MODE = None, False
    stop_server(srv, th)
    return True


FALLBACK_MSG = (
    "Non riesco ad aprire la finestra di Twenties Cleaning.\n\n"
    "Manca il componente di sistema (su Windows serve WebView2, già presente su Windows 11 e sulla maggior parte di Windows 10).\n\n"
    "Apro il programma nel browser."
)


def main():
    global WINDOW, WINDOW_MODE, MODE
    global PORT, SCHEME, BASE, TLS_ON, SN, PN, G_ID, G_SECRET, DUMMY
    quiet_streams()
    MODE = launch_mode(sys.argv)
    if sys.version_info < (3, 8):
        sys.exit("Serve Python 3.8 o più recente.")
    if not hasattr(hashlib, "scrypt"):
        sys.exit("Questo Python non supporta scrypt (serve OpenSSL 1.1 o più recente).")
    if not IS_WIN:
        os.umask(0o077)  # file creati leggibili solo dal tuo utente
        if os.geteuid() == 0:
            print("Attenzione: stai usando il programma come root. Non è necessario.")
    elif IS_WIN:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("Nota: non sei Amministratore, alcune cartelle protette verranno saltate.")
    d = data_dir()
    log_to_file(d)
    load_env(d)
    want = int(os.environ.get("TC_PORT", "8765") or 8765)
    if want and port_is_open(HOST, want):
        kind, info = identify(want)
        finish_because_busy(kind, info, want)
        return
    G_ID = (os.environ.get("GOOGLE_CLIENT_ID") or getattr(_GC, "CLIENT_ID", "") or "").strip()
    G_SECRET = (os.environ.get("GOOGLE_CLIENT_SECRET") or getattr(_GC, "CLIENT_SECRET", "") or "").strip()
    init_db(os.path.join(d, "twenties.db"))
    DUMMY = hash_pw(secrets.token_hex(8))
    try:
        srv = ThreadingHTTPServer((HOST, want), H)
    except OSError as e:
        if want and addr_in_use(e):
            kind, info = identify(want) if port_is_open(HOST, want) else ("other", None)
            finish_because_busy(kind, info, want)
            return
        raise
    srv.daemon_threads = True
    PORT = srv.server_address[1]
    cert, keyf = os.environ.get("TC_TLS_CERT"), os.environ.get("TC_TLS_KEY")
    if cert and keyf:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, keyf)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)
        TLS_ON, SCHEME = True, "https"
        SN, PN = "__Host-tc_s", "__Host-tc_p"
    BASE = f"{SCHEME}://{HOST}:{PORT}"
    print(f"{APP} {VERSION} su {BASE}/")
    print("Sicurezza: " + ("HTTPS attivo." if TLS_ON else "connessione solo locale (127.0.0.1, nulla esce dal computer). Per HTTPS vedi LEGGIMI."))
    print("Accesso con Google: " + ("attivo." if G_ID and G_SECRET else "non configurato (vedi LEGGIMI)."))
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    if MODE == "window":
        print("Si apre la finestra dell'app. Chiudendola, il programma termina.")
        if run_window(srv, th, d):
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            os._exit(0)  # niente thread rimasti di pywebview, e la porta è già libera
        WINDOW, WINDOW_MODE = None, False
        notify(FALLBACK_MSG)
        try:
            webbrowser.open(BASE + "/")
        except Exception:
            notify(f"Apri manualmente questo indirizzo nel browser:\n{BASE}/")
    elif MODE == "browser":
        print("Apro il browser. Per uscire usa Chiudi app oppure premi Ctrl+C.")
        try:
            webbrowser.open(BASE + "/")
        except Exception:
            notify(f"Apri manualmente questo indirizzo nel browser:\n{BASE}/")
    else:
        print("Modalità senza finestra. Per uscire premi Ctrl+C.")
    try:
        while th.is_alive():
            th.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server(srv, th)


if __name__ == "__main__":
    main()
