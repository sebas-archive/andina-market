#!/usr/bin/env bash
# Exporta docs/informe.md a entrega/Informe_Guia7_AndinaMarket.pdf (Tarea 7.3).
# Pandoc (imagen Docker oficial) genera HTML con tabla de contenido y recursos embebidos;
# Chrome/Chromium imprime ese HTML a PDF. Uso: CHROME=/ruta/a/chrome bash scripts/exportar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-$(command -v chromium || command -v google-chrome || true)}"
[ -n "$CHROME" ] || { echo "Defina CHROME con la ruta a Chrome o Chromium" >&2; exit 1; }
HTML=entrega/Informe_Guia7_AndinaMarket.html
PDF=entrega/Informe_Guia7_AndinaMarket.pdf

docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/data" -w /data pandoc/core:3.5 \
  docs/informe.md -s --toc --toc-depth=2 --embed-resources --resource-path=docs \
  --css=docs/informe.css -o "$HTML"
# Marca los pies de tabla ("Tabla N.") para que no queden separados de su tabla al paginar.
sed -i -E 's#<p><strong>(Tabla [0-9A]+\.)</strong>#<p class="leyenda"><strong>\1</strong>#g' "$HTML"
URL="file://$(python3 -c 'import os,sys,urllib.parse;print(urllib.parse.quote(os.path.abspath(sys.argv[1])))' "$HTML")"
"$CHROME" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf="$PWD/$PDF" "$URL"
rm -f "$HTML"
echo "PDF: $PDF"
