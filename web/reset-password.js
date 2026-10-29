const form = document.querySelector('#reset-form');
const errorBox = document.querySelector('#reset-error');
const resultBox = document.querySelector('#reset-result');
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
history.replaceState(null,'',location.pathname);
let servicesReady = false;
if (!/^[A-Za-z0-9_-]{43}$/.test(token)) {
  token = ''; form.hidden = true;
  resultBox.textContent = 'El enlace no es válido o está incompleto. Solicita uno nuevo desde Hotels.';
}
form.addEventListener('submit',async (event) => {
  event.preventDefault(); errorBox.textContent = '';
  if (!servicesReady) { errorBox.textContent = 'Espera a que Hotels termine de conectar sus servicios.'; return; }
  const data = Object.fromEntries(new FormData(form));
  if (data.password !== data.confirmPassword) { errorBox.textContent = 'Las contraseñas no coinciden.'; return; }
  const button = form.querySelector('button'); button.disabled = true;
  try {
    const response = await fetch('/api/auth/reset-password',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,...data})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo actualizar la contraseña.');
    token = ''; form.reset(); form.hidden = true; resultBox.textContent = result.message;
  } catch (error) { errorBox.textContent = error instanceof TypeError ? 'No hay conexión con Hotels. Inténtalo de nuevo.' : error.message; }
  finally { button.disabled = false; }
});
if (token) {
  form.querySelector('button').disabled = true;
  window.waitForHotelsServices(message => { resultBox.textContent = message; }).then(ready => {
    servicesReady = ready;
    form.querySelector('button').disabled = !ready;
    if (ready) resultBox.textContent = '';
  });
}
