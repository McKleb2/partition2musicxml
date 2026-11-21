"""Conversion de partitions PDF en MusicXML via le moteur OMR Audiveris."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Emplacements par défaut (surchargeables par variables d'environnement).
AUDIVERIS_BIN = os.environ.get(
    "AUDIVERIS_BIN",
    str(BASE_DIR.parent / "audiveris" / "audiveris" / "app" / "build" / "install" / "app" / "bin" / "Audiveris"),
)
TESSDATA_PREFIX = os.environ.get("TESSDATA_PREFIX", str(BASE_DIR.parent / "audiveris" / "tessdata"))
JAVA_HOME = os.environ.get("AUDIVERIS_JAVA_HOME", "/usr/lib/jvm/java-25-openjdk-amd64")
TIMEOUT_SECONDS = int(os.environ.get("AUDIVERIS_TIMEOUT", "1800"))

# Langues OCR proposées (codes Tesseract) pour titres, paroles, indications.
LANGUAGES = {"fra": "Français", "eng": "Anglais", "deu": "Allemand", "ita": "Italien"}


class ConversionError(Exception):
    """Erreur de conversion, avec un extrait du journal Audiveris."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


@dataclass
class ConversionResult:
    files: list[Path]                      # fichiers MusicXML produits (un par mouvement)
    warnings: list[str] = field(default_factory=list)
    log: str = ""


def available_languages() -> dict[str, str]:
    """Langues dont le modèle Tesseract est réellement installé."""
    d = Path(TESSDATA_PREFIX)
    return {k: v for k, v in LANGUAGES.items() if (d / f"{k}.traineddata").exists()}


def check_installation() -> list[str]:
    """Retourne la liste des problèmes d'installation (vide si tout va bien)."""
    problems = []
    if not Path(AUDIVERIS_BIN).is_file():
        problems.append(f"Audiveris introuvable : {AUDIVERIS_BIN} (variable AUDIVERIS_BIN)")
    if not (Path(JAVA_HOME) / "bin" / "java").is_file():
        problems.append(f"Java 25 introuvable : {JAVA_HOME} (variable AUDIVERIS_JAVA_HOME)")
    if not available_languages():
        problems.append(f"Aucun modèle OCR dans {TESSDATA_PREFIX} (variable TESSDATA_PREFIX)")
    return problems


def _sanitize(xml: str, display_name: str) -> str:
    """Remplace le chemin local du PDF (inscrit par Audiveris) par le nom du fichier."""
    name = display_name.replace("&", "&amp;").replace("<", "&lt;")
    xml = re.sub(r"<source>.*?</source>", f"<source>{name}</source>", xml, flags=re.S)
    xml = re.sub(
        r'(<miscellaneous-field name="source-file">).*?(</miscellaneous-field>)',
        rf"\g<1>{name}\g<2>", xml, flags=re.S,
    )
    return xml


def _finalize(mxl: Path, display_name: str, compressed: bool) -> Path:
    """Nettoie un .mxl produit par Audiveris ; le décompresse en .musicxml si demandé."""
    with zipfile.ZipFile(mxl) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    main = next(n for n in entries if n.endswith(".xml") and not n.startswith("META-INF"))
    entries[main] = _sanitize(entries[main].decode("utf-8"), display_name).encode("utf-8")

    if not compressed:
        out = mxl.with_suffix(".musicxml")
        out.write_bytes(entries[main])
        mxl.unlink()
        return out

    tmp = mxl.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        # Le fichier "mimetype" (s'il existe) doit rester le premier, non compressé.
        if "mimetype" in entries:
            z.writestr(zipfile.ZipInfo("mimetype"), entries.pop("mimetype"), zipfile.ZIP_STORED)
        for n, data in entries.items():
            z.writestr(n, data)
    tmp.replace(mxl)
    return mxl


def convert_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    languages: list[str] | None = None,
    compressed: bool = True,
    display_name: str | None = None,
) -> ConversionResult:
    """Convertit un PDF (ou une image) de partition en MusicXML.

    Retourne les fichiers produits dans out_dir : un seul en général, plusieurs
    si Audiveris détecte plusieurs mouvements (nom.mvt1.mxl, nom.mvt2.mxl…).
    """
    pdf_path = Path(pdf_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    display_name = display_name or pdf_path.name

    problems = check_installation()
    if problems:
        raise ConversionError("Installation incomplète :\n- " + "\n- ".join(problems))

    langs = [l for l in (languages or ["fra", "eng"]) if l in available_languages()]
    if not langs:
        langs = list(available_languages())[:1]

    env = dict(os.environ, TESSDATA_PREFIX=TESSDATA_PREFIX, JAVA_HOME=JAVA_HOME)
    env["PATH"] = f"{JAVA_HOME}/bin:{env.get('PATH', '')}"

    with tempfile.TemporaryDirectory(prefix="audiveris-") as work:
        # Nom de fichier neutre : Audiveris tolère mal certains caractères.
        src = Path(work) / "partition.pdf"
        if pdf_path.suffix.lower() != ".pdf":
            src = src.with_suffix(pdf_path.suffix.lower())
        shutil.copyfile(pdf_path, src)
        omr_out = Path(work) / "out"

        cmd = [
            AUDIVERIS_BIN, "-batch", "-export",
            "-output", str(omr_out),
            "-constant", f"org.audiveris.omr.text.Language.defaultSpecification={'+'.join(langs)}",
            "-constant", "org.audiveris.omr.sheet.BookManager.useCompression=true",
            "--", str(src),
        ]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise ConversionError(f"Délai dépassé ({TIMEOUT_SECONDS} s) : la partition est peut-être trop longue.")

        log = proc.stdout + proc.stderr
        log_files = sorted(omr_out.glob("*.log")) if omr_out.exists() else []
        if log_files:
            log = log_files[-1].read_text(errors="replace")

        produced = sorted(omr_out.glob("*.mxl")) if omr_out.exists() else []
        if not produced:
            raise ConversionError(
                "Aucune portée reconnue. Vérifiez que le PDF contient bien une partition "
                "lisible (idéalement imprimée, nette, au moins 300 dpi pour un scan).",
                log=log[-4000:],
            )

        warnings = sorted({
            m.group(1).strip()
            for m in re.finditer(r"WARN .*?\|\s*(.+)", log)
            if "beam height" not in m.group(1)  # avertissement sans conséquence
        })

        stem = Path(display_name).stem or "partition"
        results = []
        for f in produced:
            # partition.mxl -> <stem>.mxl ; partition.mvt2.mxl -> <stem>.mvt2.mxl
            suffix = f.name[len("partition"):]
            target = out_dir / f"{stem}{suffix}"
            shutil.move(str(f), target)
            results.append(_finalize(target, display_name, compressed))

    return ConversionResult(files=results, warnings=warnings, log=log)
