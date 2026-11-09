#!/usr/bin/env python3
"""Zündfunke: Hilfsprogramm für den Mac.

Liefert die App unter http://localhost:8765 aus und liest/schreibt die drei
Datendateien (eintraege.csv, service.csv, wartungsplan.csv) direkt im Ordner
Daten/ des PKM. Nur Python 3 (Standardbibliothek), keine Installation nötig.

Protokoll: jede Speicherung wird in Daten/.app-protokoll vermerkt (Zeit, Datei,
Prüfsumme vorher/nachher, Zeilenzahl, neu/entfernt).

Sicherheit: lauscht nur auf 127.0.0.1, akzeptiert nur die Host-Namen localhost
und 127.0.0.1, schreibt ausschließlich die drei Dateinamen, prüft Origin und
einen eigenen Header, sichert die Datei vor dem Überschreiben und schreibt
atomar (Temp-Datei, dann Umbenennen).

Ordner: Standard ist ../Daten relativ zu diesem Skript (liegt es unter
Projects/Youngtimer/App/, ist das Projects/Youngtimer/Daten). Abweichend:
Umgebungsvariable ZF_DATA. Port: ZF_PORT (Standard 8765).
"""
import csv, hashlib, http.server, io, json, mimetypes, os, pathlib, shutil, socketserver, sys, threading, time

HERE = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get("ZF_DATA") or (HERE.parent / "Daten")).resolve()
PORT = int(os.environ.get("ZF_PORT", "8765"))
NAMES = {
    "eintraege": "id,fahrzeug,datum,",
    "service": "fahrzeug,gruppe,aufgabe,km,",
    "wartungsplan": "fahrzeug,gruppe,aufgabe,intervall_km,",
}
BACKUP_DIR = DATA / "Backup-App"
PROTOKOLL = DATA / ".app-protokoll"
PROTOKOLL_KOPF = "zeit,datei,md5_vorher,md5_nachher,zeilen_vorher,zeilen_nachher,neu,entfernt,quelle"
BACKUP_EVERY = 3600      # höchstens ein Backup pro Datei und Stunde
BACKUP_KEEP = 30         # so viele Backups je Datei bleiben liegen
MAX_BYTES = 20 * 1024 * 1024
LOCK = threading.Lock()
STATIC_OK = {"index.html", "sw.js", "manifest.webmanifest"}


def md5(b):
    return hashlib.md5(b).hexdigest()


def path_of(name):
    return DATA / (name + ".csv")


def file_info(name):
    p = path_of(name)
    if not p.is_file():
        return {"exists": False}
    b = p.read_bytes()
    return {"exists": True, "bytes": len(b), "mtime": int(p.stat().st_mtime), "etag": md5(b)}


def write_sums():
    lines = []
    for n in NAMES:
        p = path_of(n)
        if p.is_file():
            lines.append("%s  %s.csv" % (md5(p.read_bytes()), n))
    tmp = DATA / ".pruefsummen.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, DATA / ".pruefsummen")


def backup(name):
    p = path_of(name)
    if not p.is_file():
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    mine = sorted(BACKUP_DIR.glob(name + "-*.csv"))
    if mine and time.time() - mine[-1].stat().st_mtime < BACKUP_EVERY:
        return
    shutil.copy2(p, BACKUP_DIR / ("%s-%s.csv" % (name, time.strftime("%Y%m%d-%H%M%S"))))
    mine = sorted(BACKUP_DIR.glob(name + "-*.csv"))
    for old in mine[:-BACKUP_KEEP]:
        old.unlink()


def rows_of(b):
    try:
        text = b.decode("utf-8-sig")
        return [tuple(r) for r in csv.reader(io.StringIO(text, newline=""))][1:]
    except Exception:
        return None


