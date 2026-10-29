"""Prepara los archivos estáticos oficiales de swagger-ui-dist fijados en package-lock."""
import gzip
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
package = ROOT/'node_modules'/'swagger-ui-dist'
version = json.loads((package/'package.json').read_text())['version']
assert version == '5.34.0', 'Revisa la actualización del paquete y su licencia antes de regenerar.'
target = ROOT/'web'/'vendor'
target.mkdir(exist_ok=True)
(target/'swagger-ui-bundle.js.gz').write_bytes(gzip.compress((package/'swagger-ui-bundle.js').read_bytes(),mtime=0))
shutil.copyfile(package/'swagger-ui.css',target/'swagger-ui.css')
shutil.copyfile(package/'LICENSE',target/'swagger-ui-LICENSE.txt')
print('Swagger UI '+version+' preparado para servir desde Hotels, sin CDN ni Node en ejecución.')
