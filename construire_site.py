"""Prépare la version web : lit la fusion SRT, la compresse et la chiffre avec un mot de passe.

Usage :
    python construire_site.py H:\\FUSION_GLOBALE_SRT.txt
    python construire_site.py H:\\FUSION_GLOBALE_SRT.txt --liens liens.json

Le mot de passe est demandé au clavier (ou lu dans la variable RG_MOT_DE_PASSE).
Résultat : docs/donnees.bin, à publier avec le reste du dossier docs/.
"""
import argparse
import datetime
import getpass
import gzip
import json
import os
import struct
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from moteur import analyser_fusion, lire_fichier

# En-tête du fichier : MAGIC | itérations (uint32) | sel (16 o) | nonce (12 o) | données chiffrées
MAGIC = b"RGB1"
ITERATIONS = 600_000


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


def chiffrer(donnees, mot_de_passe, sel=None):
    sel = sel or os.urandom(16)
    nonce = os.urandom(12)
    cle = deriver(mot_de_passe, sel)
    return MAGIC + struct.pack(">I", ITERATIONS) + sel + nonce + AESGCM(cle).encrypt(nonce, donnees, MAGIC)


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
    ap.add_argument("--sortie", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "donnees.bin"))
    args = ap.parse_args()

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
    os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
    with open(args.sortie, "wb") as f:
        f.write(chiffrer(compresse, mdp, sel))

    nb = sum(len(v["blocs"]) for v in videos)
    print(f"OK : {len(videos)} vidéos, {nb} phrases, {len(liens)} liens")
    print(f"{args.sortie} : {os.path.getsize(args.sortie) / 1e6:.1f} Mo")


if __name__ == "__main__":
    sys.exit(main())
