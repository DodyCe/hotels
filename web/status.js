'use strict';

const summary = document.getElementById('summary');
const rows = document.getElementById('services');
const services = [
  ['auth', 'Autenticación', 8101],
  ['notifications', 'Notificaciones', 8102],
  ['reservations', 'Reservas', 8103],
  ['catalog', 'Catálogo de hoteles', 8104],
  ['rooms', 'Habitaciones', 8105],
  ['availability', 'Disponibilidad e inventario', 8106],
];

function cell(text, className) {
  const td = document.createElement('td');
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

async function refresh() {
  try {
    const response = await fetch('/api/readiness', { cache: 'no-store' });
    const data = await response.json();
    rows.replaceChildren(...services.map(([key, name, port]) => {
      const tr = document.createElement('tr');
      const ok = data.services[key] === true;
      tr.append(cell(name), cell(String(port)), cell(ok ? 'Activo' : 'Sin respuesta', ok ? 'ok' : 'fail'));
      return tr;
    }));
    const time = new Date().toLocaleTimeString('es-CO');
    summary.textContent = (data.ready ? 'Todos los servicios responden.' : 'Hay servicios sin responder.') + ' Última consulta: ' + time;
    summary.className = data.ready ? 'ok' : 'fail';
  } catch {
    summary.textContent = 'No se pudo consultar el Gateway.';
    summary.className = 'fail';
  }
}

refresh();
setInterval(refresh, 5000);
