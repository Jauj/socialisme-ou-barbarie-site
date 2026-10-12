"""Corrections relues de l'OCR : data/corrections_ocr/<publication>.json.

Pour les pages scannées les plus abîmées, une version corrigée par un modèle de langue
(erreurs de reconnaissance seulement : lettres confondues, mots coupés ou collés, sans
reformulation ni complément) remplace le texte de Tesseract dans le Markdown et dans la base.
Chaque correction a été contrôlée automatiquement (part des mots modifiés, mots inconnus du
corpus) avant d'être retenue ; le texte brut de l'OCR reste inchangé dans data/pages/.

Format : {"modele": "...", "date": "AAAA-MM-JJ", "pages": {"12": {"texte": "...", ...}}}
"""
import json
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent.parent / "data" / "corrections_ocr"


def charger(pid, dossier=DOSSIER):
    """{n° de page (1 = première): texte corrigé} pour une publication."""
    f = dossier / f"{pid}.json"
    if not f.exists():
        return {}
    pages = json.loads(f.read_text(encoding="utf-8")).get("pages", {})
    return {int(k): v["texte"] for k, v in pages.items()}


def appliquer(pid, pages, dossier=DOSSIER):
    """Textes des pages (liste, page 1 en tête) avec les corrections relues de la publication."""
    corrigees = charger(pid, dossier)
    return [corrigees.get(k, t) for k, t in enumerate(pages, 1)]
