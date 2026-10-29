import assert from 'node:assert/strict';
import {cp,mkdir,mkdtemp,readFile,writeFile,access,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';
import vm from 'node:vm';

const root=fileURLToPath(new URL('..',import.meta.url));
const temp=await mkdtemp(join(tmpdir(),'hotels-build-'));
const run=(program,args,env={})=>spawnSync(program,args,{cwd:temp,env:{...process.env,...env},encoding:'utf8'});
try {
  await mkdir(join(temp,'tools'));
  await cp(join(root,'tools/build_frontend.mjs'),join(temp,'tools/build_frontend.mjs'));
  await cp(join(root,'tools/ignore_frontend_build.mjs'),join(temp,'tools/ignore_frontend_build.mjs'));
  await cp(join(root,'web'),join(temp,'web'),{recursive:true});
  await writeFile(join(temp,'.env'),'PRIVATE_BUILD_FIXTURE=must-not-be-published');
  await mkdir(join(temp,'dist'));
  await writeFile(join(temp,'dist/removed.html'),'stale');
  assert.equal(run(process.execPath,['tools/build_frontend.mjs']).status,0);
  await assert.rejects(access(join(temp,'dist/.env')));
  await assert.rejects(access(join(temp,'dist/removed.html')));
  await assert.rejects(access(join(temp,'dist/services')));
  assert.deepEqual(await readFile(join(temp,'dist/index.html')),await readFile(join(temp,'web/index.html')));
  assert.deepEqual(await readFile(join(temp,'dist/vendor/swagger-ui-bundle.js')),gunzipSync(await readFile(join(temp,'web/vendor/swagger-ui-bundle.js.gz'))));

  const source=await readFile(join(root,'vercel.ts'),'utf8');
  process.env.HOTELS_GATEWAY_URL='https://gateway.example.test';
  process.env.ORIGIN_SECRET='private-fixture-'+ 'x'.repeat(40);
  const {config}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  assert.equal(config.outputDirectory,'dist');
  const api=config.routes.find(route=>route.src==='/api/(.*)');
  assert.equal(api.dest,'https://gateway.example.test/api/$1');
  assert.equal(api.transforms[0].args,'$ORIGIN_SECRET');
  assert.ok(!JSON.stringify(config).includes(process.env.ORIGIN_SECRET));
  const readySource=await readFile(join(root,'web/service-ready.js'),'utf8');
  for (const recover of [true,false]) {
    let requests=0;
    const messages=[];
    const context=vm.createContext({window:{},location:{protocol:'https:'},AbortSignal,
      setTimeout:callback=>callback(),fetch:async (url,options)=>{
        assert.equal(url,'/api/readiness'); assert.ok(!options.method || options.method==='GET');
        requests++; if (requests===1) throw new TypeError('cold start');
        return {ok:true,json:async()=>({ready:recover})};
      }});
    vm.runInContext(readySource,context);
    assert.equal(await context.window.waitForHotelsServices(message=>messages.push(message)),recover);
    assert.equal(requests,recover?2:12);
    assert.ok(messages.length>0);
  }
  assert.equal(run(process.execPath,['tools/ignore_frontend_build.mjs'],{VERCEL_GIT_PREVIOUS_SHA:''}).status,1);
  assert.equal(run('git',['init','--quiet']).status,0);
  run('git',['config','user.email','fixture@example.test']);
  run('git',['config','user.name','Build fixture']);
  run('git',['add','tools','web']);
  assert.equal(run('git',['commit','--quiet','-m','fixture']).status,0);
  const previous=run('git',['rev-parse','HEAD']).stdout.trim();
  await writeFile(join(temp,'backend.py'),'# backend change');
  run('git',['add','backend.py']); run('git',['commit','--quiet','-m','backend']);
  assert.equal(run(process.execPath,['tools/ignore_frontend_build.mjs'],{VERCEL_GIT_PREVIOUS_SHA:previous}).status,0);
  await writeFile(join(temp,'web/change.css'),'body{}');
  run('git',['add','web']); run('git',['commit','--quiet','-m','frontend']);
  assert.equal(run(process.execPath,['tools/ignore_frontend_build.mjs'],{VERCEL_GIT_PREVIOUS_SHA:previous}).status,1);
  process.stdout.write('Frontend: artefacto aislado, Swagger, secreto privado y despliegues independientes verificados.\n');
} finally {
  if (!resolve(temp).startsWith(resolve(tmpdir())+ (process.platform==='win32'?'\\':'/'))) throw new Error('Carpeta temporal inválida.');
  await rm(temp,{recursive:true,force:true});
}
