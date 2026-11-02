# 🔎 Recherche Globale

Recherchez un mot ou une expression dans des centaines de transcriptions de vidéos (fichiers de sous-titres SRT fusionnés), et retrouvez instantanément **la vidéo et le minutage exact** où il est prononcé.

- Fonctionne sous **Windows, macOS et Linux**, sans installation.
- Tout reste sur votre ordinateur : aucune donnée n'est envoyée sur Internet.
- Recherche insensible aux majuscules et (au choix) aux accents : `priere` trouve « Prière ».
- Plusieurs termes à la fois, séparés par des virgules : `coran, bible`.
- Filtre par année, option « mot entier », contexte de deux phrases avant et après chaque passage.
- Bouton **▶ Voir** qui ouvre la vidéo en ligne au bon moment (si un fichier de liens est fourni).

Deux façons de l'utiliser :

- **Version web, protégée par mot de passe** (recommandée) : on ouvre un lien, on tape le mot de passe, on cherche. Rien à installer.
- **Logiciel à télécharger** : fonctionne hors connexion, avec votre propre fichier de transcriptions.

## Version web protégée par mot de passe

Les transcriptions sont **chiffrées** (AES-256) avant d'être mises en ligne : le fichier publié `docs/donnees.bin` est illisible sans le mot de passe. Le déchiffrement se fait uniquement dans le navigateur du visiteur ; le mot de passe ne circule jamais sur Internet.

### Pour les visiteurs

Cliquer sur le lien reçu : la recherche s'ouvre directement, rien à taper. L'ordinateur s'en souvient pour les visites suivantes.

### Le lien à partager

Le mot de passe est intégré au lien, après `#cle=` :

```
https://<compte>.github.io/<depot>/#cle=<mot-de-passe>
```

La partie après `#` n'est jamais envoyée au serveur : seul le navigateur du visiteur la lit, l'utilise pour déchiffrer, puis l'efface de la barre d'adresse. Sans cette partie, la page demande le mot de passe (écran « Accès réservé »).

La première visite télécharge la base (environ 13 Mo, quelques secondes en fibre ou en ADSL) ; le navigateur la garde ensuite.

### Pour l'administrateur

**Mettre la base en ligne ou à jour** — depuis ce dossier, avec Python et la bibliothèque `cryptography` (`pip install -r requirements-site.txt`) :

```
python construire_site.py H:\FUSION_GLOBALE_SRT.txt
```

ou, avec les liens vers les vidéos :

```
python construire_site.py H:\FUSION_GLOBALE_SRT.txt --liens liens.json
```

Le script demande le mot de passe (deux fois) et crée `docs/donnees.bin` (transcriptions) et `docs/vignettes.bin` (images des vidéos, chiffrées avec le même mot de passe). Il reste à les envoyer sur GitHub (`git add docs` puis `git commit` et `git push`) ; le site est à jour une à deux minutes plus tard.

**Images des vidéos** : le script cherche, dans les sous-dossiers année (`2019`, `2020`…) du dossier de la fusion, une image (`.jpg`, `.png`, `.webp`) portant le même nom que la vidéo, la réduit en vignette et l'affiche à droite des résultats. Autre emplacement : `--images D:\MesVideos`. Pour ne publier aucune image : `--sans-images`.

- **Même mot de passe que la fois précédente** : les visiteurs qui ont coché « Se souvenir de moi » restent connectés.
- **Nouveau mot de passe** : l'ancien lien cesse de fonctionner ; envoyez le nouveau lien aux personnes autorisées. C'est la marche à suivre si l'ancien a circulé trop largement.

**Activer le site (une seule fois)** — sur GitHub, dans le dépôt : **Settings → Pages → Branch : `main`, dossier `/docs` → Save**. L'adresse du site s'affiche sur cette même page.

**Limites à connaître** : tous les visiteurs partagent le même lien ; une personne autorisée peut le transmettre à d'autres, ou copier ce qu'elle voit à l'écran. Le code du site, lui, est public (seules les transcriptions sont protégées).

## Logiciel à télécharger

### Télécharger

Rendez-vous dans l'onglet **[Releases](../../releases)** et téléchargez l'archive de votre système :

| Système | Fichier |
|---|---|
| Windows | `RechercheGlobale-Windows.zip` |
| macOS | `RechercheGlobale-macOS.zip` |
| Linux | `RechercheGlobale-Linux.zip` |

