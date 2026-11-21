# partition2musicxml

Convertit des partitions **PDF** (ou images PNG/JPG/TIFF) en fichiers **MusicXML**, ouvrables dans MuseScore, Finale, Sibelius, Dorico, etc.

La reconnaissance optique de musique (OMR) est assurée par [Audiveris](https://github.com/Audiveris/audiveris) (open source, AGPL), et celle des textes (titres, paroles, indications) par Tesseract.

## Installation

Prérequis : `git`, Python 3.10+ et **Java 25**.

```bash
# Ubuntu / Debian
sudo apt install git python3-venv openjdk-25-jdk-headless
# macOS
brew install git python openjdk@25
```

Puis :

```bash
chmod +x install.sh run.sh
./install.sh
```

Le script compile Audiveris (quelques minutes) dans `../audiveris`, télécharge les modèles OCR et prépare l'environnement Python.

> Si Audiveris est déjà installé sur votre machine (par exemple avec l'installeur officiel), vous pouvez ignorer `install.sh` : créez un environnement Python avec Flask et définissez `AUDIVERIS_BIN`, `TESSDATA_PREFIX` et `AUDIVERIS_JAVA_HOME` dans un fichier `.env`.

## Utilisation

**Application web**

```bash
./run.sh
```

Ouvrez http://127.0.0.1:8000. Déposez le PDF, choisissez le format (`.mxl` compressé ou `.musicxml` brut) et la langue des textes. Une fois la conversion faite, vous téléchargez le fichier et voyez un aperçu de la partition reconnue.

**Ligne de commande**

```bash
./run.sh partition.pdf -o resultats
./run.sh *.pdf -o resultats --format musicxml --lang fra+ita
```

Si la partition contient plusieurs mouvements, Audiveris produit un fichier par mouvement (`nom.mvt1.mxl`, `nom.mvt2.mxl`…).

## Qualité des résultats

| Source | Résultat attendu |
|---|---|
| PDF produit par un logiciel de gravure (MuseScore, LilyPond, Finale…) | Très bon |
| Scan propre, 300 dpi, page droite | Bon, avec quelques corrections |
| Photo de téléphone, scan de mauvaise qualité | Médiocre |
| Partition manuscrite | Non pris en charge |

Relisez toujours le résultat dans votre éditeur de partitions : aucune reconnaissance optique n'est parfaite. Les erreurs typiques sont des titres non détectés, des syllabes de paroles mal lues, et des liaisons ou nuances manquantes.

## Configuration (variables d'environnement)

| Variable | Rôle | Défaut |
|---|---|---|
| `AUDIVERIS_BIN` | Exécutable Audiveris | `../audiveris/audiveris/app/build/install/app/bin/Audiveris` |
| `TESSDATA_PREFIX` | Dossier des modèles OCR | `../audiveris/tessdata` |
| `AUDIVERIS_JAVA_HOME` | Java 25 | `/usr/lib/jvm/java-25-openjdk-amd64` |
| `AUDIVERIS_TIMEOUT` | Durée maximale d'une conversion (s) | `1800` |
| `HOST` / `PORT` | Adresse du serveur web | `127.0.0.1` / `8000` |
| `WORKERS` | Conversions simultanées | `2` |
| `MAX_UPLOAD_MB` | Taille maximale d'un PDF | `50` |

Les fichiers envoyés et les résultats sont supprimés automatiquement au bout d'une heure.

> **Mise en ligne publique :** le serveur intégré de Flask est fait pour un usage local. Pour exposer l'application sur Internet, placez-la derrière un serveur de production (par exemple `gunicorn -w 1 --threads 4 server:app`) et un reverse proxy. Gardez un seul processus, car la liste des tâches est en mémoire.

## Fichiers

- `converter.py` : appel d'Audiveris et nettoyage du MusicXML (le chemin local du PDF est remplacé par son nom)
- `server.py` : API et application web (Flask)
- `cli.py` : outil en ligne de commande
- `static/index.html` : interface web ; `static/vendor/` : OpenSheetMusicDisplay pour l'aperçu (licence BSD-3)

## Licences

Audiveris est sous licence AGPL-3.0. Si vous proposez ce service publiquement sur un réseau, les obligations de l'AGPL s'appliquent à Audiveris.
