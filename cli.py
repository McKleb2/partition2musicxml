#!/usr/bin/env python3
"""Convertit des partitions PDF en MusicXML en ligne de commande.

Exemples :
    python cli.py partition.pdf
    python cli.py *.pdf -o resultats --format musicxml --lang fra+ita
"""

import argparse
import sys
from pathlib import Path

from converter import ConversionError, available_languages, check_installation, convert_pdf


def main() -> int:
    p = argparse.ArgumentParser(description="PDF de partition → MusicXML (moteur Audiveris)")
    p.add_argument("pdf", nargs="+", type=Path, help="fichier(s) PDF ou image(s) de partition")
    p.add_argument("-o", "--output", type=Path, default=Path("."), help="dossier de sortie (défaut : .)")
    p.add_argument("-f", "--format", choices=["mxl", "musicxml"], default="mxl",
                   help="mxl = compressé (défaut), musicxml = XML brut")
    p.add_argument("-l", "--lang", default="fra+eng",
                   help=f"langues OCR séparées par + (disponibles : {'+'.join(available_languages()) or 'aucune'})")
    args = p.parse_args()

    problems = check_installation()
    if problems:
        print("Installation incomplète :\n- " + "\n- ".join(problems), file=sys.stderr)
        print("Lancez d'abord ./install.sh", file=sys.stderr)
        return 2

    failures = 0
    for pdf in args.pdf:
        if not pdf.is_file():
            print(f"✗ {pdf} : fichier introuvable", file=sys.stderr)
            failures += 1
            continue
        print(f"… {pdf.name} : reconnaissance en cours (environ 10 à 30 s par page)")
        try:
            res = convert_pdf(pdf, args.output, languages=args.lang.split("+"),
                              compressed=args.format == "mxl")
        except ConversionError as e:
            print(f"✗ {pdf.name} : {e}", file=sys.stderr)
            failures += 1
            continue
        for f in res.files:
            print(f"✓ {f}")
        for w in res.warnings:
            print(f"  ⚠ {w}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
