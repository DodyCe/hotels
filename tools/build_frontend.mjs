import {cp,mkdir,readFile,writeFile,unlink,rm,lstat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {gunzipSync} from 'node:zlib';

const root=fileURLToPath(new URL('..',import.meta.url));
const output=resolve(root,'dist');
if (output !== resolve(root)+'/dist' && output !== resolve(root)+'\\dist') throw new Error('Directorio de salida inválido.');
try {
  if ((await lstat(output)).isSymbolicLink()) throw new Error('dist no puede ser un enlace.');
  await rm(output,{recursive:true});
} catch (error) { if (error.code !== 'ENOENT') throw error; }
await mkdir(output,{recursive:true});
await cp(resolve(root,'web'),output,{recursive:true});
const bundle=resolve(output,'vendor/swagger-ui-bundle.js.gz');
await writeFile(resolve(output,'vendor/swagger-ui-bundle.js'),gunzipSync(await readFile(bundle)));
await unlink(bundle);
process.stdout.write('Frontend preparado en dist; no contiene .env, bases ni código del backend.\n');
