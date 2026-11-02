"""Prépare la version web : lit la fusion SRT, la compresse et la chiffre avec un mot de passe.

Usage :
    python construire_site.py H:\\FUSION_GLOBALE_SRT.txt
    python construire_site.py H:\\FUSION_GLOBALE_SRT.txt --liens liens.json

Le mot de passe est demandé au clavier (ou lu dans la variable RG_MOT_DE_PASSE).
Résultat : docs/donnees.bin (transcriptions) et docs/vignettes.bin (images des vidéos),
à publier avec le reste du dossier docs/.

Les images sont cherchées dans les sous-dossiers « année » (2005, 2006, …) du dossier
de la fusion, ou de celui donné par --images. Une image porte le même nom que la vidéo.
"""
import argparse
import datetime
import getpass
import gzip
import io
import json
import os
import re
import struct
import sys
import unicodedata

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from moteur import analyser_fusion, lire_fichier

# En-tête des fichiers : MAGIC | itérations (uint32) | sel (16 o) | nonce (12 o) | données chiffrées
# Les deux fichiers partagent le même sel, donc la même clé : un seul mot de passe pour les deux.
MAGIC = b"RGB1"
MAGIC_IMAGES = b"RGI1"
ITERATIONS = 600_000
EXTENSIONS_IMAGES = (".jpg", ".jpeg", ".png", ".webp")
LARGEUR_VIGNETTE = 320


def deriver(mot_de_passe, sel, iterations=ITERATIONS):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sel, iterations=iterations)
    return kdf.derive(mot_de_passe.encode("utf-8"))


def sel_reutilisable(chemin, mot_de_passe):
    # Même mot de passe que la base déjà publiée : on garde son sel pour que la clé mémorisée
    # par les navigateurs (« Se souvenir de moi ») reste valable après une mise à jour.
    try:
        with open(chemin, "rb") as f:
            d = f.read()
        if d[:4] != MAGIC or struct.unpack(">I", d[4:8])[0] != ITERATIONS:
            return None
        sel, nonce = d[8:24], d[24:36]
        AESGCM(deriver(mot_de_passe, sel)).decrypt(nonce, d[36:], MAGIC)
        return sel
    except Exception:
        return None


def chiffrer(donnees, cle, sel, magic=MAGIC):
    nonce = os.urandom(12)
    return magic + struct.pack(">I", ITERATIONS) + sel + nonce + AESGCM(cle).encrypt(nonce, donnees, magic)


def cle_nom(nom):
    # Rapproche « Titre.fr.fr » / « Titre.fr » / « Titre  (720p) » / accents différents d'un même nom.
    nom = re.sub(r"(\.[a-z]{2,3})+$", "", nom)
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", nom)


def trouver_images(racine):
    images = {}
    for annee in sorted(os.listdir(racine)) if os.path.isdir(racine) else []:
        dossier = os.path.join(racine, annee)
        if not (re.fullmatch(r"\d{4}", annee) and os.path.isdir(dossier)):
            continue
        for chemin, _, fichiers in os.walk(dossier):
            for f in sorted(fichiers):
                nom, ext = os.path.splitext(f)
                if ext.lower() in EXTENSIONS_IMAGES:
                    images.setdefault(cle_nom(nom), os.path.join(chemin, f))
    return images


def faire_vignette(chemin):
    from PIL import Image
    with Image.open(chemin) as img:
        img = img.convert("RGB")
        img.thumbnail((LARGEUR_VIGNETTE, LARGEUR_VIGNETTE))
        sortie = io.BytesIO()
        img.save(sortie, "WEBP", quality=60, method=6)
        return sortie.getvalue()


def paquet_vignettes(videos, racine):
    """[longueur de l'index (uint32)] [index JSON {titre: [début, longueur]}] [images WebP à la suite]"""
    images = trouver_images(racine)
    index, blobs, pos = {}, [], 0
    for v in videos:
        chemin = images.get(cle_nom(v["titre"]))
        if not chemin:
            continue
        try:
            octets = faire_vignette(chemin)
        except Exception as e:
            print(f"  Image ignorée ({e}) : {chemin}")
            continue
        index[v["titre"]] = [pos, len(octets)]
        blobs.append(octets)
        pos += len(octets)
    entete = json.dumps({"type": "image/webp", "images": index}, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(entete)) + entete + b"".join(blobs), len(index)


def demander_mot_de_passe():
    mdp = os.environ.get("RG_MOT_DE_PASSE")
    if mdp:
        return mdp
    while True:
        mdp = getpass.getpass("Mot de passe du site (8 caractères minimum) : ")
        if len(mdp) < 8:
            print("Trop court.")
        elif mdp != getpass.getpass("Retapez le mot de passe : "):
            print("Les deux saisies sont différentes.")
        else:
            return mdp


def main():
    ap = argparse.ArgumentParser(description="Prépare docs/donnees.bin (base chiffrée) pour la version web.")
    ap.add_argument("fusion", help="chemin de FUSION_GLOBALE_SRT.txt")
    ap.add_argument("--liens", help="fichier liens.json (titre -> adresse de la vidéo)")
    ap.add_argument("--images", help="dossier contenant les sous-dossiers année (par défaut : celui de la fusion)")
    ap.add_argument("--sans-images", action="store_true", help="ne pas publier les images des vidéos")
    ap.add_argument("--sortie", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "donnees.bin"))
    args = ap.parse_args()
    sortie_images = os.path.join(os.path.dirname(args.sortie), "vignettes.bin")

    print("Lecture de la fusion...")
    videos = analyser_fusion(lire_fichier(args.fusion))
    liens = {}
    if args.liens:
        with open(args.liens, "r", encoding="utf-8") as f:
            liens = {k: v for k, v in json.load(f).items()
                     if isinstance(v, str) and v.startswith(("https://", "http://"))}

    paquet = {
        "genere": datetime.date.today().isoformat(),
        "liens": liens,
        # [titre, année, [[minutage HH:MM:SS, texte], …]]
        "videos": [[v["titre"], v["annee"], [[b["temps"].split(",")[0], b["texte"]] for b in v["blocs"]]]
                   for v in videos],
    }
    brut = json.dumps(paquet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compresse = gzip.compress(brut, compresslevel=9)

    mdp = demander_mot_de_passe()
    print("Chiffrement...")
    sel = sel_reutilisable(args.sortie, mdp)
    if os.path.exists(args.sortie):
        print("Même mot de passe : les visiteurs restent connectés." if sel
              else "Nouveau mot de passe : chaque visiteur devra saisir le nouveau.")
    sel = sel or os.urandom(16)
    cle = deriver(mdp, sel)
    os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
    with open(args.sortie, "wb") as f:
        f.write(chiffrer(compresse, cle, sel))

    nb = sum(len(v["blocs"]) for v in videos)
    print(f"OK : {len(videos)} vidéos, {nb} phrases, {len(liens)} liens")
    print(f"{args.sortie} : {os.path.getsize(args.sortie) / 1e6:.1f} Mo")

    if args.sans_images:
        if os.path.exists(sortie_images):
            os.remove(sortie_images)
        return
    print("Préparation des images...")
    racine = args.images or os.path.dirname(os.path.abspath(args.fusion))
    contenu, nb_images = paquet_vignettes(videos, racine)
    with open(sortie_images, "wb") as f:
        f.write(chiffrer(contenu, cle, sel, MAGIC_IMAGES))
    print(f"OK : {nb_images} images sur {len(videos)} vidéos")
    print(f"{sortie_images} : {os.path.getsize(sortie_images) / 1e6:.1f} Mo")


if __name__ == "__main__":
    sys.exit(main())
