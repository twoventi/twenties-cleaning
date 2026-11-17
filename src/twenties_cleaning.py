#!/usr/bin/env python3
"""Twenties - mostra cosa pesa sul PC / Mac e lascia decidere a te.
Python 3.8+ e pywebview per la finestra (se manca, si apre il browser). Sposta solo su tua conferma e solo nel Cestino.
Avvio:  python3 src/twenties_cleaning.py   -> finestra dell'app, usabile anche senza account.
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


def launcher_info(path):
    """Quale launcher, se il percorso lo dice. Il link apre la libreria, non un gioco preciso."""
    low = path.replace("\\", "/").lower()
    rules = (
        ("steamapps/common", "Steam", "https://store.steampowered.com/"),
        ("epic games", "Epic", "https://store.epicgames.com/"),
        ("gog galaxy/games", "GOG Galaxy", "https://www.gog.com/account"),
        ("gog games", "GOG", "https://www.gog.com/account"),
        ("riot games", "Riot", "https://www.riotgames.com/"),
        ("ubisoft game launcher/games", "Ubisoft", "https://ubisoftconnect.com/"),
        ("ea games", "EA", "https://www.ea.com/ea-app"),
        ("origin games", "EA", "https://www.ea.com/ea-app"),
        ("xboxgames", "Xbox", "https://www.xbox.com/play"),
    )
    for needle, name, url in rules:
        if needle in low:
            return name, url
    return "", ""


def walk(roots, minb):
    dirs, markers, sizes, top, archs, junk, n = {}, set(), {}, [], [], [], 0
    stack = list(roots)
    while stack and not S["stop"]:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            S["denied"] += 1
            continue
        st, names, subs = [0, 0, 0, 0, 0, 0, 0, 0], set(), set()
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
                    at = getattr(s, "st_atime", 0) or 0
                    if at > st[7]:
                        st[7] = at
                    if not nodup and len(junk) < 2000 and sz > 0:
                        parent = set(re.split(r"[\\/]", d.lower()))
                        if ext in JUNK_EXT or (parent & JUNK_DIRS) or (ext in INSTALLER_EXT and parent & {"downloads", "download"}):
                            junk.append({"path": e.path, "name": e.name, "size": sz, "mtime": s.st_mtime})
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
    return dirs, markers, sizes, top, archs, junk


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
        rec = {"path": p, "name": os.path.basename(p) or p, "size": size, "files": t[6], "mtime": t[5],
               "atime": t[7] if len(t) > 7 else 0, "cat": cat, "why": why}
        if cat == GAME:
            ln, lu = launcher_info(p)
            rec["launcher"], rec["launcher_url"] = ln, lu
        out.append(rec)
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


def map_tree(tot, kids):
    """Albero per la mappa. Limita profondità e figli così il disegno resta leggibile."""
    roots = [p for p in tot if os.path.dirname(p) == p or os.path.dirname(p) not in tot]
    allow, sizes, budget = set(), {}, [1200]

    def node(p, depth):
        if budget[0] <= 0 or p not in tot:
            return None
        t = tot[p]
        size = sum(t[:5])
        if size <= 0 and depth:
            return None
        budget[0] -= 1
        sp = special(p)
        cat, why = sp or by_content(p, t)
        children = []
        if depth < 5:
            subs = []
            for c in kids.get(p, ()):
                if c in tot:
                    subs.append((sum(tot[c][:5]), c))
            subs = [(s, c) for s, c in sorted(subs, reverse=True) if s > 0][:18]
            for _s, c in subs:
                n = node(c, depth + 1)
                if n:
                    children.append(n)
        allow.add(p)
        sizes[p] = size
        return {"name": os.path.basename(p) or p, "path": p, "size": size, "cat": cat, "why": why,
                "mtime": t[5], "atime": t[7] if len(t) > 7 else 0, "children": children}

    out = []
    for r in roots:
        n = node(r, 0)
        if n:
            out.append(n)
    return out, allow, sizes


def build(dirs, markers, top, junk=None):
    tot, kids = {p: list(v) for p, v in dirs.items()}, {}
    for p in sorted(dirs, key=lambda x: x.count(os.sep), reverse=True):
        par = os.path.dirname(p)
        if par != p and par in tot:
            kids.setdefault(par, []).append(p)
            a, b = tot[par], tot[p]
            for i in (0, 1, 2, 3, 4, 6):
                a[i] += b[i]
            a[5] = max(a[5], b[5])
            a[7] = max(a[7], b[7])
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
    tree, allow, dirsize = map_tree(tot, kids)
    C["dirs"], C["dirsize"] = allow, dirsize
    C["map_roots"] = {n["path"] for n in tree}
    files = []
    for sz, p, m in sorted(top, reverse=True):
        c, w = fclass(p, m)
        files.append({"path": p, "name": os.path.basename(p), "size": sz, "mtime": m, "files": None, "cat": c, "why": w})
    totals = {}
    for f in folders:
        totals[f["cat"]] = totals.get(f["cat"], 0) + f["size"]
    junk = list(junk or [])
    covered = [f["path"] for f in folders if f["cat"] == JUNK]
    extra = []
    for j in junk:
        jp = j["path"]
        if not any(jp == c or jp.startswith(c + os.sep) for c in covered):
            extra.append(j)
    scarto_folders = sum(f["size"] for f in folders if f["cat"] == JUNK)
    scarto_files = sum(j["size"] for j in extra)
    return {"folders": folders, "files": files, "totals": totals, "map": tree,
            "games": [f for f in folders if f["cat"] == GAME],
            "junk_files": junk, "scarto_extra": extra,
            "scarto_total": scarto_folders + scarto_files}


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
                    res.append({"size": sz, "paths": ps, "mt": mt, "wasted": sz * (len(h) - 1),
                                "hash": "blake2b", "exact": True})
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
                lvl, why, code = "ok", f"Tutti i {n} file dell'archivio sono già presenti in: {where}", "arch.ok"
            elif ratio >= .6:
                lvl, why, code = "part", f"Estratto solo in parte ({ratio:.0%}) in: {where}. Controlla prima di eliminare", "arch.part"
            else:
                continue
        elif nm.lower().endswith((".rar", ".7z", ".zip")) and os.path.isdir(bases[1]):
            try:
                with os.scandir(bases[1]) as it:
                    if next(it, None) is None:
                        continue
            except OSError:
                continue
            lvl, n, where, code = "guess", 0, bases[1], "arch.guess"
            why = "Esiste una cartella con lo stesso nome, ma non riesco a leggere l'archivio (installa 7-Zip o WinRAR): verifica a mano"
        else:
            continue
        out.append({"path": p, "name": nm, "size": sum(v[1] for v in vols), "vols": vols, "level": lvl, "why": why,
                    "why_code": code, "why_n": n, "why_where": where, "why_ratio": round(ratio, 2) if ents else None,
                    "where": where, "files": n, "mtime": mt})
    return sorted(out, key=lambda a: (a["level"] != "ok", -a["size"]))


def run(roots, dups, arch, minmb):
    try:
        dirs, markers, sizes, top, archs, junk = walk(roots, minmb << 20)
        S["phase"] = "agg"
        res = build(dirs, markers, top, junk)
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
    """Sposta nel Cestino (recuperabile). Se il Cestino non e' disponibile NON elimina nulla.
    File e cartelle. I percorsi restano Unicode: su Windows il JSON entra in UTF-8."""
    files = [p for p in paths if os.path.isfile(p) and not os.path.islink(p)]
    dirs = [p for p in paths if os.path.isdir(p) and not os.path.islink(p)]
    if not files and not dirs:
        return
    try:
        if IS_WIN:
            ps = ("[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false;"
                  "$i=[Console]::In.ReadToEnd()|ConvertFrom-Json;Add-Type -AssemblyName Microsoft.VisualBasic;"
                  "foreach($p in @($i.files)){try{[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile([string]$p,'OnlyErrorDialogs','SendToRecycleBin')}catch{}};"
                  "foreach($p in @($i.dirs)){try{[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory([string]$p,'OnlyErrorDialogs','SendToRecycleBin')}catch{}}")
            raw = json.dumps({"files": files, "dirs": dirs}, ensure_ascii=False).encode("utf-8")
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           input=b"\xef\xbb\xbf" + raw, capture_output=True, timeout=900, **NW)
        elif IS_MAC:
            scr = ['on run argv', 'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)', 'end run']
            for p in files + dirs:
                subprocess.run(["osascript"] + [x for l in scr for x in ("-e", l)] + [p], capture_output=True, timeout=120)
        else:
            exe = shutil.which("gio") and ["gio", "trash"] or shutil.which("trash-put") and ["trash-put"]
            for p in files + dirs:
                if exe:
                    subprocess.run(exe + [p], capture_output=True, timeout=120)
    except Exception:
        pass


def _covered(path, roots):
    return any(path == d or path.startswith(d + os.sep) for d in roots)


def _trim_map(nodes, gone):
    out = []
    for n in nodes or []:
        if _covered(n.get("path", ""), gone):
            continue
        n = dict(n)
        n["children"] = _trim_map(n.get("children"), gone)
        out.append(n)
    return out


def prune(done):
    r, gone = S["res"], set(done)
    if not r:
        return

    def keep(path):
        return not _covered(path, gone)

    r["files"] = [f for f in r["files"] if keep(f["path"])]
    r["folders"] = [f for f in r.get("folders", []) if keep(f["path"])]
    r["archives"] = [a for a in r["archives"] if keep(a["path"])]
    r["junk_files"] = [j for j in r.get("junk_files") or [] if keep(j["path"])]
    r["scarto_extra"] = [j for j in r.get("scarto_extra") or [] if keep(j["path"])]
    r["map"] = _trim_map(r.get("map"), gone)
    r["games"] = [f for f in r["folders"] if f["cat"] == GAME]
    gs = []
    for g in r["dups"]:
        k = [i for i, p in enumerate(g["paths"]) if keep(p)]
        if len(k) > 1:
            g["paths"], g["mt"] = [g["paths"][i] for i in k], [g["mt"][i] for i in k]
            g["wasted"] = g["size"] * (len(k) - 1)
            gs.append(g)
    r["dups"], r["wasted"] = gs, sum(g["wasted"] for g in gs)
    r["arch_total"] = sum(a["size"] for a in r["archives"] if a["level"] == "ok")
    totals = {}
    for f in r["folders"]:
        totals[f["cat"]] = totals.get(f["cat"], 0) + f["size"]
    r["totals"] = totals
    covered = [f["path"] for f in r["folders"] if f["cat"] == JUNK]
    extra = [j for j in r["junk_files"] if not _covered(j["path"], covered)]
    r["scarto_extra"] = extra
    r["scarto_total"] = sum(f["size"] for f in r["folders"] if f["cat"] == JUNK) + sum(j["size"] for j in extra)
    for p in list(C.get("ok", {})):
        if not keep(p):
            C["ok"].pop(p, None)
    for p in list(C.get("dirs", ())):
        if not keep(p):
            C["dirs"].discard(p)
            C.get("dirsize", {}).pop(p, None)


def _safe_dir(p):
    """Cartella della mappa che si può spostare. Mai un disco intero o una cartella di sistema."""
    if p not in C.get("dirs", ()) or p in C.get("map_roots", ()):
        return False
    if not os.path.isabs(p) or os.path.dirname(p) == p:
        return False
    low = p.lower()
    if low in SYSDIRS or any(low == s or low.startswith(s + os.sep) for s in SYS if s):
        return False
    return True


def do_trash(paths):
    bad, files, folders = [], [], []
    seen = set()
    for raw in paths:
        if not isinstance(raw, str) or "\0" in raw:
            bad.append([str(raw), "percorso non valido"])
            continue
        p = os.path.normpath(raw)
        if p in seen:
            continue
        seen.add(p)
        try:
            if os.path.islink(p):
                bad.append([p, "collegamento simbolico: non toccato"])
            elif p in C.get("dirs", ()) and os.path.isdir(p):
                if not _safe_dir(p):
                    bad.append([p, "cartella di sistema, disco intero o non autorizzata"])
                else:
                    folders.append(p)
            elif p in C.get("ok", {}):
                sz = C["ok"][p]
                if not os.path.isfile(p) or os.path.getsize(p) != sz:
                    bad.append([p, "il file è cambiato o non esiste più"])
                else:
                    files.append(p)
            else:
                bad.append([p, "non autorizzato"])
        except OSError as e:
            bad.append([p, str(e)])
    # una cartella già scelta copre i file che contiene
    files = [p for p in files if not _covered(p, folders)]
    rs = set(files)
    for g in (S.get("res") or {}).get("dups") or []:  # di un gruppo di doppioni resta sempre almeno una copia
        if set(g["paths"]) <= rs:
            for p in g["paths"]:
                rs.discard(p)
                bad.append([p, "tenuta almeno una copia di sicurezza"])
    ordered = sorted(folders) + sorted(rs)
    trash_many(ordered)
    done = [p for p in ordered if not os.path.exists(p)]
    bad += [[p, "Cestino non disponibile o operazione non riuscita"] for p in ordered if os.path.exists(p)]
    freed = 0
    for p in done:
        freed += C.get("dirsize", {}).get(p, 0) if p in folders else C.get("ok", {}).get(p, 0)
    prune(done)
    return {"done": done, "failed": bad, "freed": freed}


# ====================================================================================
#  Account, sicurezza e server web (solo 127.0.0.1)
# ====================================================================================
APP = "Twenties"
VERSION = "1.1.0"
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
DONE_PAGE = '<!doctype html><meta charset="utf-8"><title>Twenties</title><body style="font-family:sans-serif"><h2>%s</h2><p>%s</p></body>'
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
        expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, kind TEXT NOT NULL,
        summary TEXT NOT NULL, undo TEXT);""")
    if not IS_WIN:
        os.chmod(path, 0o600)
    now = int(time.time())
    dbx("DELETE FROM sessions WHERE last<? OR created<?", (now - IDLE, now - ABSOLUTE))
    dbx("DELETE FROM resets WHERE expires<? OR used=1", (now,))


def dbx(sql, a=()):
    with DBL:
        cur = CON.execute(sql, a)
        return cur.fetchall(), cur.rowcount, cur.lastrowid


SYSTEM_LANG = "en"
UPDATE_API = "https://api.github.com/repos/twoventi/twenties-cleaning/releases/latest"


def setting(k, default=None):
    if CON is None:
        return default
    rows = dbx("SELECT v FROM settings WHERE k=?", (k,))[0]
    return rows[0]["v"] if rows else default


