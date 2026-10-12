"""Accès aux scripts et petit vocabulaire de test (sans les données du dépôt)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pdf_markdown  # noqa: E402


def petit_vocabulaire():
    """Vocabulaire minimal : débuts de phrase fréquents, pour les lettrines perdues."""
    phrases = {
        "Les projets de loi sont votés.": 30, "Le gouvernement attaque.": 40, "La lutte continue.": 40,
        "On lira l'article.": 10, "En effet il faut.": 20, "Pendant ce temps rien.": 25, "Face à la crise.": 25,
        "Après la grève.": 30, "Près de chez lui.": 1, "Et que dire.": 2, "Il est clair.": 30,
    }
    v = pdf_markdown.Vocabulaire()
    for phrase, n in phrases.items():
        for _ in range(n):
            v.ajouter(phrase + "\n")
    return v