def protokoll(name, old_bytes, new_bytes):
    """Hängt eine Zeile an .app-protokoll an: Wer hat wann was geschrieben.
    Der Abgleich kann damit prüfen, ob der Stand in .pruefsummen von der App stammt.
    Ein Fehler hier darf das Speichern nie verhindern."""
    try:
        a = rows_of(old_bytes) if old_bytes is not None else []
        b = rows_of(new_bytes)
        if a is None or b is None:
            n_neu = n_weg = n_a = n_b = -1
        else:
            sa, sb = set(a), set(b)
            n_a, n_b = len(a), len(b)
            n_neu, n_weg = len(sb - sa), len(sa - sb)
        line = ",".join([time.strftime("%Y-%m-%dT%H:%M:%S%z"), name + ".csv",
                         md5(old_bytes) if old_bytes is not None else "none", md5(new_bytes),
                         str(n_a), str(n_b), str(n_neu), str(n_weg), "app"])
        new_file = not PROTOKOLL.is_file()
        with open(PROTOKOLL, "a", encoding="utf-8", newline="") as f:
            if new_file:
                f.write(PROTOKOLL_KOPF + "\n")
            f.write(line + "\n")
    except Exception as e:
        sys.stderr.write("Protokoll nicht geschrieben: %s\n" % e)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "Zuendfunke"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s  %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # --- Hilfen ---
    def send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, code, obj, extra=None):
        self.send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8", extra)

    def host_ok(self):
        return (self.headers.get("Host") or "") in ("localhost:%d" % PORT, "127.0.0.1:%d" % PORT)

    def origin_ok(self):
        o = self.headers.get("Origin")
        return o is None or o in ("http://localhost:%d" % PORT, "http://127.0.0.1:%d" % PORT)

    # --- GET ---
    def do_GET(self):
        if not self.host_ok():
            return self.send(403, b"Host nicht erlaubt")
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            return self.json(200, {"app": "zuendfunke-pkm", "version": 1, "dir": str(DATA),
                                   "files": {n: file_info(n) for n in NAMES}})
        if path.startswith("/api/daten/") and path.endswith(".csv"):
            name = path[len("/api/daten/"):-4]
            if name not in NAMES:
                return self.send(404, b"unbekannt")
            p = path_of(name)
            if not p.is_file():
                return self.send(404, b"fehlt")
            b = p.read_bytes()
            return self.send(200, b, "text/csv; charset=utf-8", {"ETag": '"%s"' % md5(b)})
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/")
        if rel in STATIC_OK or (rel.startswith("icons/") and "/" not in rel[6:] and ".." not in rel):
            f = HERE / rel
            if f.is_file():
                ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                if rel.endswith(".webmanifest"):
                    ctype = "application/manifest+json"
                if ctype.startswith("text/") or ctype in ("application/javascript", "application/manifest+json"):
                    ctype += "; charset=utf-8"
                return self.send(200, f.read_bytes(), ctype)
        return self.send(404, b"nicht gefunden")

    do_HEAD = do_GET

    # --- PUT ---
    def do_PUT(self):
        if not self.host_ok() or not self.origin_ok() or self.headers.get("X-Zuendfunke") != "1":
            return self.send(403, b"nicht erlaubt")
        path = self.path.split("?", 1)[0]
        if not (path.startswith("/api/daten/") and path.endswith(".csv")):
            return self.send(404, b"unbekannt")
        name = path[len("/api/daten/"):-4]
        if name not in NAMES:
            return self.send(404, b"unbekannt")
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = -1
        if n <= 0 or n > MAX_BYTES:
            return self.send(400, b"Inhalt fehlt oder zu gross")
        body = self.rfile.read(n)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return self.send(400, b"kein UTF-8")
        if not text.startswith(NAMES[name]):
            return self.send(400, "Kopfzeile passt nicht zu {}.csv".format(name).encode("utf-8"))
        want = (self.headers.get("If-Match") or "").strip('"')
        with LOCK:
            p = path_of(name)
            old = p.read_bytes() if p.is_file() else None
            cur = md5(old) if old is not None else "none"
            if want != cur:
                return self.json(409, {"fehler": "Datei wurde zwischenzeitlich geändert", "etag": cur})
            DATA.mkdir(parents=True, exist_ok=True)
            backup(name)
            tmp = DATA / ("." + name + ".tmp")
            tmp.write_bytes(body)
            os.replace(tmp, p)
            write_sums()
            protokoll(name, old, body)
        return self.json(200, {"ok": True, "etag": md5(body)}, {"ETag": '"%s"' % md5(body)})

    def do_OPTIONS(self):
        return self.send(405, b"kein CORS")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if not DATA.is_dir():
        sys.exit("Datenordner nicht gefunden: %s\nTipp: Das Skript gehört in Projects/Youngtimer/App/ (neben den Ordner Daten) oder ZF_DATA setzen." % DATA)
    if not (HERE / "index.html").is_file():
        sys.exit("index.html fehlt neben server.py: %s" % HERE)
    try:
        srv = Server(("127.0.0.1", PORT), Handler)
    except OSError as e:
        sys.exit("Port %d ist belegt (%s). Läuft Zündfunke schon? Dann einfach http://localhost:%d öffnen." % (PORT, e, PORT))
    print("Zündfunke läuft: http://localhost:%d" % PORT)
    print("Daten: %s" % DATA)
    print("Beenden mit Strg+C oder Fenster schließen.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
