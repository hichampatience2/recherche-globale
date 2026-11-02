"""Lecture du fichier de fusion SRT et recherche plein texte."""
import re
import unicodedata
from bisect import bisect_right

MARQUEUR = "=== FICHIER SOURCE : "
BRUIT = re.compile(r"\(Transcrit par TurboScribe\.ai\.[^)]*\)\s*")


class _SansAccents(dict):
    # Table pour str.translate : chaque caractère accentué -> sa lettre de base (1 pour 1).
    def __missing__(self, code):
        c = chr(code)
        base = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
        self[code] = base if len(base) == 1 else c
        return self[code]


_TABLE = _SansAccents()


def normaliser(texte, ignorer_accents=True):
    # La longueur est conservée pour que les positions trouvées servent au surlignage du texte original.
    bas = texte.lower()
    if len(bas) != len(texte):
        bas = "".join(c.lower() if len(c.lower()) == 1 else c for c in texte)
    return bas.translate(_TABLE) if ignorer_accents else bas


def lire_fichier(chemin):
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(chemin, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Encodage illisible : {chemin}")


def analyser_fusion(contenu):
    """Retourne une liste de vidéos : {titre, annee, blocs:[{temps, texte}]}."""
    videos = []
    for morceau in contenu.split(MARQUEUR):
        if not morceau.strip():
            continue
        entete, _, corps = morceau.partition("\n")
        nom = entete.strip().rstrip("=").strip()
        if not corps:
            continue
        titre = nom[:-4] if nom.lower().endswith(".srt") else nom
        m = re.match(r"^(\d{4})", titre)
        blocs = []
        for b in re.split(r"\n\s*\n", corps.replace("\r\n", "\n").strip()):
            lignes = b.strip().split("\n")
            if len(lignes) >= 3 and "-->" in lignes[1]:
                texte = BRUIT.sub("", " ".join(lignes[2:])).strip()
                if texte:
                    blocs.append({"temps": lignes[1].split("-->")[0].strip(), "texte": texte})
        if blocs:
            videos.append({"titre": titre, "annee": m.group(1) if m else "Autres", "blocs": blocs})
    return videos


def _fusionner(spans):
    res = []
    for d, f in spans:
        if res and d <= res[-1][1]:
            res[-1][1] = max(res[-1][1], f)
        else:
            res.append([d, f])
    return res


class Index:
    def __init__(self, videos):
        self.videos = videos
        # Tout le corpus en une seule chaîne (une phrase par ligne) : une recherche = une passe regex.
        self._refs, self._debuts = [], []
        textes, pos = [], 0
        for vi, v in enumerate(videos):
            for bi, b in enumerate(v["blocs"]):
                self._refs.append((vi, bi))
                self._debuts.append(pos)
                textes.append(b["texte"])
                pos += len(b["texte"]) + 1
        brut = "\n".join(textes)
        self._corpus = {False: normaliser(brut, ignorer_accents=False)}
        self._corpus[True] = self._corpus[False].translate(_TABLE)

    @classmethod
    def depuis_fichier(cls, chemin):
        return cls(analyser_fusion(lire_fichier(chemin)))

    def annees(self):
        return sorted({v["annee"] for v in self.videos}, reverse=True)

    def nb_blocs(self):
        return len(self._refs)

    def rechercher(self, termes, annees=None, mot_entier=False, ignorer_accents=True, limite=300):
        termes = [normaliser(t.strip(), ignorer_accents) for t in termes if t.strip()]
        if not termes:
            return {"resultats": [], "total": 0, "videos": 0}
        motifs = "|".join(re.escape(t) for t in sorted(set(termes), key=len, reverse=True))
        motif = re.compile(rf"(?<!\w)(?:{motifs})(?!\w)" if mot_entier else motifs)
        filtre = set(annees) if annees else None

        trouves = {}  # indice de phrase -> [(début, fin)] relatifs à la phrase
        for m in motif.finditer(self._corpus[ignorer_accents]):
            k = bisect_right(self._debuts, m.start()) - 1
            d = self._debuts[k]
            trouves.setdefault(k, []).append((m.start() - d, m.end() - d))

        resultats, total, videos_touchees = [], 0, set()
        for k in sorted(trouves):
            vi, bi = self._refs[k]
            v = self.videos[vi]
            if filtre and v["annee"] not in filtre:
                continue
            total += 1
            videos_touchees.add(vi)
            if len(resultats) >= limite:
                continue
            blocs = v["blocs"]
            contexte = [{"temps": blocs[j]["temps"], "texte": blocs[j]["texte"], "trouve": j == bi,
                         "surlignage": _fusionner(trouves[k]) if j == bi else []}
                        for j in range(max(0, bi - 2), min(len(blocs), bi + 3))]
            resultats.append({"titre": v["titre"], "annee": v["annee"],
                              "temps": blocs[bi]["temps"], "contexte": contexte})
        return {"resultats": resultats, "total": total, "videos": len(videos_touchees)}