Téléchargez aussi la base de transcriptions **`FUSION_GLOBALE_SRT.txt`** (et `liens.json` s'il est proposé) depuis la même page.

### Utilisation

1. Décompressez l'archive dans un dossier.
2. Placez `FUSION_GLOBALE_SRT.txt` (et `liens.json`) **dans ce même dossier**.
3. Lancez le programme :
   - **Windows** : double-cliquez sur `RechercheGlobale.exe`. Si Windows SmartScreen s'affiche, cliquez sur « Informations complémentaires » puis « Exécuter quand même ».
   - **macOS** : le programme n'est pas signé par Apple. La première fois, faites un clic droit sur `RechercheGlobale` → **Ouvrir**, puis confirmez. Si macOS refuse encore, dans le Terminal :
     ```
     xattr -d com.apple.quarantine RechercheGlobale
     ```
   - **Linux** : dans un terminal, depuis le dossier :
     ```
     chmod +x RechercheGlobale
     ./RechercheGlobale
     ```
4. Votre navigateur s'ouvre sur la page de recherche. Une petite fenêtre noire reste ouverte : c'est le programme. **Fermez-la pour quitter.**

Si la base n'est pas à côté du programme, la page vous demande son chemin ; il est ensuite mémorisé. Vous pouvez aussi le donner au lancement :

```
RechercheGlobale  /chemin/vers/FUSION_GLOBALE_SRT.txt
```

**Images des vidéos** : si le dossier de la fusion contient des sous-dossiers année (`2019`, `2020`…) avec, pour chaque vidéo, une image du même nom (`.jpg`, `.png`, `.webp`), elle s'affiche à droite des résultats. Autre emplacement : `--images D:\MesVideos`.

Options : `--port 8765` pour choisir le port, `--sans-navigateur` pour ne pas ouvrir le navigateur automatiquement, `--images` pour le dossier des images.

Astuce : une recherche peut être ouverte directement par son adresse, par exemple `http://127.0.0.1:8765/?q=messie`.

## Format des fichiers

### `FUSION_GLOBALE_SRT.txt`

Une suite de fichiers SRT, chacun précédé d'une ligne d'en-tête portant son nom :

```
=== FICHIER SOURCE : 20190322 - Titre de la vidéo.srt ===
1
00:00:01,750 --> 00:00:05,990
Texte de la première phrase.

2
00:00:05,990 --> 00:00:13,070
Texte de la phrase suivante.
```

L'année affichée est lue dans les 4 premiers chiffres du nom (`2019…`). Un exemple complet se trouve dans [`exemple/FUSION_EXEMPLE.txt`](exemple/FUSION_EXEMPLE.txt).

### `liens.json` (facultatif)

Associe chaque titre (nom du fichier SRT sans `.srt`) à l'adresse de la vidéo en ligne. Le minutage est ajouté automatiquement au lien (`?t=secondes`), ce qui fonctionne avec YouTube et Odysee.

```json
{
  "20190322 - Titre de la vidéo": "https://www.youtube.com/watch?v=XXXXXXXXXXX"
}
```

Voir [`exemple/liens.exemple.json`](exemple/liens.exemple.json).

## Pour les développeurs

Aucune dépendance : Python 3.10 ou plus récent suffit.

```
python recherche_globale.py exemple/FUSION_EXEMPLE.txt
python -m unittest discover -s tests -v
```

| Fichier | Rôle |
|---|---|
| `moteur.py` | Lecture de la fusion SRT et recherche |
| `recherche_globale.py` | Serveur local (127.0.0.1 uniquement) et lancement du navigateur |
| `web/index.html` | Interface de recherche |
| `recherche_globale.spec` | Configuration de compilation PyInstaller |

### Compiler un exécutable

```
python -m pip install -r requirements-build.txt
pyinstaller recherche_globale.spec
```

L'exécutable est créé dans `dist/`. PyInstaller ne compile que pour le système sur lequel il tourne.

### Publier une nouvelle version

Les trois versions (Windows, macOS, Linux) sont compilées automatiquement par GitHub Actions. Il suffit de créer un tag :

```
git tag v1.0.0
git push origin v1.0.0
```

Les archives apparaissent ensuite dans **Releases**. Ajoutez-y à la main `FUSION_GLOBALE_SRT.txt` (et `liens.json`) comme fichiers joints de la version.

## Licence

Code sous licence [MIT](LICENSE). Les transcriptions distribuées avec le logiciel restent la propriété de leurs auteurs.
