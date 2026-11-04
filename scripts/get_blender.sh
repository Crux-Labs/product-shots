#!/usr/bin/env bash
# Downloads a portable Blender into tools/blender (nothing installed system-wide). About 300 MB.
# Override the version with BLENDER_VERSION=4.2.3 ./scripts/get_blender.sh (4.2 or newer).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${BLENDER_VERSION:-5.2.3}
SERIES=${VERSION%.*}
MIRRORS=(https://download.blender.org/release https://mirror.clarkson.edu/blender/release https://ftp.nluug.nl/pub/graphics/blender/release)
mkdir -p tools
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  FILE="blender-${VERSION}-macos-arm64.dmg" ;;
  Linux-x86_64)  FILE="blender-${VERSION}-linux-x64.tar.xz" ;;
  *) echo "No portable Blender for $(uname -s)-$(uname -m). Install Blender 4.2+ yourself and set BLENDER_PATH in .env." >&2; exit 1 ;;
esac

got=""
for m in "${MIRRORS[@]}"; do
  echo "Downloading ${m}/Blender${SERIES}/${FILE}"
  if curl -fL --progress-bar -A "layoutfirst-setup" -o "tools/${FILE}" "${m}/Blender${SERIES}/${FILE}"; then got=1; break; fi
done
[ -n "$got" ] || { echo "Could not download ${FILE}. Install Blender 4.2+ from blender.org and set BLENDER_PATH in .env." >&2; exit 1; }
rm -rf tools/blender && mkdir -p tools/blender
if [[ "$FILE" == *.dmg ]]; then
  MNT=$(mktemp -d)
  hdiutil attach -quiet -nobrowse -mountpoint "$MNT" "tools/${FILE}"
  cp -R "$MNT/Blender.app" tools/blender/
  hdiutil detach -quiet "$MNT"
else
  tar -xf "tools/${FILE}" -C tools/blender --strip-components=1
fi
rm -f "tools/${FILE}"
echo "Blender ready in tools/blender"
