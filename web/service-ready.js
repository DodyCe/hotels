// Espera únicamente lecturas de salud; nunca repite reservas ni cambios de contraseña.
window.waitForHotelsServices = async (onWait = () => {}) => {
  if (location.protocol === 'file:') return true;
  for (let attempt = 0; attempt < 12; attempt++) {
    try {
      const response = await fetch('/api/readiness', { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(75000) });
      if (response.ok && (await response.json()).ready) return true;
    } catch { /* El alojamiento puede estar iniciando los servicios. */ }
    onWait('Estamos iniciando los servicios de Hotels. La primera conexión puede tardar unos minutos…');
    await new Promise(resolve => setTimeout(resolve, 4000));
  }
  onWait('Los servicios siguen iniciándose. Actualiza la página en unos momentos.');
  return false;
};
