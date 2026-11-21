#!/usr/bin/env bash
# Installe tout ce qu'il faut pour partition2musicxml (Linux ou macOS) :
#   - Audiveris (compilé depuis les sources, nécessite Java 25 et git)
#   - les modèles OCR Tesseract (français, anglais, allemand, italien)
#   - un environnement Python avec Flask
# Usage : ./install.sh            (installe dans ../audiveris, à côté de ce dossier)
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="${AUDIVERIS_DIR:-$(dirname "$APP_DIR")/audiveris}"
LANGS="eng fra deu ita"

need() { command -v "$1" >/dev/null || { echo "✗ '$1' est requis : $2" >&2; exit 1; }; }
need git "installez git"
need python3 "installez Python 3.10 ou plus récent"

# Java 25 (Audiveris l'exige)
if [ -z "${AUDIVERIS_JAVA_HOME:-}" ]; then
  for d in /usr/lib/jvm/java-25-openjdk-amd64 /usr/lib/jvm/java-25-openjdk-arm64 \
           /opt/homebrew/opt/openjdk@25 /usr/local/opt/openjdk@25 "${JAVA_HOME:-}"; do
    if [ -x "$d/bin/java" ] && "$d/bin/java" -version 2>&1 | grep -q '"25'; then AUDIVERIS_JAVA_HOME="$d"; break; fi
  done
fi
if [ -z "${AUDIVERIS_JAVA_HOME:-}" ]; then
  echo "✗ Java 25 introuvable. Installez-le :" >&2
  echo "    Ubuntu/Debian : sudo apt install openjdk-25-jdk-headless" >&2
  echo "    macOS         : brew install openjdk@25" >&2
  echo "  puis relancez ce script (ou définissez AUDIVERIS_JAVA_HOME)." >&2
  exit 1
fi
echo "✓ Java 25 : $AUDIVERIS_JAVA_HOME"

mkdir -p "$DEST"

# 1. Audiveris
if [ ! -x "$DEST/audiveris/app/build/install/app/bin/Audiveris" ]; then
  [ -d "$DEST/audiveris/.git" ] || git clone --depth 1 https://github.com/Audiveris/audiveris "$DEST/audiveris"
  echo "… compilation d'Audiveris (quelques minutes la première fois)"
  (cd "$DEST/audiveris" && JAVA_HOME="$AUDIVERIS_JAVA_HOME" PATH="$AUDIVERIS_JAVA_HOME/bin:$PATH" \
     ./gradlew --no-daemon -q :app:installDist)
fi
echo "✓ Audiveris compilé"

# 2. Modèles OCR (version standard : Audiveris utilise le moteur « legacy » de Tesseract)
if [ ! -d "$DEST/tessdata/.git" ]; then
  git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/tesseract-ocr/tessdata "$DEST/tessdata"
fi
(cd "$DEST/tessdata" && git sparse-checkout set --no-cone $(for l in $LANGS; do echo "/$l.traineddata"; done) && git checkout -q)
echo "✓ Modèles OCR : $LANGS"

# 3. Python
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
echo "✓ Environnement Python"

# 4. Fichier de configuration lu par run.sh
cat > "$APP_DIR/.env" <<EOF
AUDIVERIS_BIN=$DEST/audiveris/app/build/install/app/bin/Audiveris
TESSDATA_PREFIX=$DEST/tessdata
AUDIVERIS_JAVA_HOME=$AUDIVERIS_JAVA_HOME
EOF
echo
echo "Installation terminée. Lancez l'application avec :  ./run.sh"
