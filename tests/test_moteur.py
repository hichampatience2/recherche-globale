import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from moteur import Index  # noqa: E402

EXEMPLE = os.path.join(os.path.dirname(__file__), "..", "exemple", "FUSION_EXEMPLE.txt")


class TestMoteur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = Index.depuis_fichier(EXEMPLE)

    def test_lecture(self):
        self.assertEqual(len(self.idx.videos), 2)
        self.assertEqual(self.idx.annees(), ["2024", "2019"])
        self.assertEqual(self.idx.videos[1]["titre"], "20240706 - Exemple de vidéo deux.fr")

    def test_message_turboscribe_retire(self):
        self.assertTrue(self.idx.videos[0]["blocs"][0]["texte"].startswith("Bonjour"))

    def test_accents_et_casse(self):
        r = self.idx.rechercher(["priere"])
        self.assertEqual(r["total"], 2)
        r = self.idx.rechercher(["priere"], ignorer_accents=False)
        self.assertEqual(r["total"], 0)

    def test_surlignage_aligne(self):
        r = self.idx.rechercher(["ecole"])
        bloc = next(c for c in r["resultats"][0]["contexte"] if c["trouve"])
        d, f = bloc["surlignage"][0]
        self.assertEqual(bloc["texte"][d:f], "ÉCOLE")

    def test_mot_entier(self):
        self.assertEqual(self.idx.rechercher(["ecole"])["total"], 1)
        r = self.idx.rechercher(["ecol"], mot_entier=True)
        self.assertEqual(r["total"], 0)

    def test_plusieurs_termes_et_annees(self):
        r = self.idx.rechercher(["coran", "vendredi"])
        self.assertEqual(r["total"], 2)
        self.assertEqual(r["videos"], 2)
        r = self.idx.rechercher(["coran", "vendredi"], annees=["2019"])
        self.assertEqual(r["total"], 1)

    def test_contexte_et_limite(self):
        r = self.idx.rechercher(["e"], limite=1)
        self.assertEqual(len(r["resultats"]), 1)
        self.assertGreater(r["total"], 1)
        self.assertLessEqual(len(r["resultats"][0]["contexte"]), 5)


if __name__ == "__main__":
    unittest.main()
