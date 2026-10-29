async function loadDocumentation() {
  const internal = document.querySelector('#api-spec').value === 'internal';
  document.body.classList.toggle('docs-internal',internal);
  document.querySelector('#docs-error').textContent = '';
  document.querySelector('#docs-note').textContent = internal ? 'Estas rutas solo se usan entre microservicios con una clave privada. La consola interna es de solo lectura; no solicita ni expone la clave.' : 'Para probar reservas y administración, inicia sesión en Hotels en otra pestaña. Las operaciones utilizan tu sesión actual y pueden modificar datos.';
  try {
    const response = await fetch(internal?'/openapi-internal.json':'/openapi.json');
    if(!response.ok)throw new Error('No se pudo cargar el contrato.');
    const spec = await response.json();
    if(!internal)spec.servers=[{url:location.origin+'/api',description:'Gateway de esta instancia'}];
    window.SwaggerUIBundle({spec,dom_id:'#swagger-ui',deepLinking:true,validatorUrl:null,persistAuthorization:false,withCredentials:true,supportedSubmitMethods:internal?[]:['get','post','patch','put','delete'],docExpansion:'list',displayRequestDuration:true});
  }catch(error){document.querySelector('#docs-error').textContent=error.message;}
}
document.querySelector('#api-spec').addEventListener('change',loadDocumentation);
loadDocumentation();
