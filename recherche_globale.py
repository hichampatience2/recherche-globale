"""Recherche Globale — recherche dans une fusion de sous-titres SRT, interface dans le navigateur."""
import argparse
import json
import os
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from moteur import Index, cle_nom, trouver_images

VERSION = "1.2.0"
NOM_FUSION = "FUSION_GLOBALE_SRT.txt"
NOM_LIENS = "liens.json"
TYPES_IMAGES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
CONFIG = os.path.join(os.path.expanduser("~"), ".recherche_globale.json")


def dossier_appli():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ressource(nom):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nom)


def lire_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire_config(cfg):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def trouver_fusion(chemin_arg):
    candidats = [chemin_arg,
                 os.path.join(dossier_appli(), NOM_FUSION),
                 os.path.join(os.getcwd(), NOM_FUSION),
                 lire_config().get("fichier")]
    for c in candidats:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


class Etat:
    def __init__(self):
        self.index = None
        self.fichier = None
        self.liens = {}
        self.images = {}          # titre -> chemin de l'image de la vidéo
        self.dossier_images = None
        self.chargement = False
        self.erreur = None
        self.verrou = threading.Lock()

    def charger(self, chemin):
        with self.verrou:
            self.chargement, self.erreur = True, None
        try:
            index = Index.depuis_fichier(chemin)
            liens = {}
            for d in (os.path.dirname(chemin), dossier_appli()):
                p = os.path.join(d, NOM_LIENS)
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        liens = json.load(f)
                    break
            trouvees = trouver_images(self.dossier_images or os.path.dirname(chemin))
            images = {v["titre"]: trouvees[cle_nom(v["titre"])] for v in index.videos
                      if cle_nom(v["titre"]) in trouvees}
            with self.verrou:
                self.index, self.fichier, self.liens, self.images = index, chemin, liens, images
            cfg = lire_config()
            cfg["fichier"] = chemin
            ecrire_config(cfg)
        except Exception as e:
            with self.verrou:
                self.erreur = f"Impossible de lire le fichier : {e}"
        finally:
            with self.verrou:
                self.chargement = False

    def resume(self):
        with self.verrou:
            idx = self.index
            return {
                "version": VERSION,
                "chargement": self.chargement,
                "erreur": self.erreur,
                "fichier": self.fichier,
                "videos": len(idx.videos) if idx else 0,
                "phrases": idx.nb_blocs() if idx else 0,
                "annees": idx.annees() if idx else [],
                "liens": len(self.liens),
                "images": len(self.images),
            }


ETAT = Etat()


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, data, code=200):
        corps = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _lire_json(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _origine_ok(self):
        # Bloque les sites tiers (CSRF) et le DNS rebinding : seule notre page peut appeler l'API.
        port = self.server.server_address[1]
        hotes = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in hotes:
            return False
        origine = self.headers.get("Origin")
        return origine is None or origine.split("//", 1)[-1] in hotes

    def do_GET(self):
        if not self._origine_ok():
            return self._json({"erreur": "Accès refusé."}, 403)
        chemin = urlsplit(self.path).path
        if chemin in ("/", "/index.html"):
            with open(ressource(os.path.join("web", "index.html")), "rb") as f:
                corps = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
        elif chemin == "/api/etat":
            self._json(ETAT.resume())
        elif chemin == "/api/image":
            self._image(parse_qs(urlsplit(self.path).query).get("t", [""])[0])
        else:
            self._json({"erreur": "Introuvable"}, 404)

    def _image(self, titre):
        # Seules les images associées à une vidéo de la base sont servies : aucun autre fichier du disque.
        chemin = ETAT.images.get(titre)
        if not chemin:
            return self._json({"erreur": "Introuvable"}, 404)
        try:
            with open(chemin, "rb") as f:
                corps = f.read()
        except OSError:
            return self._json({"erreur": "Introuvable"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", TYPES_IMAGES.get(os.path.splitext(chemin)[1].lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        if not self._origine_ok():
            return self._json({"erreur": "Accès refusé."}, 403)
        data = self._lire_json()
        chemin_url = urlsplit(self.path).path
        if chemin_url == "/api/charger":
            chemin = os.path.expanduser(str(data.get("chemin", "")).strip().strip('"'))
            if not os.path.isfile(chemin):
                return self._json({"erreur": "Fichier introuvable."}, 400)
            threading.Thread(target=ETAT.charger, args=(os.path.abspath(chemin),), daemon=True).start()
            return self._json({"ok": True})
        if chemin_url == "/api/transcription":
            idx = ETAT.index
            blocs = idx.transcription(str(data.get("titre", ""))) if idx else None
            if blocs is None:
                return self._json({"erreur": "Vidéo introuvable."}, 404)
            return self._json({"blocs": blocs})
        if chemin_url == "/api/recherche":
            idx = ETAT.index
            if idx is None:
                return self._json({"erreur": "Aucune base chargée."}, 400)
            termes = str(data.get("termes", "")).split(",")
            try:
                limite = max(1, min(int(data.get("limite", 300)), 2000))
            except (TypeError, ValueError):
                limite = 300
            res = idx.rechercher(termes, annees=data.get("annees") or None,
                                 mot_entier=bool(data.get("mot_entier")),
                                 ignorer_accents=data.get("ignorer_accents", True) is not False,
                                 limite=limite)
            for r in res["resultats"]:
                lien = ETAT.liens.get(r["titre"])
                r["lien"] = lien if isinstance(lien, str) and lien.startswith(("https://", "http://")) else None
                r["image"] = r["titre"] in ETAT.images
            return self._json(res)
        self._json({"erreur": "Introuvable"}, 404)


def port_libre(depart):
    for p in range(depart, depart + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("Aucun port libre.")


def main():
    ap = argparse.ArgumentParser(description="Recherche Globale dans une fusion de sous-titres SRT.")
    ap.add_argument("fichier", nargs="?", help=f"chemin du fichier de fusion (par défaut : {NOM_FUSION})")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur")
    ap.add_argument("--images", help="dossier contenant les sous-dossiers année avec les images des vidéos "
                                     "(par défaut : celui du fichier de fusion)")
    args = ap.parse_args()
    ETAT.dossier_images = args.images

    chemin = trouver_fusion(args.fichier)
    if chemin:
        threading.Thread(target=ETAT.charger, args=(chemin,), daemon=True).start()

    port = port_libre(args.port)
    url = f"http://127.0.0.1:{port}/"
    serveur = ThreadingHTTPServer(("127.0.0.1", port), Gestionnaire)
    print(f"Recherche Globale {VERSION} — {url}")
    print("Fermez cette fenêtre (ou Ctrl+C) pour quitter.")
    if not args.sans_navigateur:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
