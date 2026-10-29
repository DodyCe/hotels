const gateway = new URL(process.env.HOTELS_GATEWAY_URL || '');
if (gateway.protocol !== 'https:' || gateway.username || gateway.password || gateway.pathname !== '/' || gateway.search || gateway.hash) {
  throw new Error('Configura HOTELS_GATEWAY_URL con la URL HTTPS del Gateway de Render.');
}
if (!process.env.ORIGIN_SECRET || process.env.ORIGIN_SECRET.length < 32) {
  throw new Error('Configura ORIGIN_SECRET en Vercel y en el Gateway.');
}
const originHeader = [{type:'request.headers',op:'set',target:{key:'x-origin-secret'},args:'$ORIGIN_SECRET',env:['ORIGIN_SECRET']}];
export const config = {
  framework: null,
  installCommand: '',
  buildCommand: 'node tools/build_frontend.mjs',
  outputDirectory: 'dist',
  ignoreCommand: 'node tools/ignore_frontend_build.mjs',
  routes: [
    {src:'/(.*)',headers:{'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin','Content-Security-Policy':"default-src 'self'; img-src 'self' https://images.unsplash.com data:; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"},continue:true},
    {src:'/reset-password.html',headers:{'Referrer-Policy':'no-referrer','Cache-Control':'no-store'},continue:true},
    {src:'/api/(.*)',dest:gateway.origin+'/api/$1',transforms:originHeader},
    {src:'/(openapi|openapi-internal).json',dest:gateway.origin+'/$1.json',transforms:originHeader},
    {handle:'filesystem'},
  ],
};