def set_setting(k, v):
    dbx("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k, str(v)))


def detect_lang():
    """Italiano se il sistema è in italiano, altrimenti inglese."""
    parts = []
    for key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(key, "")
        for piece in raw.split(":"):
            p = piece.split(".")[0].strip().lower().replace("-", "_")
            if p and p not in ("c", "posix"):
                parts.append(p)
    for p in parts:
        if p == "it" or p.startswith("it_"):
            return "it"
    if not parts and IS_WIN:
        try:
            import ctypes
            if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x10:
                return "it"
        except Exception:
            pass
    if not parts and IS_MAC:
        try:
            r = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=2)
            head = (r.stdout or "").lower()[:120]
            if "it-" in head or "it_" in head or '"it"' in head:
                return "it"
        except Exception:
            pass
    return "en"


def active_lang():
    v = setting("lang", "")
    return v if v in ("it", "en") else SYSTEM_LANG


def parse_ver(s):
    s = str(s or "").strip().lstrip("vV")
    if not s:
        return None
    parts = []
    for p in s.split("."):
        n = ""
        for ch in p:
            if ch.isdigit():
                n += ch
            else:
                break
        if n == "":
            return None
        parts.append(int(n))
    return tuple(parts)


def newer(remote, local):
    a, b = parse_ver(remote), parse_ver(local)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def latest_release():
    """Solo con consenso. Con TC_UPDATE_FIXTURE non esce dalla macchina (i test)."""
    fixture = os.environ.get("TC_UPDATE_FIXTURE", "").strip()
    if fixture:
        with open(fixture, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(UPDATE_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Twenties/" + VERSION,
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read(1 << 20))


def schedule_state():
    enabled = setting("schedule", "0") == "1"
    try:
        days = min(90, max(1, int(setting("schedule_days", "7") or 7)))
    except ValueError:
        days = 7
    try:
        last = int(setting("schedule_last", "0") or 0)
    except ValueError:
        last = 0
    due = bool(enabled and (time.time() - last) >= days * 86400)
    return {"enabled": enabled, "days": days, "due": due, "last": last}


def scarto_preview():
    """Cartelle etichettate Scarto e i file di scarto che non ci stanno già dentro."""
    res = S.get("res") or {}
    items = []
    for f in res.get("folders") or []:
        if f.get("cat") == JUNK:
            items.append({"path": f["path"], "name": f["name"], "size": f["size"], "why": f.get("why") or "", "kind": "folder"})
    for j in res.get("scarto_extra") or []:
        items.append({"path": j["path"], "name": j.get("name") or os.path.basename(j["path"]), "size": j["size"],
                      "why": "temporaneo, cache, log o backup", "kind": "file"})
    return items


def log_action(kind, summary, undo=None):
    dbx("INSERT INTO actions(ts,kind,summary,undo) VALUES(?,?,?,?)",
        (int(time.time()), kind, summary[:500], json.dumps(undo, ensure_ascii=False) if undo else None))
    dbx("DELETE FROM actions WHERE id NOT IN (SELECT id FROM actions ORDER BY id DESC LIMIT 200)")
    rows = dbx("SELECT id FROM actions ORDER BY id DESC LIMIT 1")[0]
    return rows[0]["id"] if rows else None


def _trash_home():
    if IS_WIN:
        return None
    if IS_MAC:
        return os.path.expanduser("~/.Trash")
    data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(data, "Trash")


def restore_one(path):
    """Rimette un percorso al suo posto, se il Cestino lo permette ancora. Altrimenti False."""
    if os.path.lexists(path):
        return False
    home = _trash_home()
    if not home:
        return _restore_windows(path)
    if IS_MAC:
        src = os.path.join(home, os.path.basename(path))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.move(src, path)
            return True
        return False
    info = os.path.join(home, "info")
    files = os.path.join(home, "files")
    if not os.path.isdir(info):
        return False
    try:
        names = os.listdir(info)
    except OSError:
        return False
    for name in names:
        if not name.endswith(".trashinfo"):
            continue
        ip = os.path.join(info, name)
        try:
            text = open(ip, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        origin = ""
        for line in text.splitlines():
            if line.startswith("Path="):
                origin = urllib.parse.unquote(line[5:].strip())
                break
        if os.path.normpath(origin) != os.path.normpath(path):
            continue
        src = os.path.join(files, name[:-len(".trashinfo")])
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.move(src, path)
        try:
            os.remove(ip)
        except OSError:
            pass
        return True
    return False


def _restore_windows(path):
    name = os.path.basename(path)
    ps = ("[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false;"
          "$name=[Console]::In.ReadToEnd().Trim();"
          "$shell=New-Object -ComObject Shell.Application;$rb=$shell.NameSpace(10);$ok=$false;"
          "foreach($item in @($rb.Items())){ if($item.Name -eq $name){ foreach($v in @($item.Verbs())){"
          " if($v.Name -match 'estore|ipristin|Wiederherstell|Restaurar'){ $v.DoIt(); $ok=$true; break } } } };"
          "if($ok){'ok'}")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           input=b"\xef\xbb\xbf" + name.encode("utf-8"), capture_output=True, timeout=60, **NW)
        return b"ok" in (r.stdout or b"") and os.path.exists(path)
    except Exception:
        return False


def restore_paths(paths):
    restored, failed = [], []
    for p in paths:
        try:
            if restore_one(p):
                restored.append(p)
            else:
                failed.append(p)
        except Exception:
            failed.append(p)
    return restored, failed


def asset_text(name):
    roots = []
    if getattr(sys, "frozen", False):
        me = getattr(sys, "_MEIPASS", "")
        if me:
            roots.append(me)
    here = os.path.dirname(os.path.abspath(__file__))
    roots += [os.path.dirname(here), here]
    for root in roots:
        p = os.path.join(root, "assets", name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                continue
    return ""


def adopt_scan(uid):
    """Chi entra tiene l'analisi fatta senza account. Non tocca l'analisi di un altro account."""
    if S.get("owner") in (None, 0) and S.get("res"):
        S["owner"] = uid


def release_scan(uid):
    """Uscendo, l'analisi resta su questo computer e si continua a vederla senza account."""
    if S.get("owner") == uid:
        S["owner"] = 0


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

    def actor(self):
        s = self.session()
        return s["uid"] if s else 0

    def owns(self):
        """L'analisi senza account (owner 0) resta visibile su questo computer. Quella di un altro account no."""
        owner = S.get("owner")
        if owner in (None, 0):
            return True
        s = self.session()
        return bool(s) and owner == s["uid"]

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
            if p in ("/logo.svg", "/favicon.svg"):
                body = asset_text("logo.svg") or FALLBACK_LOGO
                return self.send(200, body, "image/svg+xml")
            if p == "/logo-mono.svg":
                return self.send(200, asset_text("logo-mono.svg") or FALLBACK_LOGO, "image/svg+xml")
            if p in ("/", "/reset"):
                _, ck = self.pre_cookie()
                nonce = secrets.token_urlsafe(16)
                html = PAGE.replace("__NONCE__", nonce).replace("__I18N__", json.dumps(I18N, ensure_ascii=False))
                return self.send(200, html, "text/html", cookies=ck, nonce=nonce)
            if p == "/api/me":
                pre, ck = self.pre_cookie()
                b = ("s:" + s["sid"]) if s else "p:" + pre
                return self.jout({"user": {"email": s["email"], "name": s["name"]} if s else None, "csrf": csrf_for(b),
                                  "google": bool(G_ID and G_SECRET), "mail": bool(os.environ.get("SMTP_HOST")),
                                  "platform": PLATFORM, "app": APP, "version": VERSION, "window": WINDOW_MODE,
                                  "lang": active_lang(), "updates": setting("updates", "0") == "1",
                                  "onboarded": setting("onboarded", "0") == "1", "schedule": schedule_state()}, cookies=ck)
            if p == "/api/focus":  # una seconda copia della STESSA versione chiede di riportare in primo piano la finestra
                self.raise_window()
                return self.jout({"app": APP, "version": VERSION, "window": WINDOW_MODE})
            if p == "/api/i18n":
                lang = active_lang()
                return self.jout({"lang": lang, "available": ["it", "en"], "tagline": I18N[lang]["tagline"], "catalog": I18N})
            if p == "/api/settings":
                return self.jout({"lang": active_lang(), "updates": setting("updates", "0") == "1",
                                  "onboarded": setting("onboarded", "0") == "1", "schedule": schedule_state()})
            if p == "/auth/google":
                return self.google_start(ip, (qs.get("t") or [""])[0])
            if p == "/auth/google/callback":
                return self.google_cb(qs)
            if p == "/auth/finish":
                return self.auth_finish((qs.get("t") or [""])[0])
            if p == "/api/drives":
                return self.jout(drives())
            if p in ("/api/status", "/api/results", "/api/map", "/api/schedule", "/api/history"):
                mine = self.owns()
                if p == "/api/status":
                    r = {k: v for k, v in S.items() if k not in ("res", "owner")} if mine else {"phase": "idle"}
                    r["has_res"] = bool(mine and S["res"])
                    return self.jout(r)
                if p == "/api/map":
                    res = S.get("res") or {}
                    return self.jout({"roots": (res.get("map") or []) if mine else [], "scarto": res.get("scarto_total", 0) if mine else 0})
                if p == "/api/schedule":
                    stt = schedule_state()
                    stt["preview"] = scarto_preview() if mine and stt["due"] else []
                    stt["estimate"] = (S.get("res") or {}).get("scarto_total", 0) if mine else 0
                    return self.jout(stt)
                if p == "/api/history":
                    rows = dbx("SELECT id, ts, kind, summary, undo FROM actions ORDER BY id DESC LIMIT 40")[0]
                    out = []
                    for row in rows:
                        can = False
                        if row["undo"]:
                            try:
                                can = not json.loads(row["undo"]).get("used")
                            except Exception:
                                can = False
                        out.append({"id": row["id"], "ts": row["ts"], "kind": row["kind"], "summary": row["summary"], "can_undo": can})
                    return self.jout(out)
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
                return self.send(200, DONE_PAGE % ("Accesso non riuscito", "Torna a Twenties e riprova."), "text/html")
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
                    return self.send(200, DONE_PAGE % ("Accesso completato", "Puoi chiudere questa scheda e tornare a Twenties."), "text/html")
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
            guest = {"/api/start": self.p_start, "/api/stop": self.p_stop, "/api/reveal": self.p_reveal,
                     "/api/trash": self.p_trash, "/api/quit": self.p_quit, "/api/settings": self.p_settings,
                     "/api/lang": self.p_lang, "/api/update_check": self.p_update, "/api/schedule": self.p_schedule,
                     "/api/schedule_apply": self.p_schedule_apply, "/api/undo": self.p_undo}
            if p in guest:
                key = "api:" + (s["sid"] if s else ip)
                if RL.count(key, 60) >= 240:
                    return self.err(429, "Troppe richieste. Riprova tra poco.", headers=[("Retry-After", "30")])
                RL.add(key)
                return guest[p](d, s)
            if not s:
                return self.err(401, "Accesso richiesto")
            if RL.count("api:" + s["sid"], 60) >= 240:
                return self.err(429, "Troppe richieste. Riprova tra poco.", headers=[("Retry-After", "30")])
            RL.add("api:" + s["sid"])
            fn = {"/api/logout": self.p_logout, "/api/delete_account": self.p_delete}.get(p)
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
        adopt_scan(uid)
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
        release_scan(s["uid"])
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
        me = self.actor()
        with START_LOCK:
            if S["phase"] in RUNNING:
                return self.err(409, "Analisi già in corso." if S["owner"] == me else "Un'altra sessione sta analizzando il computer. Riprova tra poco.")
            S.update(owner=me, phase="scan", count=0, current="", done=0, total=0, stop=False, error="", res=None, denied=0)
        threading.Thread(target=run, args=(roots, bool(d.get("dups")), bool(d.get("arch")), mb), daemon=True).start()
        self.jout({})

    def p_stop(self, d, s):
        if S["owner"] == self.actor():
            S["stop"] = True
        self.jout({})

    def p_reveal(self, d, s):
        p = d.get("path")
        if self.owns() and isinstance(p, str) and (p in allowed_paths() or p in C.get("dirs", ())):
            reveal(p)
        self.jout({})

    def p_trash(self, d, s):
        paths = d.get("paths")
        if not self.owns() or not S["res"] or S["phase"] != "done":
            return self.err(403, "Nessun risultato disponibile.")
        if not isinstance(paths, list) or len(paths) > 2000 or not all(isinstance(x, str) and len(x) < 4096 for x in paths):
            return self.err(400, "Selezione non valida.")
        out = do_trash(paths)
        if out.get("done"):
            out["undo"] = log_action("trash", "Spostati nel Cestino: %d" % len(out["done"]), {"paths": out["done"]})
        self.jout(out)

    def p_settings(self, d, s):
        if "lang" in d:
            if d.get("lang") not in ("it", "en"):
                return self.err(400, "Lingua non valida.")
            set_setting("lang", d["lang"])
        if "updates" in d:
            set_setting("updates", "1" if d.get("updates") else "0")
        if "onboarded" in d:
            set_setting("onboarded", "1" if d.get("onboarded") else "0")
        if "schedule" in d:
            set_setting("schedule", "1" if d.get("schedule") else "0")
            if not d.get("schedule"):
                set_setting("schedule_last", "0")
        if d.get("schedule_dismiss"):
            set_setting("schedule_last", str(int(time.time())))
        if "schedule_days" in d:
            try:
                days = min(90, max(1, int(d.get("schedule_days"))))
            except (TypeError, ValueError):
                return self.err(400, "Intervallo non valido.")
            set_setting("schedule_days", str(days))
        self.jout({"lang": active_lang(), "updates": setting("updates", "0") == "1",
                   "onboarded": setting("onboarded", "0") == "1", "schedule": schedule_state()})

    def p_lang(self, d, s):
        if d.get("lang") not in ("it", "en"):
            return self.err(400, "Lingua non valida.")
        set_setting("lang", d["lang"])
        self.jout({"lang": d["lang"], "tagline": I18N[d["lang"]]["tagline"]})

    def p_update(self, d, s):
        """Con consenso legge solo l'ultima release pubblica. Senza consenso non esce nulla dal computer."""
        if setting("updates", "0") != "1":
            return self.jout({"consent": False, "current": VERSION})
        try:
            data = latest_release()
        except Exception:
            return self.jout({"consent": True, "current": VERSION, "error": "unavailable"})
        if not isinstance(data, dict):
            return self.jout({"consent": True, "current": VERSION, "error": "unavailable"})
        tag = str(data.get("tag_name") or "")
        url = str(data.get("html_url") or "https://github.com/twoventi/twenties-cleaning/releases/latest")
        if not url.startswith("https://github.com/twoventi/twenties-cleaning/"):
            url = "https://github.com/twoventi/twenties-cleaning/releases/latest"
        latest = tag[1:] if tag[:1] in ("v", "V") else tag
        self.jout({"consent": True, "current": VERSION, "latest": latest, "update": newer(tag, VERSION), "url": url})

    def p_schedule(self, d, s):
        return self.p_settings(d, s)

    def p_schedule_apply(self, d, s):
        if setting("schedule", "0") != "1":
            return self.err(403, "La pulizia programmata è spenta.")
        if not self.owns() or not S.get("res") or S.get("phase") != "done":
            return self.err(403, "Serve prima un'analisi, per vedere l'anteprima.")
        paths = d.get("paths")
        allowed = {i["path"] for i in scarto_preview()}
        if not isinstance(paths, list) or not paths or len(paths) > 2000 or not all(isinstance(x, str) and x in allowed for x in paths):
            return self.err(400, "L'anteprima non corrisponde. Ricaricala.")
        out = do_trash(paths)
        set_setting("schedule_last", str(int(time.time())))
        if out.get("done"):
            out["undo"] = log_action("schedule", "Scarto spostato nel Cestino: %d" % len(out["done"]), {"paths": out["done"]})
        self.jout(out)

    def p_undo(self, d, s):
        try:
            i = int(d.get("id"))
        except (TypeError, ValueError):
            return self.err(400, "Azione non valida.")
        rows = dbx("SELECT id, undo FROM actions WHERE id=?", (i,))[0]
        if not rows or not rows[0]["undo"]:
            return self.err(400, "Questa azione non si può annullare.")
        try:
            payload = json.loads(rows[0]["undo"])
        except Exception:
            return self.err(400, "Questa azione non si può annullare.")
        if payload.get("used"):
            return self.err(400, "Già annullata.")
        restored, failed = restore_paths(payload.get("paths") or [])
        payload["used"] = True
        payload["restored"] = restored
        dbx("UPDATE actions SET undo=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), i))
        if restored:
            log_action("restore", "Ripristinati: %d" % len(restored), None)
        self.jout({"ok": bool(restored), "restored": restored, "failed": failed, "manual": not restored})

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


I18N = {"it":{"app.name":"Twenties","tagline":"Vedi cosa pesa. Decidi tu.","intro.skip":"Salta","intro.next":"Avanti","intro.start":"Ok","intro.1.title":"Cosa fa","intro.2.title":"Cosa lascia stare","intro.3.title":"Dove va il file","intro.1.body":"Legge il disco e scrive perché ogni cartella pesa.","intro.2.body":"Non sposta nulla da solo.","intro.3.body":"Se confermi, finisce nel Cestino. Lo recuperi da lì.","nav.home":"Inizio","nav.map":"Mappa","nav.folders":"Cartelle","nav.games":"Giochi","nav.files":"File grandi","nav.dups":"Doppioni","nav.arch":"Archivi","cat.tutti":"Tutti","cat.gioco":"Gioco","cat.scarto":"Scarto","cat.bassa":"Importanza bassa","cat.media":"Importanza media","cat.elevata":"Importanza elevata","leg.gioco":"File di un gioco. Se non ti serve, toglilo dal launcher.","leg.scarto":"Cache, temporanei, log. Di solito si possono spostare.","leg.bassa":"Roba vecchia o che si riscarica.","leg.media":"Usato di recente, o un programma installato.","leg.elevata":"Documenti, foto, progetti, sistema.","why.game":"Cartella di un gioco: c'è un launcher nel percorso, oppure file tipici del motore.","why.junk":"Il nome è cache, temporanei o log. Di solito si possono ricreare.","why.sys":"È una cartella di sistema. Twenties non la propone per lo spostamento.","why.prog.mac":"Programma installato. Si toglie trascinando l'app nel Cestino, non i file interni.","why.prog.win":"Programma installato. Si toglie dalle Impostazioni, non cancellando la cartella.","why.mostlyjunk":"La maggior parte del peso sono file temporanei, log o copie di backup.","why.docs":"Ci sono documenti, foto o progetti. Per questo l'importanza è elevata.","why.down":"È la cartella Download: spesso si può scaricare di nuovo, ma dai un'occhiata.","why.iso":"Immagini disco, ISO o macchine virtuali. Pesano tanto e di solito si possono rifare.","why.oldmedia":"Video, audio o archivi non toccati da più di due anni.","why.media":"Video, audio o archivi. Non è scarto solo perché pesa.","why.oldmix":"Contenuto misto, non toccato da più di due anni.","why.mix":"Contenuto misto, usato di recente.","why.gamefile":"Sta dentro la cartella di un gioco.","why.temp":"Temporaneo, cache, log o copia di backup.","why.inst":"Installer scaricato. Di solito si può scaricare di nuovo.","why.sysfile":"File di sistema. Meglio lasciarlo dov'è.","why.doc":"Documento, foto o progetto personale.","why.isofile":"Immagine disco o ISO. Di solito si può rifare.","why.oldfile":"Media o archivio vecchio, oppure sta in Download.","why.mediafile":"Video, audio o archivio.","why.oldunk":"Tipo non riconosciuto, non modificato da più di due anni.","why.unk":"Tipo non riconosciuto, usato di recente.","hero.title":"Vedi cosa pesa.","hero.body":"Scegli i dischi. La scansione non modifica i file.","go":"Scansiona","stop":"Ferma","stopping":"Fermo…","disks":"Dischi","disks.none":"Nessun disco rilevato su questo computer.","disks.pick":"{n} di {all} selezionati","disk.meta":"{used} usati · {free} liberi su {total}","metric.used":"Spazio usato","metric.free":"Spazio libero","metric.cap":"Capacità","metric.one":"1 disco","metric.many":"{n} dischi","status.title":"Stato","status.platform":"Sistema","status.conn":"Connessione","status.local":"Solo questo computer","status.account":"Account","status.google":"Accesso Google","status.analysis":"Analisi","status.running":"In corso","status.ready":"Risultati pronti","status.idle":"In attesa","status.read":"File letti","status.denied":"Cartelle non accessibili","status.rar":"Lettura RAR e 7z","status.yes":"Disponibile","status.no":"Non disponibile","quick.title":"Opzioni","quick.hint":"I doppioni si riconoscono dall'hash del file, non dal nome.","opt.dups":"Cerca doppioni","opt.dups_from":"solo file da","opt.dups_why":"Due file sono doppi solo se l'hash BLAKE2b è uguale. Di ogni gruppo ne resta uno.","opt.arch":"Archivi già estratti","opt.arch_hint":"ZIP e TAR sempre. RAR e 7z se trovi 7-Zip o UnRAR.","opt.folder":"Cartella specifica da aggiungere, anche sotto OneDrive","about.title":"Cosa riconosce","about.body":"Se non è sicuro, lo dice.","about.folders.t":"Cartelle","about.folders.d":"Cartelle da almeno 100 MB, con un motivo per l'etichetta.","about.files.t":"File grandi","about.files.d":"Fino a 400 file più pesanti.","about.games.t":"Giochi","about.games.d":"Steam, Epic, GOG, Riot, Ubisoft, EA, Xbox.","about.dups.t":"Doppioni","about.dups.d":"Stesso contenuto, non solo lo stesso nome.","about.arch.t":"Archivi","about.arch.d":"Solo se i file estratti sono già sul disco.","prog.title":"Scansione","prog.body":"La finestra resta usabile. Non sta spostando file.","step.scan":"Lettura","step.agg":"Cartelle","step.dups":"Doppioni","step.arch":"Archivi","scan.files":"{n} file letti · {p}","scan.agg":"Sto sommando le cartelle.","scan.checked":"{d} / {t} elementi controllati","again":"Altra scansione","settings":"Impostazioni","theme":"Tema","account":"Account","logout":"Esci","logout.done":"Sei uscito. La scansione di questa finestra resta.","quit":"Chiudi","close.ask.title":"Chiudere Twenties?","close.ask.body":"I file restano dove sono.","close.ask.ok":"Chiudi","closed.title":"Programma chiuso","closed.body":"Puoi chiudere questa scheda.","who.guest":"Senza account","greet.night":"Buonanotte","greet.morning":"Buongiorno","greet.afternoon":"Buon pomeriggio","greet.evening":"Buonasera","auth.login.title":"Account","auth.login.sub":"Non serve per scansionare.","auth.register.title":"Nuovo account","auth.register.sub":"Email e password restano su questo computer.","auth.forgot.title":"Password dimenticata","auth.forgot.sub":"Senza posta, da qui non si recupera.","auth.reset.title":"Nuova password","auth.reset.sub":"Almeno 10 caratteri.","auth.email":"Email","auth.password":"Password","auth.submit.login":"Entra","auth.submit.register":"Crea account","auth.submit.forgot":"Chiedi il link","auth.submit.reset":"Aggiorna password","auth.google":"Continua con Google","auth.google.off":"L'accesso con Google non è configurato su questo computer.","auth.forgot.link":"Password dimenticata","auth.back":"Torna all'accesso","auth.guest":"Continua senza account","auth.forgot.sent":"Se l'account c'è, il link è in viaggio. Scade tra 15 minuti.","auth.forgot.nomail":"Non parte nessuna email. Puoi usare Twenties senza account. I file restano dove sono.","auth.reset.ok":"Password aggiornata.","session.expired":"Sessione scaduta. Entra di nuovo, o continua senza account.","google.wait":"Completa l'accesso nel browser, poi torna qui.","google.fail":"Accesso con Google non riuscito.","google.timeout":"Tempo scaduto. Riprova.","delete.title":"Eliminare l'account?","delete.body":"Cancella account e sessioni su questo computer. I file del disco restano.","delete.pw":"Password, se l'account ne ha una","delete.ok":"Elimina l'account","delete.done":"Account eliminato. I file sono ancora al loro posto.","trash.ask.title":"Spostare nel Cestino?","trash.ask.body":"{n} elementi vanno nel Cestino. Di ogni gruppo di doppioni ne resta uno.","trash.ask.ok":"Sposta nel Cestino","trash.working":"Sposto nel Cestino…","trash.result":"Spostati {n} · {size}","act.clear":"Deseleziona","act.trash":"Sposta nel Cestino","show.mac":"Mostra nel Finder","show.win":"Mostra","show.linux":"Mostra","perm.mac":"Per le cartelle protette serve l'accesso completo al disco, in Impostazioni di Sistema › Privacy e sicurezza. Poi riapri Twenties.","perm.win":"Avvia Twenties come amministratore per leggere anche le cartelle protette.","perm.linux":"Servono i permessi di lettura su quelle cartelle.","tool.mac":"Per leggere RAR e 7z installa 7-Zip. ZIP e TAR vengono controllati lo stesso.","tool.win":"Per leggere RAR e 7z installa 7-Zip o WinRAR. ZIP e TAR vengono controllati lo stesso.","tool.linux":"Per leggere RAR e 7z installa 7-Zip. ZIP e TAR vengono controllati lo stesso.","home.scarto.kicker":"Scarto, stima","home.scarto.note":"Somma delle cartelle segnate come scarto, più i file di scarto che stanno fuori. Guarda i nomi prima di spostare.","home.denied":"{n} cartelle non erano leggibili e sono state saltate.","home.stats.folders":"Cartelle","home.stats.files":"File grandi","home.stats.games":"Giochi","home.stats.dups":"Gruppi di doppioni","home.stats.arch":"Archivi già estratti","home.stats.copies":"Copie in più","home.stats.scarto":"Scarto","home.stats.free":"Libero sui dischi","home.bycat":"Per etichetta","home.bycat.note":"Peso delle cartelle in elenco, non di tutto il disco.","home.quick":"Apri un risultato","home.q.scarto":"Vedi lo Scarto","home.q.dups":"Vedi i doppioni","home.q.arch":"Vedi gli archivi","home.q.games":"Libreria giochi","home.top":"Cartelle più pesanti","home.legend":"Etichette","home.disks.note":"{used} usati · {free} liberi · {total} di capacità, sui dischi letti.","intro.folders":"Le cartelle più pesanti, con il motivo dell'etichetta.","intro.files":"I file più pesanti. Puoi spostarli nel Cestino.","intro.dups":"Stesso hash. Di ogni gruppo ne resta una copia.","intro.arch":"Il contenuto risulta già estratto sul disco.","search":"Cerca per nome o percorso","sort.size":"Più grandi prima","sort.name":"Nome","sort.date":"Più vecchi prima","selok":"Seleziona i già estratti","keep":"Tieni la copia più vecchia","empty.filters":"Niente da mostrare con questi filtri.","empty.dups":"Nessun doppione, oppure la ricerca era spenta.","dups.hash":"Hash BLAKE2b dell'intero file.","dups.lead":"Copie in più: {size}.","files.count":"{n} file","modified":"modificato il {d}","level.ok":"Già estratto","level.part":"Estratto in parte","level.guess":"Da verificare","arch.ok":"Tutti i {n} file dell'archivio sono già in: {where}","arch.part":"Estratto solo in parte ({p}%) in: {where}. Controlla prima di spostarlo.","arch.guess":"C'è una cartella con lo stesso nome, ma l'archivio non si legge. Controlla a mano.","map.lead":"Il colore è l'etichetta. Il motivo sta a lato.","map.root":"Cartelle analizzate","map.sun":"Anelli","map.tree":"Riquadri","map.back":"Livello sopra","map.open":"Apri cartella","map.trash":"Sposta nel Cestino","map.pick":"Apri una cartella per vederla o spostarla. Un disco intero non si sposta.","map.empty":"Qui dentro non ci sono altre cartelle da disegnare.","map.confirm":"Spostare «{name}» nel Cestino? {why}","games.lead":"Peso, data e launcher. Il link apre la libreria, non un gioco solo.","games.launcher":"Launcher","games.unknown":"Riconosciuto dai file di gioco, senza un launcher nel percorso.","games.open":"Apri {name}","games.access":"Ultimo accesso","games.modified":"Ultima modifica","games.access.note":"Su alcuni dischi la data di accesso non si aggiorna.","games.unknown.date":"non indicato","games.empty":"Nessun gioco in questa analisi.","settings.title":"Impostazioni","settings.lang":"Lingua","settings.lang.why":"All'avvio usa la lingua del sistema.","settings.updates":"Avviso di versione","settings.updates.why":"Se lo accendi, chiede a GitHub solo il numero dell'ultima versione.","settings.schedule":"Promemoria scarto","settings.schedule.why":"Spento. Se lo accendi, ogni tanto elenca lo scarto. Va nel Cestino solo se confermi.","settings.days":"Ogni quanti giorni","settings.history":"Cronologia","settings.history.empty":"Ancora nessuna azione.","settings.undo":"Annulla","settings.undo.manual":"Non riesco a rimetterlo al posto. È nel Cestino: puoi ripristinarlo da lì.","settings.account":"Account","settings.delete":"Elimina account","common.cancel":"Annulla","update.banner":"C'è la versione {v}.","update.open":"Apri la pagina","update.later":"Non ora","schedule.card":"Anteprima scarto","schedule.lead":"Solo lo scarto. Niente si sposta finché non confermi.","schedule.now":"Sposta nel Cestino","schedule.later":"Non ora","schedule.empty":"Non c'è scarto in questa scansione.","schedule.confirm":"Spostare nel Cestino i file di questa anteprima?","undo.ok":"Rimessi al loro posto: {n}.","need.root":"Scegli un disco, o scrivi una cartella.","err.offline":"Connessione al programma non riuscita.","err.rate":"Troppi tentativi. Riprova tra qualche minuto."},"en":{"app.name":"Twenties","tagline":"See what takes space. You decide.","intro.skip":"Skip","intro.next":"Next","intro.start":"OK","intro.1.title":"What it does","intro.2.title":"What it leaves alone","intro.3.title":"Where the file goes","intro.1.body":"It reads the disk and says why each folder takes space.","intro.2.body":"It does not move anything on its own.","intro.3.body":"If you confirm, it goes to the Trash. You put it back from there.","nav.home":"Home","nav.map":"Map","nav.folders":"Folders","nav.games":"Games","nav.files":"Large files","nav.dups":"Duplicates","nav.arch":"Archives","cat.tutti":"All","cat.gioco":"Game","cat.scarto":"Discard","cat.bassa":"Low importance","cat.media":"Medium importance","cat.elevata":"High importance","leg.gioco":"A game's files. If you do not want it, remove it from the launcher.","leg.scarto":"Cache, temporary files, logs. Usually fine to move.","leg.bassa":"Old, or something you can download again.","leg.media":"Used recently, or an installed program.","leg.elevata":"Documents, photos, projects, the system.","why.game":"A game folder: a launcher is in the path, or typical game-engine files are inside.","why.junk":"The name is cache, temporary files or logs. They can usually be recreated.","why.sys":"This is a system folder. Twenties does not offer to move it.","why.prog.mac":"An installed app. Remove it by dragging the app to the Trash, not its inner files.","why.prog.win":"An installed program. Remove it from Settings, not by deleting the folder.","why.mostlyjunk":"Most of the size is temporary files, logs or backup copies.","why.docs":"There are documents, photos or projects. That is why the importance is high.","why.down":"This is Downloads: things can often be downloaded again, but look first.","why.iso":"Disk images, ISOs or virtual machines. They are large and can usually be recreated.","why.oldmedia":"Video, audio or archives not touched for more than two years.","why.media":"Video, audio or archives. Size alone does not make this discard.","why.oldmix":"Mixed content, untouched for more than two years.","why.mix":"Mixed content, used recently.","why.gamefile":"It sits inside a game folder.","why.temp":"Temporary file, cache, log or backup copy.","why.inst":"A downloaded installer. You can usually download it again.","why.sysfile":"A system file. Better to leave it where it is.","why.doc":"A document, photo or personal project.","why.isofile":"A disk image or ISO. It can usually be recreated.","why.oldfile":"Old media or an archive, or it is in Downloads.","why.mediafile":"Video, audio or an archive.","why.oldunk":"Unrecognized type, not modified for more than two years.","why.unk":"Unrecognized type, used recently.","hero.title":"See what takes space.","hero.body":"Pick the drives. The scan does not change files.","go":"Scan","stop":"Stop","stopping":"Stopping…","disks":"Drives","disks.none":"No drives found on this computer.","disks.pick":"{n} of {all} selected","disk.meta":"{used} used · {free} free of {total}","metric.used":"Used space","metric.free":"Free space","metric.cap":"Capacity","metric.one":"1 drive","metric.many":"{n} drives","status.title":"Status","status.platform":"System","status.conn":"Connection","status.local":"This computer only","status.account":"Account","status.google":"Google sign-in","status.analysis":"Scan","status.running":"Running","status.ready":"Results ready","status.idle":"Waiting","status.read":"Files read","status.denied":"Folders that could not be read","status.rar":"Reading RAR and 7z","status.yes":"Available","status.no":"Not available","quick.title":"Options","quick.hint":"Duplicates are matched by the file hash, not the name.","opt.dups":"Find duplicates","opt.dups_from":"only files from","opt.dups_why":"Two files match only when the BLAKE2b hash is the same. One copy of each group stays.","opt.arch":"Extracted archives","opt.arch_hint":"ZIP and TAR always. RAR and 7z if 7-Zip or UnRAR is installed.","opt.folder":"A specific folder to add, including under OneDrive","about.title":"What it recognizes","about.body":"If it is not sure, it says so.","about.folders.t":"Folders","about.folders.d":"Folders from 100 MB up, with a reason for the label.","about.files.t":"Large files","about.files.d":"Up to 400 of the heaviest files.","about.games.t":"Games","about.games.d":"Steam, Epic, GOG, Riot, Ubisoft, EA, Xbox.","about.dups.t":"Duplicates","about.dups.d":"Same content, not just the same name.","about.arch.t":"Archives","about.arch.d":"Only when the extracted files are already on disk.","prog.title":"Scan","prog.body":"The window stays usable. It is not moving files.","step.scan":"Reading","step.agg":"Folders","step.dups":"Duplicates","step.arch":"Archives","scan.files":"{n} files read · {p}","scan.agg":"Adding up the folders.","scan.checked":"{d} / {t} items checked","again":"Scan again","settings":"Settings","theme":"Theme","account":"Account","logout":"Sign out","logout.done":"You signed out. This window's scan stays.","quit":"Quit","close.ask.title":"Quit Twenties?","close.ask.body":"Your files stay where they are.","close.ask.ok":"Quit","closed.title":"Program closed","closed.body":"You can close this tab.","who.guest":"No account","greet.night":"Good night","greet.morning":"Good morning","greet.afternoon":"Good afternoon","greet.evening":"Good evening","auth.login.title":"Account","auth.login.sub":"You do not need one to scan.","auth.register.title":"New account","auth.register.sub":"Email and password stay on this computer.","auth.forgot.title":"Forgot the password","auth.forgot.sub":"Without mail, it cannot be recovered from here.","auth.reset.title":"New password","auth.reset.sub":"At least 10 characters.","auth.email":"Email","auth.password":"Password","auth.submit.login":"Sign in","auth.submit.register":"Create account","auth.submit.forgot":"Request the link","auth.submit.reset":"Update password","auth.google":"Continue with Google","auth.google.off":"Google sign-in is not set up on this computer.","auth.forgot.link":"Forgot password","auth.back":"Back to sign-in","auth.guest":"Continue without an account","auth.forgot.sent":"If the account exists, the link is on its way. It expires in 15 minutes.","auth.forgot.nomail":"No email is sent. You can use Twenties without an account. Your files stay where they are.","auth.reset.ok":"Password updated.","session.expired":"Session expired. Sign in again, or continue without an account.","google.wait":"Finish signing in in the browser, then come back here.","google.fail":"Google sign-in did not work.","google.timeout":"Timed out. Try again.","delete.title":"Delete the account?","delete.body":"Deletes the account and sessions on this computer. Files on disk stay.","delete.pw":"Password, if the account has one","delete.ok":"Delete account","delete.done":"Account deleted. Your files are still in place.","trash.ask.title":"Move to the Trash?","trash.ask.body":"{n} items go to the Trash. One copy of each duplicate group stays.","trash.ask.ok":"Move to the Trash","trash.working":"Moving to the Trash…","trash.result":"Moved {n} · {size}","act.clear":"Clear","act.trash":"Move to the Trash","show.mac":"Show in Finder","show.win":"Show","show.linux":"Show","perm.mac":"Protected folders need Full Disk Access, in System Settings › Privacy & Security. Then reopen Twenties.","perm.win":"Run Twenties as administrator to read protected folders too.","perm.linux":"Read permission is needed for those folders.","tool.mac":"To read RAR and 7z, install 7-Zip. ZIP and TAR are checked anyway.","tool.win":"To read RAR and 7z, install 7-Zip or WinRAR. ZIP and TAR are checked anyway.","tool.linux":"To read RAR and 7z, install 7-Zip. ZIP and TAR are checked anyway.","home.scarto.kicker":"Discard, estimate","home.scarto.note":"Folders marked discard, plus discard files outside them. Read the names before you move anything.","home.denied":"{n} folders could not be read and were skipped.","home.stats.folders":"Folders","home.stats.files":"Large files","home.stats.games":"Games","home.stats.dups":"Duplicate groups","home.stats.arch":"Extracted archives","home.stats.copies":"Extra copies","home.stats.scarto":"Discard","home.stats.free":"Free on the drives","home.bycat":"By label","home.bycat.note":"Weight of the listed folders, not of the whole disk.","home.quick":"Open a result","home.q.scarto":"See Discard","home.q.dups":"See duplicates","home.q.arch":"See archives","home.q.games":"Game library","home.top":"Heaviest folders","home.legend":"Labels","home.disks.note":"{used} used · {free} free · {total} capacity, on the drives that were read.","intro.folders":"The heaviest folders, with the reason for the label.","intro.files":"The heaviest files. You can move them to the Trash.","intro.dups":"Same hash. One copy of each group stays.","intro.arch":"The content is already extracted on disk.","search":"Search by name or path","sort.size":"Largest first","sort.name":"Name","sort.date":"Oldest first","selok":"Select the extracted ones","keep":"Keep the oldest copy","empty.filters":"Nothing to show with these filters.","empty.dups":"No duplicates, or the search was off.","dups.hash":"BLAKE2b hash of the whole file.","dups.lead":"Extra copies: {size}.","files.count":"{n} files","modified":"modified {d}","level.ok":"Already extracted","level.part":"Partly extracted","level.guess":"Check this","arch.ok":"All {n} files from the archive are already in: {where}","arch.part":"Only partly extracted ({p}%) in: {where}. Look before you move it.","arch.guess":"A folder with the same name exists, but the archive could not be read. Check it yourself.","map.lead":"The color is the label. The reason is beside it.","map.root":"Scanned folders","map.sun":"Rings","map.tree":"Blocks","map.back":"Up one level","map.open":"Open folder","map.trash":"Move to the Trash","map.pick":"Open a folder to see it or move it. A whole drive stays put.","map.empty":"There are no further folders to draw here.","map.confirm":"Move “{name}” to the Trash? {why}","games.lead":"Size, date and launcher. The link opens the library, not one game.","games.launcher":"Launcher","games.unknown":"Recognized from game files, with no launcher in the path.","games.open":"Open {name}","games.access":"Last access","games.modified":"Last modified","games.access.note":"On some disks the access date is not updated.","games.unknown.date":"not recorded","games.empty":"No games in this scan.","settings.title":"Settings","settings.lang":"Language","settings.lang.why":"On startup it uses the system language.","settings.updates":"Version notice","settings.updates.why":"If you turn this on, it asks GitHub only for the latest version number.","settings.schedule":"Discard reminder","settings.schedule.why":"Off. If you turn it on, it sometimes lists discard. It goes to the Trash only if you confirm.","settings.days":"Every how many days","settings.history":"History","settings.history.empty":"No actions yet.","settings.undo":"Undo","settings.undo.manual":"I could not put it back. It is in the Trash: you can restore it from there.","settings.account":"Account","settings.delete":"Delete account","common.cancel":"Cancel","update.banner":"Version {v} is available.","update.open":"Open the page","update.later":"Not now","schedule.card":"Discard preview","schedule.lead":"Discard only. Nothing moves until you confirm.","schedule.now":"Move to the Trash","schedule.later":"Not now","schedule.empty":"There is no discard in this scan.","schedule.confirm":"Move the files in this preview to the Trash?","undo.ok":"Put back: {n}.","need.root":"Pick a drive, or type a folder.","err.offline":"Could not reach the program.","err.rate":"Too many attempts. Try again in a few minutes."}}
PAGE = r"""<!doctype html><html lang="it" data-th="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>Twenties</title>
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<script nonce="__NONCE__">try{document.documentElement.dataset.th=localStorage.getItem("tc_th")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light")}catch(e){}</script>
<style nonce="__NONCE__">
:root{
 --bg:#F3EEE6;--card:#FFFCF7;--ink:#111114;--inv:#F3EEE6;--mu:#5C574E;
 --line:rgba(17,17,20,.12);--fill:rgba(17,17,20,.05);--fill2:rgba(17,17,20,.08);
 --accent:#0F6E6B;--on:#fff;--sand:#D9CDB8;--warn:#C2410C;
 --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;--s7:48px;
 --side:208px;
 --f:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
 --serif:Iowan Old Style,Palatino,"Palatino Linotype",Georgia,serif;
}
[data-th=dark]{
 --bg:#111114;--card:#1C1C22;--ink:#F3EEE6;--inv:#111114;--mu:#B7A995;
 --line:rgba(243,238,230,.14);--fill:rgba(243,238,230,.06);--fill2:rgba(243,238,230,.12);
 --accent:#1F8F8B;--sand:#3A342C;--warn:#E07A45;
}
*{box-sizing:border-box}[hidden]{display:none!important}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--ink);font:14px/1.45 var(--f);-webkit-font-smoothing:antialiased}
button,input,select{font:inherit;color:inherit}
button{white-space:normal}
h1,h2,h3,p{margin:0;overflow-wrap:anywhere}
h1,h2,.hero h2,.slide h1,.slide h2{font-family:var(--serif);font-weight:600}
a{color:var(--accent)}
img,svg{max-width:100%;display:block}
#shell{height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);min-width:0}
header{display:flex;align-items:center;gap:var(--s3);padding:var(--s2) var(--s4);border-bottom:1px solid var(--line);background:var(--card);min-width:0}
img.logo{width:32px;height:32px;border-radius:8px;background:#0B0C12;flex:none}
.brand{min-width:0}
.brand b{display:block;font-size:15px;font-weight:650}
.brand .tag{display:block;color:var(--mu);font-size:12px}
#frame{display:grid;grid-template-columns:var(--side) minmax(0,1fr);min-height:0;min-width:0}
#sidenav{display:flex;flex-direction:column;gap:var(--s1);padding:var(--s2);border-right:1px solid var(--line);background:var(--sand);min-height:0;min-width:0;overflow:auto}
#nav{display:flex;flex-direction:column;gap:var(--s1);min-width:0}
.sidegrow{flex:1 1 auto;min-height:var(--s2)}
.nv,.sidebtn{display:flex;justify-content:space-between;align-items:center;gap:var(--s2);width:100%;text-align:left;background:transparent;border:0;border-radius:4px;padding:6px var(--s2);color:var(--ink);cursor:pointer}
.nv em{font-style:normal;font-size:12px;opacity:.75}
.nv.on,.sidebtn.on{background:var(--ink);color:var(--inv)}
.nv:hover,.sidebtn:hover{background:var(--fill)}
.nv.on:hover{background:var(--ink)}
#who{color:var(--mu);font-size:13px;padding:var(--s2) var(--s3) 0}
#stage{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--bg)}
#notice{display:flex;flex-direction:column;gap:var(--s2);padding:var(--s3) var(--s4) 0}
#notice:not(:has(*:not([hidden]))){display:none;padding:0}
#upd,#toast{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:var(--s3) var(--s4);display:flex;flex-wrap:wrap;gap:var(--s2) var(--s3);align-items:center;justify-content:space-between}
#views{flex:1;min-height:0;min-width:0;overflow:hidden;display:flex;flex-direction:column}
#views>*{flex:1;min-height:0;min-width:0;overflow:auto;padding:var(--s3) var(--s4)}
#act{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:center;padding:var(--s3) var(--s4);border-top:1px solid var(--line);background:var(--card)}
#act .dng{background:var(--warn);color:#fff;border:0;border-radius:4px;padding:6px 12px;cursor:pointer;font-weight:600}
.stack{display:flex;flex-direction:column;gap:var(--s3);min-width:0}
.grid-2{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(220px,.8fr);gap:var(--s3);align-items:start}
.grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:var(--s2)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--s3)}
.card{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:var(--s3);min-width:0}
.card h2{font-size:22px}
.card h3{font-size:15px;font-weight:650}
.s{color:var(--mu);margin-top:var(--s1)}
.r{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:center;min-width:0}
.btn{background:transparent;border:1px solid var(--line);border-radius:4px;padding:6px 10px;cursor:pointer}
.btn:hover{background:var(--fill)}
.pri{background:var(--accent);color:var(--on);border:0;border-radius:4px;padding:8px 14px;cursor:pointer;font-weight:600}
.pri:disabled,.btn:disabled{opacity:.45;cursor:default}
.chip{display:inline-flex;align-items:center;gap:var(--s2);border:1px solid var(--line);border-radius:4px;padding:4px 8px;background:var(--card);color:var(--ink);cursor:pointer}
.chip.on{background:var(--ink);color:var(--inv);border-color:var(--ink)}
input[type=text],input[type=email],input[type=password],input[type=number],select{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:8px 10px;min-width:0;max-width:100%}
input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}
.metric{background:transparent;border-top:1px solid var(--line);border-radius:0;padding:var(--s2) 0;min-width:0}
.metric b{display:block;font-size:22px;font-family:var(--serif);font-weight:600;margin-top:var(--s1)}
.metric small,.s{overflow-wrap:anywhere}
.hero h2{font-size:clamp(26px,4vw,36px);line-height:1.15;font-weight:600}
.hero-top{display:flex;flex-wrap:wrap;gap:var(--s4);align-items:flex-end;justify-content:space-between}
.hero-top .copy{flex:1 1 220px;min-width:0}
.dcard{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:var(--s1) var(--s3);align-items:center;padding:var(--s2) 0;border-top:1px solid var(--line);border-radius:0;min-width:0}
.dcard:has(input:checked){color:var(--ink)}
.dcard b,.dcard small{overflow-wrap:anywhere;min-width:0}
.dcard .pct{font-size:18px;font-family:var(--serif);font-weight:600}
.dcard .bar{grid-column:1 / -1}
.bar{height:4px;background:var(--fill2);border-radius:0;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--accent)}
.kv{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s2);padding:var(--s2) 0;border-top:1px solid var(--line)}
.kv span{color:var(--mu)}
.kv b{text-align:right;font-weight:600;overflow-wrap:anywhere}
.opt{display:flex;flex-direction:column;align-items:flex-start;gap:var(--s2);border-top:1px solid var(--line);border-radius:0;padding:var(--s2) 0;background:transparent;min-width:0}
.pill{display:inline;max-width:100%;font-size:12px;font-weight:650;padding:0;border-radius:0;background:none}
.p-g{color:var(--accent)}
.p-s{color:var(--warn)}
.p-l{color:var(--mu)}
.p-m{color:var(--ink)}
.p-h{color:var(--ink)}
.row{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--s2) var(--s3);padding:var(--s3) 0;border-top:1px solid var(--line);align-items:start}
.row .nm{min-width:0}
.row .nm b,.row .nm small{display:block;overflow-wrap:anywhere}
.row .nm small{color:var(--mu)}
.row .sz{grid-column:1 / -1}
.row .go{justify-self:start}
.warn{border-left:3px solid var(--warn);padding:var(--s1) 0 var(--s1) var(--s3)}
.grp{border-top:1px solid var(--line);border-radius:0;padding:var(--s2) 0;margin-top:var(--s2);min-width:0}
.cp{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--s2);align-items:start;margin-top:var(--s2)}
.cp span{overflow-wrap:anywhere;color:var(--mu)}
.statgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:var(--s3)}
button.k{display:block;width:100%;text-align:left;background:transparent;border:0;border-top:1px solid var(--line);border-radius:0;padding:var(--s2) 0;cursor:pointer;min-width:0}
button.k b{display:block;font-size:20px;font-family:var(--serif);font-weight:600}
button.k small{color:var(--mu)}
.leg{display:flex;flex-direction:column;gap:var(--s2)}
.leg div{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:flex-start;color:var(--mu)}
.maplay{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(200px,.7fr);gap:var(--s4);align-items:start}
#mapdraw{min-width:0}
#mapdraw svg{width:100%;height:auto}
#mapinfo{min-width:0}
.glib{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--s3)}
.gcard{border-top:1px solid var(--line);border-radius:0;padding:var(--s2) 0;min-width:0;background:transparent}
.gcard p{color:var(--mu);margin-top:var(--s1)}
.setrow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:var(--s3);align-items:center;padding:var(--s3) 0;border-top:1px solid var(--line)}
.setrow p{color:var(--mu);margin-top:var(--s1)}
.hitem{padding:var(--s2) 0;border-top:1px solid var(--line)}
.steps{display:flex;flex-wrap:wrap;gap:var(--s2)}
.st{font-size:12px;padding:2px 0;margin-right:var(--s3);color:var(--mu)}
.st.on{color:var(--ink);font-weight:650}
.sk{height:28px;border-radius:0;background:var(--fill2)}
.authbox{max-width:440px;margin:0 auto;display:flex;flex-direction:column;gap:var(--s3)}
.authbox img.logo{width:48px;height:48px;border-radius:12px}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:var(--s2)}
.seg button{background:transparent;border:0;border-bottom:1px solid transparent;border-radius:0;padding:6px 0;cursor:pointer;color:var(--mu)}
.seg button.on{background:var(--card);color:var(--ink)}
.fe{min-height:18px;color:var(--warn);font-size:13px}
.fe.ok{color:var(--mu)}
.links{display:flex;flex-wrap:wrap;gap:var(--s3)}
.links button{background:none;border:0;color:var(--mu);cursor:pointer;padding:0}
#intro{display:flex;flex-direction:column;gap:var(--s4);background:#111114;color:#F3EEE6}
#intro .skip{align-self:flex-end;background:none;border:0;color:#B7A995;cursor:pointer;padding:var(--s2)}
.slide{display:none;flex-direction:column;gap:var(--s4);max-width:640px}
.slide.on{display:flex}
.slide h1,.slide h2{font-size:clamp(26px,4vw,40px);line-height:1.15;font-weight:600;color:#F3EEE6}
.slide p{color:#D9CDB8;font-size:17px}
.slide img{width:56px;height:56px;border-radius:14px}
.foot{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:center}
.dots{display:flex;gap:var(--s2)}
.dots i{width:6px;height:6px;border-radius:6px;background:#3a3a3c}
.dots i.on{background:#F3EEE6}
#confirm .sheet{max-width:480px;display:flex;flex-direction:column;gap:var(--s3)}
#confirm p{white-space:pre-line}
@media(max-width:880px){
 #frame{grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr)}
 #sidenav{flex-direction:row;flex-wrap:wrap;border-right:0;border-bottom:1px solid var(--line);max-height:42%;overflow:auto}
 #nav{flex-direction:row;flex-wrap:wrap}
 .nv,.sidebtn{width:auto}
 .sidegrow{display:none}
 .grid-2,.maplay,.setrow{grid-template-columns:minmax(0,1fr)}
 .setrow{align-items:start}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>
<div id=shell>
<header><img class=logo src="/logo.svg" alt=""><div class=brand><b data-k=app.name>Twenties</b><span class=tag data-k=tagline>Vedi cosa pesa. Decidi tu.</span></div></header>
<div id=frame>
<nav id=sidenav>
 <div id=nav><button type=button class="nv on" data-t=home data-k=nav.home>Panoramica</button></div>
 <div class=sidegrow></div>
 <button type=button class=sidebtn id=again hidden data-k=again>Nuova analisi</button>
 <button type=button class=sidebtn id=gear data-k=settings>Impostazioni</button>
 <button type=button class=sidebtn id=histBtn data-k=settings.history>Cronologia</button>
 <button type=button class=sidebtn id=acct data-k=account>Account</button>
 <button type=button class=sidebtn id=th data-k=theme>Tema</button>
 <button type=button class=sidebtn id=quit data-k=quit>Chiudi</button>
 <p id=who></p>
</nav>
<div id=stage>
 <div id=notice><div id=upd hidden></div><div id=toast hidden></div></div>
 <div id=views>
  <div id=intro hidden>
   <button class=skip id=skip data-k=intro.skip>Salta</button>
   <div class=slides>
    <div class="slide on"><img src="/logo.svg" alt=""><h1 data-k=intro.1.title>Vedi cosa pesa.</h1><p data-k=intro.1.body></p></div>
    <div class=slide><h2 data-k=intro.2.title>Non tocca da solo.</h2><p data-k=intro.2.body></p></div>
    <div class=slide><h2 data-k=intro.3.title>Finisce nel Cestino.</h2><p data-k=intro.3.body></p></div>
   </div>
   <div class=foot><div class=dots id=dots></div><button class=pri id=nx data-k=intro.next>Continua</button></div>
  </div>
  <div id=auth hidden></div>
  <div id=app hidden>
   <div id=scan class=stack>
    <section class="card hero">
     <div class=hero-top>
      <div class=copy><p class=s id=greet></p><h2 data-k=hero.title>Vedi cosa pesa.</h2><p class=s data-k=hero.body></p></div>
      <button class=pri id=go data-k=go>Avvia analisi</button>
     </div>
     <div class=grid-3 id=disksum style="margin-top:16px"><div class=sk></div><div class=sk></div><div class=sk></div></div>
    </section>
    <div class=grid-2>
     <section class=card>
      <h3 data-k=disks>Dischi</h3><p class=s id=pick></p>
      <div class=stack id=drv style="margin-top:8px"><div class=sk></div></div>
     </section>
     <div class=stack>
      <section class=card id=sched hidden></section>
      <section class=card><h3 data-k=status.title>Stato</h3><div id=sys></div></section>
     </div>
    </div>
    <section class=card>
     <h3 data-k=quick.title>Come analizzare</h3><p class=s data-k=quick.hint></p>
     <div class=stack>
      <div class=opt><label class=chip><input type=checkbox id=dups checked><span data-k=opt.dups>Doppioni esatti</span></label><div class=r><span data-k=opt.dups_from>solo file da</span><input type=number id=minmb value=5 min=1 style="width:88px"><span>MB</span></div><p class=s data-k=opt.dups_why></p></div>
      <div class=opt><label class=chip><input type=checkbox id=arch checked><span data-k=opt.arch>Archivi già estratti</span></label><p class=s data-k=opt.arch_hint></p></div>
      <div class=opt><input type=text id=custom data-ph=opt.folder style="width:100%"></div>
     </div>
    </section>
    <section class=card>
     <h3 data-k=about.title>Cosa guarda</h3><p class=s data-k=about.body></p>
     <div class=cards>
      <article><h3 data-k=about.folders.t></h3><p class=s data-k=about.folders.d></p></article>
      <article><h3 data-k=about.files.t></h3><p class=s data-k=about.files.d></p></article>
      <article><h3 data-k=about.games.t></h3><p class=s data-k=about.games.d></p></article>
      <article><h3 data-k=about.dups.t></h3><p class=s data-k=about.dups.d></p></article>
      <article><h3 data-k=about.arch.t></h3><p class=s data-k=about.arch.d></p></article>
     </div>
    </section>
    <section class=card id=prog hidden>
     <h3 data-k=prog.title>Analisi in corso</h3><p class=s data-k=prog.body></p>
     <div class=steps id=steps></div>
     <p id=msg class=s></p>
     <div class=bar id=bar hidden><i></i></div>
    </section>
   </div>
   <div id=res hidden><section id=view class=stack></section></div>
   <div id=setview hidden></div>
   <div id=histview hidden></div>
  </div>
  <div id=confirm hidden></div>
 </div>
 <div id=act hidden></div>
</div>
</div>
</div>
<script nonce="__NONCE__">
"use strict";
const I18N=__I18N__;
let LANG="it";
function t(k){const a=(I18N[LANG]||I18N.it||{});return a[k]||(I18N.it||{})[k]||k}
function tf(k,o){let s=t(k);if(o)Object.keys(o).forEach(n=>{s=s.split("{"+n+"}").join(String(o[n]))});return s}
function applyLang(){document.documentElement.lang=LANG;document.title=t("app.name");document.querySelectorAll("[data-k]").forEach(el=>{el.textContent=t(el.dataset.k)});document.querySelectorAll("[data-ph]").forEach(el=>{el.placeholder=t(el.dataset.ph)})}
const SHOT=new URLSearchParams(location.search).get("shot")||"";
function outside(u){try{const x=new URL(String(u),location.href);return (x.protocol==="http:"||x.protocol==="https:")&&x.host!==location.host}catch(e){return false}}
document.addEventListener("click",e=>{let n=e.target;while(n&&n!==document){if(n.tagName==="A"&&n.href)break;n=n.parentNode}if(!n||n===document||!outside(n.href))return;const api=window.pywebview&&window.pywebview.api;if(!api||!api.open_external)return;e.preventDefault();e.stopPropagation();api.open_external(n.href)},true);
const CATS=["Gioco","Scarto","Importanza bassa","Importanza media","Importanza elevata"];
const CK={"Gioco":"cat.gioco","Scarto":"cat.scarto","Importanza bassa":"cat.bassa","Importanza media":"cat.media","Importanza elevata":"cat.elevata"};
const PC={"Gioco":"p-g","Scarto":"p-s","Importanza bassa":"p-l","Importanza media":"p-m","Importanza elevata":"p-h"};
const WHY={"gioco rilevato (cartella di launcher o file del motore di gioco)":"why.game","cache, temporanei o log: di solito eliminabili":"why.junk","sistema: non toccare":"why.sys","programma installato (si rimuove trascinando l'app nel Cestino)":"why.prog.mac","programma installato (si rimuove dalle Impostazioni)":"why.prog.win","prevalentemente file temporanei, log o backup":"why.mostlyjunk","documenti, foto o progetti personali":"why.docs","cartella Download: spesso roba riscaricabile, controlla":"why.down","immagini disco, ISO o macchine virtuali":"why.iso","video/audio/archivi non toccati da 2+ anni":"why.oldmedia","video, audio o archivi":"why.media","contenuto misto, non toccato da 2+ anni":"why.oldmix","contenuto misto, usato di recente":"why.mix","file di un gioco":"why.gamefile","temporaneo, cache, log o backup":"why.temp","installer scaricato, riscaricabile":"why.inst","file di sistema":"why.sysfile","documento, foto o progetto personale":"why.doc","immagine disco/ISO, di solito riscaricabile":"why.isofile","media/archivio vecchio o in Download":"why.oldfile","video, audio o archivio":"why.mediafile","tipo sconosciuto, non modificato da 2+ anni":"why.oldunk","tipo sconosciuto, usato di recente":"why.unk"};
const NAV=[["home","nav.home"],["map","nav.map"],["folders","nav.folders"],["games","nav.games"],["files","nav.files"],["dups","nav.dups"],["arch","nav.arch"]];
const STEPK={scan:"step.scan",agg:"step.agg",dups:"step.dups",arch:"step.arch"};
let ME=null,CSRF="",GOOGLE=false,MAIL=false,PLAT="linux",RT="",AMODE="login",FLASH=null,scanned=null;
let R=null,tab="home",filt="Tutti",q="",sortk="size",sel=new Set(),running=false,timer,AM={},SZ={};
let UPDATES=false,SCHED={enabled:false,due:false,days:7},mapMode="sun",mapFocus="",mapStack=[];
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?"":s).replace(/[&<>"'`]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;","`":"&#96;"}[c]));
const fmt=n=>{n=Number(n)||0;const u=["B","KB","MB","GB","TB"];let i=0;while(n>=1024&&i<4){n/=1024;i++}return (i?n.toFixed(1):n)+" "+u[i]};
const loc=()=>LANG==="en"?"en":"it";
const dt=v=>v?new Date(v*1000).toLocaleDateString(loc()):"";
const pill=cat=>`<span class="pill ${PC[cat]||""}">${esc(t(CK[cat]||"cat.media"))}</span>`;
function whyOf(x){if(!x)return "";if(x.why_code==="arch.ok")return tf("arch.ok",{n:x.why_n,where:x.why_where});if(x.why_code==="arch.part")return tf("arch.part",{p:Math.round((x.why_ratio||0)*100),where:x.why_where});if(x.why_code==="arch.guess")return t("arch.guess");const k=WHY[x.why];return k?t(k):(x.why||"")}
function os(k){const p=PLAT==="mac"||PLAT==="win"?PLAT:"linux";return t(k+"."+p)}
function showPanel(id){["intro","auth","app","confirm"].forEach(p=>{const el=document.getElementById(p);if(el)el.hidden=p!==id})}
function showAppView(id){showPanel("app");["scan","res","setview","histview"].forEach(p=>{const el=document.getElementById(p);if(el)el.hidden=p!==id});document.querySelectorAll("#sidenav .sidebtn").forEach(b=>b.classList.remove("on"));if(id==="setview")$("#gear").classList.add("on");if(id==="histview")$("#histBtn").classList.add("on")}
function toast(h,ms){const el=$("#toast");clearTimeout(el._t);el.textContent=h;el.hidden=false;el._t=setTimeout(()=>{el.hidden=true},ms||5000)}
function toastUndo(h,id){const el=$("#toast");clearTimeout(el._t);el.replaceChildren(document.createTextNode(h));if(id){const b=document.createElement("button");b.className="btn";b.textContent=t("settings.undo");b.onclick=()=>doUndo(id);el.append(b)}el.hidden=false;el._t=setTimeout(()=>{el.hidden=true},9000)}
async function api(u,b){const o=b===undefined?{credentials:"same-origin"}:{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRF-Token":CSRF},body:JSON.stringify(b)};let r,j;try{r=await fetch(u,o);j=await r.json()}catch(e){return{error:t("err.offline"),_s:0}}if(j&&typeof j==="object")j._s=r.status;if(r.status===401&&ME&&u!=="/api/login"){ME=null;stopPoll();showAuth("login");toast(t("session.expired"))}return j}
async function googleGo(){const r=await api("/api/google_begin",{});if(!r||r.error){toast(r&&r.error?r.error:t("auth.google.off"));return}if(r.same){location.href="/auth/google";return}toast(t("google.wait"),300000);for(let i=0;i<150;i++){await new Promise(z=>setTimeout(z,2000));const q=await api("/api/google_poll",{ticket:r.ticket});if(q&&q.ready){location.replace("/auth/finish?t="+encodeURIComponent(r.ticket));return}if(q&&q.error){toast(t("google.fail"));return}}toast(t("google.timeout"))}
function ask(title,body,ok){return new Promise(res=>{const ids=["intro","auth","app"];const prev=ids.map(id=>({id,h:document.getElementById(id).hidden}));ids.forEach(id=>{document.getElementById(id).hidden=true});const box=$("#confirm");box.hidden=false;box.innerHTML=`<div class=sheet role=dialog><h2>${esc(title)}</h2><p>${esc(body)}</p><div class=r><button type=button class=btn data-m=0>${esc(t("common.cancel"))}</button><button type=button class=pri data-m=1>${esc(ok)}</button></div></div>`;const done=v=>{box.hidden=true;box.innerHTML="";prev.forEach(x=>{document.getElementById(x.id).hidden=x.h});res(v)};box.onclick=e=>{const b=e.target.closest("[data-m]");if(b)done(b.dataset.m==="1")};const p=box.querySelector(".pri");if(p)p.focus()})}
let si=0;const SL=()=>[...document.querySelectorAll(".slide")];
function slide(n){si=n;SL().forEach((s,i)=>s.classList.toggle("on",i===n));const dots=$("#dots");dots.innerHTML=SL().map(()=>"<i></i>").join("");[...dots.children].forEach((d,i)=>d.classList.toggle("on",i===n));$("#nx").textContent=n===SL().length-1?t("intro.start"):t("intro.next")}
function endIntro(){try{localStorage.setItem("tc_onboard","1")}catch(e){}api("/api/settings",{onboarded:true});enterApp()}
$("#nx").onclick=()=>si<SL().length-1?slide(si+1):endIntro();$("#skip").onclick=endIntro;
function fe(m,ok){const e=$("#fe");if(e){e.textContent=m||"";e.className="fe"+(ok?" ok":"")}}
function showAuth(mode){AMODE=mode;showPanel("auth");const A=$("#auth");const titles={login:["auth.login.title","auth.login.sub"],register:["auth.register.title","auth.register.sub"],forgot:["auth.forgot.title","auth.forgot.sub"],reset:["auth.reset.title","auth.reset.sub"]}[mode];const lr=mode==="login"||mode==="register";
A.innerHTML=`<div class=authbox><img class=logo src="/logo.svg" alt=""><h2>${esc(t(titles[0]))}</h2><p class=s>${esc(t(titles[1]))}</p>${lr?`<div class=seg><button type=button data-am=login class="${mode==="login"?"on":""}">${esc(t("auth.submit.login"))}</button><button type=button data-am=register class="${mode==="register"?"on":""}">${esc(t("auth.submit.register"))}</button></div>`:""}<form id=af class=stack>${mode!=="reset"?`<input type=email id=em placeholder="${esc(t("auth.email"))}" autocomplete=email maxlength=254 required>`:""}${mode!=="forgot"?`<input type=password id=pw placeholder="${esc(t("auth.password"))}" maxlength=128 required>`:""}<div id=fe class=fe role=alert></div><button class=pri id=sb type=submit>${esc(t({login:"auth.submit.login",register:"auth.submit.register",forgot:"auth.submit.forgot",reset:"auth.submit.reset"}[mode]))}</button></form>${lr?`<button type=button class=btn id=gg ${GOOGLE?"":"disabled"}>${esc(t("auth.google"))}</button>${GOOGLE?"":`<p class=s>${esc(t("auth.google.off"))}</p>`}`:""}<div class=links>${mode==="login"?`<button type=button data-am=forgot>${esc(t("auth.forgot.link"))}</button>`:""}${mode!=="login"?`<button type=button data-am=login>${esc(t("auth.back"))}</button>`:""}<button type=button id=guestbtn>${esc(t("auth.guest"))}</button></div></div>`;if(FLASH){fe(FLASH);FLASH=null}const f=$("#em")||$("#pw");if(f)f.focus()}
document.addEventListener("submit",async e=>{if(e.target.id!=="af")return;e.preventDefault();const em=$("#em")?$("#em").value.trim():"",pw=$("#pw")?$("#pw").value:"",b=$("#sb");b.disabled=true;fe("");let r;if(AMODE==="forgot")r=await api("/api/forgot",{email:em});else if(AMODE==="reset")r=await api("/api/reset",{token:RT,password:pw});else r=await api(AMODE==="login"?"/api/login":"/api/register",{email:em,password:pw});b.disabled=false;if(r.error)return fe(r.error);if(AMODE==="forgot")fe(MAIL?t("auth.forgot.sent"):t("auth.forgot.nomail"),true);else if(AMODE==="reset"){RT="";ME=null;enterApp();toast(t("auth.reset.ok"))}else{ME=r.user;CSRF=r.csrf;enterApp()}});
function paintAcct(){const b=$("#acct");if(b)b.textContent=ME?t("logout"):t("account");const w=$("#who");if(w)w.textContent=ME?(ME.name?ME.name+" · "+ME.email:ME.email):t("who.guest")}
function resetUI(){R=null;sel.clear();tab=SHOT==="map"?"map":"home";filt="Tutti";q="";running=false;scanned=null;mapFocus="";mapStack=[];showAppView("scan");$("#again").hidden=true;$("#prog").hidden=true;$("#act").hidden=true;const g=$("#go");if(g)g.textContent=t("go")}
function driveCard(x){const pct=x.total?Math.min(100,Math.round(x.used/x.total*100)):0;return `<label class=dcard><input type=checkbox checked value="${esc(x.path)}"><span><b>${esc(x.path)}</b><small>${esc(tf("disk.meta",{used:fmt(x.used),free:fmt(x.free),total:fmt(x.total)}))}</small></span><span class=pct>${pct}%</span><div class=bar><i style="width:${pct}%"></i></div></label>`}
function updatePick(){const el=$("#pick");if(!el)return;const all=document.querySelectorAll("#drv input").length,n=document.querySelectorAll("#drv input:checked").length;el.textContent=all?tf("disks.pick",{n:n,all:all}):t("disks.none")}
function paintStatus(){const el=$("#sys");if(!el)return;const plat={mac:"macOS",win:"Windows",linux:"Linux"}[PLAT]||PLAT;const rows=[[t("status.platform"),plat],[t("status.conn"),t("status.local")],[t("status.account"),ME?(ME.email):t("who.guest")],[t("status.google"),GOOGLE?t("status.yes"):t("status.no")],[t("status.analysis"),running?t("status.running"):(R&&R.folders?t("status.ready"):t("status.idle"))]];if(scanned!=null)rows.push([t("status.read"),scanned.toLocaleString(loc())]);if(R&&R.folders){rows.push([t("status.denied"),String(R.denied||0)]);rows.push([t("status.rar"),R.tool?t("status.yes"):t("status.no")])}el.innerHTML=rows.map(([k,v])=>`<div class=kv><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("")}
function hello(){const h=new Date().getHours(),p=h<5?t("greet.night"):h<12?t("greet.morning"):h<18?t("greet.afternoon"):t("greet.evening"),g=$("#greet");if(g)g.textContent=ME&&ME.name?p+", "+ME.name:p}
async function loadDrives(){const d=await api("/api/drives");if(!Array.isArray(d)||!$("#drv"))return;$("#drv").innerHTML=d.length?d.map(driveCard).join(""):`<p class=s>${esc(t("disks.none"))}</p>`;updatePick();const used=d.reduce((a,x)=>a+(x.used||0),0),total=d.reduce((a,x)=>a+(x.total||0),0),free=d.reduce((a,x)=>a+(x.free||0),0);$("#disksum").innerHTML=`<div class=metric><small>${esc(t("metric.used"))}</small><b>${fmt(used)}</b></div><div class=metric><small>${esc(t("metric.free"))}</small><b>${fmt(free)}</b></div><div class=metric><small>${esc(t("metric.cap"))}</small><b>${fmt(total)}</b><small>${d.length===1?t("metric.one"):tf("metric.many",{n:d.length})}</small></div>`}
async function showSchedule(){const box=$("#sched");if(!box)return;if(!SCHED||!SCHED.enabled||!SCHED.due){box.hidden=true;return}const s=await api("/api/schedule");if(!s||s.error||!s.due){box.hidden=true;return}const items=s.preview||[];box.hidden=false;box.innerHTML=`<h3>${esc(t("schedule.card"))}</h3><p class=s>${esc(t("schedule.lead"))}</p>`+(items.length?`<p><b>${fmt(items.reduce((a,x)=>a+(x.size||0),0))}</b></p><div class=stack>`+items.slice(0,40).map(x=>`<div class=hitem><b>${esc(x.name)}</b> · ${fmt(x.size)}<br><span class=s>${esc(whyOf(x))}</span></div>`).join("")+`</div><div class=r><button class=pri id=schedgo>${esc(t("schedule.now"))}</button><button class=btn id=schedlater>${esc(t("schedule.later"))}</button></div>`:`<p class=s>${esc(t("schedule.empty"))}</p><button class=btn id=schedlater>${esc(t("schedule.later"))}</button>`);const go=$("#schedgo");if(go)go.onclick=async()=>{if(!await ask(t("trash.ask.title"),t("schedule.confirm"),t("trash.ask.ok")))return;const r=await api("/api/schedule_apply",{paths:items.map(x=>x.path)});if(r.error){toast(r.error);return}SCHED.due=false;box.hidden=true;if(r.undo)toastUndo(tf("trash.result",{n:r.done.length,size:fmt(r.freed)}),r.undo);if(R){R=await api("/api/results");if(R&&R.folders){idx();render()}}};const later=$("#schedlater");if(later)later.onclick=async()=>{await api("/api/settings",{schedule_dismiss:true});SCHED.due=false;box.hidden=true}}
async function checkUpdates(){if(!UPDATES){$("#upd").hidden=true;return}const r=await api("/api/update_check",{});if(!r||!r.update||!r.url)return;let hide="";try{hide=localStorage.getItem("tc_upd_hide")||""}catch(e){}if(hide&&hide===r.latest)return;const el=$("#upd");el.hidden=false;el.innerHTML=`<span>${esc(tf("update.banner",{v:r.latest}))}</span><span class=r><a href="${esc(r.url)}">${esc(t("update.open"))}</a><button type=button class=btn id=updno>${esc(t("update.later"))}</button></span>`;$("#updno").onclick=()=>{try{localStorage.setItem("tc_upd_hide",r.latest)}catch(e){}el.hidden=true}}
async function enterApp(){showPanel("app");applyLang();paintAcct();resetUI();hello();paintStatus();const drives=loadDrives();const s=await api("/api/status");if(s.phase==="done"&&s.has_res&&SHOT!=="app"){R=await api("/api/results");if(R&&R.folders){idx();if(SHOT==="map")tab="map";if(SHOT==="games")tab="games";render()}}else if(["scan","agg","dups","arch"].includes(s.phase)){running=true;$("#go").textContent=t("stop");$("#prog").hidden=false;timer=setInterval(poll,600);poll()}paintStatus();await drives;showSchedule();checkUpdates();if(SHOT==="settings")showSettings();if(SHOT==="history")showHistory()}
function stopPoll(){clearInterval(timer);running=false}
function list(){let L=tab==="folders"?R.folders:tab==="files"?R.files:R.archives;if(tab==="folders"||tab==="files")L=L.filter(x=>filt==="Tutti"||x.cat===filt);if(q)L=L.filter(x=>(x.path||"").toLowerCase().includes(q));return [...L].sort((a,b)=>sortk==="name"?a.name.localeCompare(b.name):sortk==="date"?(a.mtime||0)-(b.mtime||0):b.size-a.size)}
function row(x,mx){const isA=tab==="arch",ck=tab==="files"||isA,pl=isA?`<span class="pill ${x.level==="ok"?"p-s":"p-m"}">${esc(t("level."+x.level))}</span>`:pill(x.cat);const why=whyOf(x)+(x.files!=null&&!isA?" · "+tf("files.count",{n:Number(x.files).toLocaleString(loc())}):"");return `<div class=row>${ck?`<input type=checkbox data-s="${esc(x.path)}" ${sel.has(x.path)?"checked":""}>`:""}<div class=nm>${pl} <b>${esc(x.name)}</b><small>${esc(x.path)}</small><small>${esc(why)}${x.mtime?" · "+esc(tf("modified",{d:dt(x.mtime)})):""}</small></div><div class=sz>${fmt(x.size)}<div class=bar><i style="width:${Math.max(2,x.size/mx*100)}%"></i></div></div><button class="btn go" data-p="${esc(x.path)}">${esc(os("show"))}</button></div>`}
function home(){const tot=R.totals||{},scarto=R.scarto_total||tot["Scarto"]||0;const folders=R.folders||[],files=R.files||[],dups=R.dups||[],arch=R.archives||[],games=R.games||folders.filter(x=>x.cat==="Gioco"),disks=R.disks||[];const free=disks.reduce((a,d)=>a+(d.free||0),0),used=disks.reduce((a,d)=>a+(d.used||0),0),total=disks.reduce((a,d)=>a+(d.total||0),0);const catSum=CATS.reduce((a,c)=>a+(tot[c]||0),0);let h=`<section class=card><p class=s>${esc(t("home.scarto.kicker"))}</p><h2>${fmt(scarto)}</h2><p class=s>${esc(t("home.scarto.note"))}</p></section>`;if(R.denied)h+=`<div class=warn><p>${esc(tf("home.denied",{n:Number(R.denied).toLocaleString(loc())}))} ${esc(os("perm"))}</p></div>`;if(!R.tool)h+=`<div class=warn><p>${esc(t("tool."+(PLAT==="mac"||PLAT==="win"?PLAT:"linux")))}</p></div>`;const stats=[[t("home.stats.folders"),folders.length,"folders"],[t("home.stats.files"),files.length,"files"],[t("home.stats.games"),games.length,"games"],[t("home.stats.dups"),dups.length,"dups"],[t("home.stats.arch"),arch.length,"arch"],[t("home.stats.copies"),fmt(R.wasted||0),"dups"],[t("home.stats.scarto"),fmt(scarto),"folders"],[t("home.stats.free"),fmt(free),""]];h+=`<div class=statgrid>`+stats.map(([l,n,go])=>go?`<button type=button class=k data-go="${go}"><small>${esc(l)}</small><b>${typeof n==="number"?n.toLocaleString(loc()):n}</b></button>`:`<div class=k><small>${esc(l)}</small><b>${n}</b></div>`).join("")+`</div>`;h+=`<section class=card><h2>${esc(t("home.bycat"))}</h2><p class=s>${esc(t("home.bycat.note"))}</p>`+CATS.map(c=>{const v=tot[c]||0,p=catSum?v/catSum*100:0;return `<div class=r>${pill(c)}<b>${fmt(v)}</b><div class=bar style="flex:1 1 120px"><i style="width:${p.toFixed(1)}%"></i></div></div>`}).join("")+`</section>`;h+=`<section class=card><h2>${esc(t("home.quick"))}</h2><div class=r>`+[["folders",t("home.q.scarto")],["dups",t("home.q.dups")],["arch",t("home.q.arch")],["games",t("home.q.games")],["map",t("nav.map")]].map(([k,l])=>`<button class=btn data-go="${k}">${esc(l)}</button>`).join("")+`</div></section>`;if(folders[0]){const top=folders.slice(0,4),mx=top[0].size||1;h+=`<section class=card><h2>${esc(t("home.top"))}</h2>`+top.map(x=>`<div class=row>${pill(x.cat)}<div class=nm><b>${esc(x.name)}</b><small>${esc(x.path)}</small><small>${esc(whyOf(x))}</small></div><div class=sz>${fmt(x.size)}<div class=bar><i style="width:${Math.max(2,x.size/mx*100)}%"></i></div></div><button class="btn go" data-p="${esc(x.path)}">${esc(os("show"))}</button></div>`).join("")+`</section>`}h+=`<section class=card><h2>${esc(t("home.legend"))}</h2><div class=leg>`+CATS.map(c=>`<div>${pill(c)} <span>${esc(t("leg."+CK[c].split(".")[1]))}</span></div>`).join("")+`</div></section>`;h+=`<p class=s>${esc(tf("home.disks.note",{used:fmt(used),free:fmt(free),total:fmt(total)}))}</p>`;return h}
function gamesHtml(){const games=(R.games&&R.games.length?R.games:R.folders.filter(x=>x.cat==="Gioco"));let L=games;if(q)L=L.filter(x=>(x.path||"").toLowerCase().includes(q));L=[...L].sort((a,b)=>b.size-a.size);let h=`<section class=card><h2>${esc(t("nav.games"))}</h2><p class=s>${esc(t("games.lead"))}</p><p class=s>${esc(t("games.access.note"))}</p><input id=q placeholder="${esc(t("search"))}" value="${esc(q)}" style="width:100%;margin-top:8px">`;if(!L.length)h+=`<p class=s>${esc(t("games.empty"))}</p>`;else h+=`<div class=glib style="margin-top:12px">`+L.map(g=>{const launch=g.launcher?`<a href="${esc(g.launcher_url)}">${esc(tf("games.open",{name:g.launcher}))}</a>`:`<span>${esc(t("games.unknown"))}</span>`;return `<article class=gcard><b>${esc(g.name)}</b><p>${fmt(g.size)} · ${esc(whyOf(g))}</p><p>${esc(t("games.launcher"))}: ${launch}</p><p>${esc(t("games.access"))}: ${g.atime?dt(g.atime):t("games.unknown.date")}</p><p>${esc(t("games.modified"))}: ${dt(g.mtime)||"—"}</p><button class=btn data-p="${esc(g.path)}">${esc(os("show"))}</button></article>`}).join("")+`</div>`;return h+`</section>`}
function findNode(path,nodes){for(const n of nodes||[]){if(n.path===path)return n;const c=findNode(path,n.children);if(c)return c}return null}
function currentMap(){const roots=(R&&R.map)||[];if(mapFocus){const n=findNode(mapFocus,roots);if(n)return n}if(roots.length===1)return roots[0];const size=roots.reduce((s,n)=>s+(n.size||0),0);return {name:t("map.root"),path:"",size:size,cat:"",why:t("map.lead"),children:roots,virtual:true}}
function col(cat){const dark=document.documentElement.dataset.th==="dark";const m={"Gioco":"#0F6E6B","Scarto":"#C2410C","Importanza bassa":dark?"#8C7E68":"#C4B49A","Importanza media":dark?"#1F8F8B":"#0F6E6B","Importanza elevata":dark?"#E4DCCE":"#2C2A26"};return m[cat]||"#8A8478"}
function arc(cx,cy,r0,r1,a0,a1){let span=a1-a0;if(span>=Math.PI*2-1e-3){a1=a0+Math.PI*2-0.0001;span=a1-a0}const large=span>Math.PI?1:0;const P=(r,a)=>[cx+Math.cos(a)*r,cy+Math.sin(a)*r];const A=P(r1,a0),B=P(r1,a1),C=P(r0,a1),D=P(r0,a0);const f=n=>n.toFixed(2);return `M${f(A[0])} ${f(A[1])} A${r1} ${r1} 0 ${large} 1 ${f(B[0])} ${f(B[1])} L${f(C[0])} ${f(C[1])} A${r0} ${r0} 0 ${large} 0 ${f(D[0])} ${f(D[1])} Z`}
function paintMapInfo(node){const el=$("#mapinfo");if(!el||!node)return;const roots=(R&&R.map)||[];const rootish=!node.path||node.virtual||(roots.some(r=>r.path===node.path)&&!mapFocus);const cat=node.cat?pill(node.cat):"";el.innerHTML=`<h3>${esc(node.name||t("map.root"))}</h3><p class=s>${fmt(node.size||0)}</p>${cat}<p class=s>${esc(whyOf(node)||t("map.lead"))}</p>`+(node.path&&!rootish?`<div class=r><button class=btn id=mapopen>${esc(t("map.open"))}</button><button class=btn id=maptrash>${esc(t("map.trash"))}</button></div>`:`<p class=s>${esc(t("map.pick"))}</p>`);const o=$("#mapopen"),tr=$("#maptrash");if(o)o.onclick=()=>api("/api/reveal",{path:node.path});if(tr)tr.onclick=()=>trashPaths([node.path],tf("map.confirm",{name:node.name,why:whyOf(node)||""}))}
function drawMap(){const host=$("#mapdraw");if(!host)return;const node=currentMap();const kids=(node.children||[]).filter(c=>c.size>0);const info=()=>paintMapInfo(node);const back=$("#mback");if(back)back.disabled=!mapStack.length;if(!kids.length){host.innerHTML=`<p class=s>${esc(t("map.empty"))}</p>`;info();return}if(mapMode==="tree"){const W=640,H=420,rects=[];function split(nodes,x,y,w,h){if(!nodes.length||w<2||h<2)return;if(nodes.length===1){rects.push({n:nodes[0],x,y,w,h});return}const tot=nodes.reduce((s,n)=>s+n.size,0)||1;let i=0,acc=0;while(i<nodes.length-1&&acc+nodes[i].size<=tot*0.5){acc+=nodes[i].size;i++}if(i<1)i=1;acc=nodes.slice(0,i).reduce((s,n)=>s+n.size,0);const f=acc/tot;if(w>=h){split(nodes.slice(0,i),x,y,Math.max(1,w*f),h);split(nodes.slice(i),x+w*f,y,Math.max(1,w*(1-f)),h)}else{split(nodes.slice(0,i),x,y,w,Math.max(1,h*f));split(nodes.slice(i),x,y+h*f,w,Math.max(1,h*(1-f)))}}split(kids,6,6,W-12,H-12);let svg=`<svg viewBox="0 0 ${W} ${H}" role="img">`;rects.forEach(r=>{svg+=`<rect class=seg data-id="${esc(r.n.path)}" x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${Math.max(1,r.w-3).toFixed(1)}" height="${Math.max(1,r.h-3).toFixed(1)}" rx="8" fill="${col(r.n.cat)}"></rect>`});host.innerHTML=svg+`</svg>`;info();return}const W=640,H=420,cx=320,cy=210;let svg=`<svg viewBox="0 0 ${W} ${H}" role="img"><circle cx="${cx}" cy="${cy}" r="48" fill="${document.documentElement.dataset.th==="dark"?"#2A2A32":"#E7E1D6"}"/>`;const tot=kids.reduce((s,c)=>s+c.size,0)||1;let a=-Math.PI/2;kids.forEach(c=>{const span=Math.PI*2*(c.size/tot);const a1=a+span;svg+=`<path class=seg data-id="${esc(c.path)}" d="${arc(cx,cy,58,150,a,a1)}" fill="${col(c.cat)}"></path>`;a=a1});host.innerHTML=svg+`</svg>`;info()}
function mapHtml(){return `<section class=card><h2>${esc(t("nav.map"))}</h2><p class=s>${esc(t("map.lead"))}</p><div class=r><button type=button class="chip ${mapMode==="sun"?"on":""}" id=msun>${esc(t("map.sun"))}</button><button type=button class="chip ${mapMode==="tree"?"on":""}" id=mtree>${esc(t("map.tree"))}</button><button type=button class=btn id=mback ${mapStack.length?"":"disabled"}>${esc(t("map.back"))}</button></div><div class=maplay><div id=mapdraw></div><aside id=mapinfo></aside></div></section>`}
function render(){if(!R||!R.folders)return;const n={folders:R.folders.length,games:(R.games||R.folders.filter(x=>x.cat==="Gioco")).length,files:R.files.length,dups:R.dups.length,arch:R.archives.length};$("#nav").innerHTML=NAV.map(([k,key])=>`<button type=button class="nv ${k===tab?"on":""}" data-t="${k}">${esc(t(key))}${n[k]!=null&&k!=="home"&&k!=="map"?`<em>${n[k]}</em>`:""}</button>`).join("");let h="";if(tab==="home")h=home();else if(tab==="map")h=mapHtml();else if(tab==="games")h=gamesHtml();else{h=`<section class=card><h2>${esc(t(NAV.find(x=>x[0]===tab)[1]))}</h2><p class=s>${esc(t("intro."+tab))}</p><div class=r><input id=q placeholder="${esc(t("search"))}" value="${esc(q)}" style="flex:1 1 180px;min-width:0"><select id=so><option value=size ${sortk==="size"?"selected":""}>${esc(t("sort.size"))}</option><option value=name ${sortk==="name"?"selected":""}>${esc(t("sort.name"))}</option><option value=date ${sortk==="date"?"selected":""}>${esc(t("sort.date"))}</option></select>`;if(tab==="arch")h+=`<button class=btn id=selok>${esc(t("selok"))}</button>`;if(tab==="dups")h+=`<button class=btn id=keep>${esc(t("keep"))}</button>`;h+=`</div>`;if(tab==="folders"||tab==="files")h+=`<div class=r><button class="chip ${filt==="Tutti"?"on":""}" data-f="Tutti">${esc(t("cat.tutti"))}</button>`+CATS.map(c=>`<button class="chip ${c===filt?"on":""}" data-f="${esc(c)}">${esc(t(CK[c]))}</button>`).join("")+`</div>`;if(tab==="dups"){const G=R.dups.filter(g=>!q||g.paths.some(p=>p.toLowerCase().includes(q)));h+=`<p class=s>${esc(t("dups.hash"))} ${esc(tf("dups.lead",{size:fmt(R.wasted||0)}))}</p>`+(G.length?G.map(g=>`<div class=grp><b>${g.paths.length} × ${fmt(g.size)}</b> · ${fmt(g.wasted)}${g.paths.map(p=>`<div class=cp><input type=checkbox data-s="${esc(p)}" ${sel.has(p)?"checked":""}><span>${esc(p)}</span><button class=btn data-p="${esc(p)}">${esc(os("show"))}</button></div>`).join("")}</div>`).join(""):`<p class=s>${esc(t("empty.dups"))}</p>`)}else{const L=list(),mx=Math.max(1,...L.map(x=>x.size));h+=(L.length?L.map(x=>row(x,mx)).join(""):`<p class=s>${esc(t("empty.filters"))}</p>`)}h+=`</section>`}$("#again").hidden=false;showAppView("res");$("#view").innerHTML=h;if(tab==="map")drawMap();act();paintStatus()}
function act(){const a=$("#act");if(!sel.size){a.hidden=true;return}let s=0;sel.forEach(p=>s+=AM[p]?AM[p].size:(SZ[p]||0));a.hidden=false;a.innerHTML=`<span><b>${sel.size}</b> · <b>${fmt(s)}</b></span><button type=button class=btn id=clr>${esc(t("act.clear"))}</button><button type=button class=dng id=del2>${esc(t("act.trash"))}</button>`}
async function trashPaths(paths,body){if(!paths.length)return;if(!await ask(t("trash.ask.title"),body||tf("trash.ask.body",{n:paths.length}),t("trash.ask.ok")))return;toast(t("trash.working"),60000);const r=await api("/api/trash",{paths});if(r.error){toast(r.error);return}sel.clear();R=await api("/api/results");if(R&&R.folders){idx();render()}if(r.undo)toastUndo(tf("trash.result",{n:(r.done||[]).length,size:fmt(r.freed||0)}),r.undo);else toast(tf("trash.result",{n:(r.done||[]).length,size:fmt(r.freed||0)}))}
function trash(){const paths=[];sel.forEach(p=>{if(AM[p])AM[p].vols.forEach(v=>paths.push(v[0]));else paths.push(p)});trashPaths(paths)}
async function doUndo(id){const r=await api("/api/undo",{id});$("#toast").hidden=true;if(r&&r.ok)toast(tf("undo.ok",{n:(r.restored||[]).length}));else toast(t("settings.undo.manual"));if(!$("#histview").hidden)showHistory()}
function idx(){AM={};SZ={};(R.files||[]).forEach(f=>SZ[f.path]=f.size);(R.archives||[]).forEach(a=>AM[a.path]=a);(R.dups||[]).forEach(g=>g.paths.forEach(p=>SZ[p]=g.size))}
async function showSettings(){showAppView("setview");const box=$("#setview");box.innerHTML=`<section class=card><h2>${esc(t("settings.title"))}</h2><div class=setrow><div><b>${esc(t("settings.lang"))}</b><p>${esc(t("settings.lang.why"))}</p></div><select id=slang><option value=it ${LANG==="it"?"selected":""}>Italiano</option><option value=en ${LANG==="en"?"selected":""}>English</option></select></div><div class=setrow><div><b>${esc(t("settings.updates"))}</b><p>${esc(t("settings.updates.why"))}</p></div><input type=checkbox id=supd ${UPDATES?"checked":""}></div><div class=setrow><div><b>${esc(t("settings.schedule"))}</b><p>${esc(t("settings.schedule.why"))}</p></div><input type=checkbox id=ssc ${SCHED&&SCHED.enabled?"checked":""}></div><div class=setrow><div><b>${esc(t("settings.days"))}</b></div><input type=number id=sdays min=1 max=90 value="${(SCHED&&SCHED.days)||7}" style="width:88px"></div><div class=setrow><div><b>${esc(t("settings.account"))}</b><p>${esc(ME?ME.email:t("who.guest"))}</p></div>${ME?`<button class=btn id=sdel>${esc(t("settings.delete"))}</button>`:`<button class=btn id=slog>${esc(t("account"))}</button>`}</div></section>`;$("#slang").onchange=async()=>{const r=await api("/api/lang",{lang:$("#slang").value});if(r&&r.lang){LANG=r.lang;applyLang();paintAcct();hello();if(R&&!$("#res").hidden)render();if(!$("#setview").hidden)showSettings();if(!$("#histview").hidden)showHistory()}};$("#supd").onchange=async()=>{UPDATES=$("#supd").checked;await api("/api/settings",{updates:UPDATES});if(UPDATES)checkUpdates();else $("#upd").hidden=true};$("#ssc").onchange=async()=>{const on=$("#ssc").checked;const days=+$("#sdays").value||7;const r=await api("/api/settings",{schedule:on,schedule_days:days});if(r&&r.schedule)SCHED=r.schedule;showSchedule()};const slog=$("#slog");if(slog)slog.onclick=()=>showAuth("login");const sdel=$("#sdel");if(sdel)sdel.onclick=()=>deleteAccount()}
async function showHistory(){showAppView("histview");const hist=await api("/api/history");const items=Array.isArray(hist)?hist:[];$("#histview").innerHTML=`<section class=card><h2>${esc(t("settings.history"))}</h2>`+(items.length?items.map(x=>`<div class=hitem><p>${esc(x.summary||x.kind)}</p>${x.can_undo?`<button class=btn data-undo="${x.id}">${esc(t("settings.undo"))}</button>`:""}</div>`).join(""):`<p class=s>${esc(t("settings.history.empty"))}</p>`)+`</section>`;$("#histview").querySelectorAll("[data-undo]").forEach(b=>b.onclick=()=>doUndo(+b.dataset.undo))}
function deleteAccount(){const box=$("#setview");const keep=box.innerHTML;box.innerHTML=`<section class=card><h2>${esc(t("delete.title"))}</h2><p class=s>${esc(t("delete.body"))}</p><input type=password id=dpw placeholder="${esc(t("delete.pw"))}" maxlength=128 style="width:100%;margin-top:12px"><div id=de class=fe></div><div class=r><button class=btn id=dn>${esc(t("common.cancel"))}</button><button class=pri id=dy>${esc(t("delete.ok"))}</button></div></section>`;$("#dn").onclick=()=>{box.innerHTML=keep;showSettings()};$("#dy").onclick=async()=>{const r=await api("/api/delete_account",{password:$("#dpw").value});if(r.error){$("#de").textContent=r.error;return}stopPoll();ME=null;if(r.csrf)CSRF=r.csrf;paintAcct();toast(t("delete.done"));showSettings()}}
document.addEventListener("click",async e=>{const g=id=>e.target.closest(id);const am=g("[data-am]");if(am){e.preventDefault();return showAuth(am.dataset.am)}if(g("#guestbtn"))return enterApp();if(g("#gg")&&GOOGLE)googleGo();const p=g("[data-p]");if(p)api("/api/reveal",{path:p.dataset.p});const f=g("[data-f]");if(f){filt=f.dataset.f;render()}const tb=g("[data-t]");if(tb){tab=tb.dataset.t;q="";if(!R||!R.folders){showAppView("scan");return}render()}const o=g("[data-go]");if(o){tab=o.dataset.go;filt="Tutti";q="";render()}if(g("#clr")){sel.clear();render()}if(g("#del2"))trash();if(g("#selok")&&R){(R.archives||[]).filter(a=>a.level==="ok").forEach(a=>sel.add(a.path));render()}if(g("#keep")&&R){(R.dups||[]).forEach(d=>{const k=d.mt.indexOf(Math.min(...d.mt));d.paths.forEach((x,i)=>{if(i!==k)sel.add(x)})});render()}if(g("#msun")){mapMode="sun";drawMap()}if(g("#mtree")){mapMode="tree";drawMap()}if(g("#mback")){mapFocus=mapStack.pop()||"";drawMap()}const seg=g(".seg");if(seg&&seg.dataset.id){mapStack.push(mapFocus);mapFocus=seg.dataset.id;drawMap()}});
document.addEventListener("pointerover",e=>{const seg=e.target.closest&&e.target.closest(".seg");if(!seg||!R||tab!=="map")return;const n=findNode(seg.dataset.id,R.map||[]);if(n)paintMapInfo(n)});
document.addEventListener("change",e=>{if(e.target.dataset&&e.target.dataset.s){e.target.checked?sel.add(e.target.dataset.s):sel.delete(e.target.dataset.s);act()}if(e.target.id==="so"){sortk=e.target.value;render()}if(e.target.closest&&e.target.closest("#drv"))updatePick()});
document.addEventListener("input",e=>{if(e.target.id==="q"){q=e.target.value.toLowerCase();render()}});
$("#th").onclick=()=>{const h=document.documentElement,n=h.dataset.th==="dark"?"light":"dark";h.dataset.th=n;try{localStorage.setItem("tc_th",n)}catch(e){}if(tab==="map"&&R&&!$("#res").hidden)drawMap()};
$("#again").onclick=()=>{showAppView("scan");$("#again").hidden=!$("#res").hidden?$("#again").hidden:false;$("#again").hidden=true};
$("#acct").onclick=async()=>{if(!ME)return showAuth("login");const r=await api("/api/logout",{});stopPoll();ME=null;if(r.csrf)CSRF=r.csrf;paintAcct();toast(t("logout.done"));if(!$("#setview").hidden)showSettings()};
$("#quit").onclick=async()=>{if(await ask(t("close.ask.title"),t("close.ask.body"),t("close.ask.ok"))){await api("/api/quit",{});document.body.innerHTML='<main class=card style="margin:24px"><h2>'+esc(t("closed.title"))+'</h2><p class=s>'+esc(t("closed.body"))+'</p></main>'}};
$("#gear").onclick=()=>showSettings();
$("#histBtn").onclick=()=>showHistory();
$("#go").onclick=async()=>{if(running){await api("/api/stop",{});$("#go").textContent=t("stopping");return}const roots=[...document.querySelectorAll("#drv input:checked")].map(i=>i.value);const c=$("#custom").value.trim();if(c)roots.push(c);if(!roots.length)return toast(t("need.root"));const r=await api("/api/start",{roots,dups:$("#dups").checked,arch:$("#arch").checked,minmb:+$("#minmb").value||5});if(r.error)return toast(r.error);running=true;scanned=0;$("#go").textContent=t("stop");$("#prog").hidden=false;paintStatus();timer=setInterval(poll,600);poll()};
async function poll(){const s=await api("/api/status");if(!s||s.error)return;const steps=$("#steps");if(steps)steps.innerHTML=Object.keys(STEPK).map(k=>`<span class="st ${k===s.phase?"on":""}">${esc(t(STEPK[k]))}</span>`).join("");const b=$("#bar"),m=$("#msg");if((s.phase==="scan"||s.phase==="done")&&typeof s.count==="number")scanned=s.count;if(s.phase==="scan"){if(b)b.hidden=true;if(m)m.textContent=tf("scan.files",{n:(s.count||0).toLocaleString(loc()),p:s.current||""})}else if(s.phase==="agg"){if(m)m.textContent=t("scan.agg")}else if(s.phase==="dups"||s.phase==="arch"){if(b){b.hidden=false;if(b.firstChild)b.firstChild.style.width=(s.done/Math.max(1,s.total)*100)+"%"}if(m)m.textContent=tf("scan.checked",{d:(s.done||0).toLocaleString(loc()),t:(s.total||0).toLocaleString(loc())})}paintStatus();if(s.phase==="done"||s.phase==="idle"){stopPoll();if($("#go"))$("#go").textContent=t("go");if(s.error){$("#prog").hidden=true;toast(s.error);return}if(s.phase==="done"){R=await api("/api/results");sel.clear();tab="home";if(R&&R.folders){idx();render()}else $("#prog").hidden=true}else $("#prog").hidden=true}}
(async()=>{const m=await api("/api/me");CSRF=m.csrf||"";ME=m.user||null;GOOGLE=!!m.google;MAIL=!!m.mail;PLAT=(m.platform==="mac"||m.platform==="win")?m.platform:"linux";LANG=m.lang==="en"?"en":"it";UPDATES=!!m.updates;SCHED=m.schedule||{enabled:false,due:false,days:7};applyLang();const p=new URLSearchParams(location.search);if(location.pathname==="/reset"){RT=(p.get("token")||"").slice(0,100);history.replaceState(null,"","/")}else if(p.get("e")){const map={google_off:t("auth.google.off"),google_fail:t("google.fail"),rate:t("err.rate")};FLASH=map[p.get("e")]||null;history.replaceState(null,"","/")}let seen=false;try{seen=localStorage.getItem("tc_onboard")==="1"||localStorage.getItem("tc_intro")==="1"}catch(e){}if(SHOT&&SHOT!=="intro")seen=true;if(SHOT==="intro"||(!seen&&!m.onboarded&&!RT)){showPanel("intro");slide(0)}else if(RT||SHOT==="auth")showAuth(RT?"reset":"login");else enterApp()})();
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
            f"{APP} non si è avviato.\n\n"
            f"La porta {port} è già usata da una versione precedente del programma, ancora aperta su questo computer. "
            f"Se ne aprissi un'altra vedresti la schermata vecchia.\n\n"
            f"Chiudi quella copia (dalla barra delle applicazioni, oppure da Gestione attività su Windows "
            f"o Monitoraggio Attività su Mac) e riapri {APP}."
        ))
    give_up(1, (
        f"{APP} non si è avviato.\n\n"
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
                                       min_size=(800, 560), background_color="#F3EEE6")
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
    "Non riesco ad aprire la finestra di Twenties.\n\n"
    "Manca il componente di sistema (su Windows serve WebView2, già presente su Windows 11 e sulla maggior parte di Windows 10).\n\n"
    "Apro il programma nel browser."
)
FALLBACK_LOGO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#0B0C12"/><text x="32" y="44" text-anchor="middle" font-size="28" font-family="sans-serif" font-weight="700" fill="#fff">20</text></svg>'


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
    global SYSTEM_LANG
    SYSTEM_LANG = detect_lang()
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
