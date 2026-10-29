import {spawnSync} from 'node:child_process';
const previous=process.env.VERCEL_GIT_PREVIOUS_SHA || '';
if (!/^[a-f0-9]{40,64}$/i.test(previous)) process.exit(1);
const result=spawnSync('git',['diff','--quiet',previous,'HEAD','--','web','vercel.ts','tools/build_frontend.mjs','tools/ignore_frontend_build.mjs']);
// Vercel: 0 omite, 1 construye; ante una referencia ausente se construye.
process.exit(result.status===0 ? 0 : 1);
