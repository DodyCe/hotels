/* Hotels: interfaz HTML/CSS y APIs de autenticación, reservas y notificaciones. */
const $ = (selector) => document.querySelector(selector);
let hotelCatalog = window.HOTELS_CATALOG;
let rooms = window.HOTELS_ROOMS;
let hotels = [];
const money = (value) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);
const dateText = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value + 'T12:00:00'));
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localISO = (date) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
// Mismo calendario que el servidor (common.validate_dates): hora de Montería, sin importar la zona del visitante.
const hotelToday = () => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
};
const addDays = (iso, days) => { const date = new Date(iso + 'T12:00:00'); date.setDate(date.getDate() + days); return localISO(date); };
const today = hotelToday();
$('#checkin').value = addDays(today, 7); $('#checkout').value = addDays(today, 10); $('#checkin').min = today;
const state = { checkin: $('#checkin').value, checkout: $('#checkout').value, guests: 2, filter: 'all', sort: 'recommended', selected: hotelCatalog[0].id, availability: {}, roomChoice: {}, user: null, online: false };
let toastTimer;
let modalOpener = null;

function hideToast() {
  const el = $('#toast'); clearTimeout(toastTimer);
  if (el.hidePopover && el.matches(':popover-open')) el.hidePopover();
  el.hidden = true;
}
function toast(message, type = 'info') {
  const el = $('#toast');
  el.className = `toast toast-${type}`; $('#toast-message').textContent = '';
  el.hidden = false;
  // Como popover queda en la capa superior, visible también sobre el modal abierto.
  if (el.showPopover) { if (el.matches(':popover-open')) el.hidePopover(); el.showPopover(); }
  requestAnimationFrame(() => { $('#toast-message').textContent = message; });
  clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, type === 'error' ? 9000 : 5500);
}
async function api(path, body) {
  if (location.protocol === 'file:') throw new Error('Abre Hotels desde su dirección web para usar esta función.');
  let response;
  try {
    response = await fetch('/api' + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', headers: body === undefined ? {} : {'Content-Type':'application/json'}, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch { throw new Error('No hay conexión con Hotels. Inténtalo de nuevo en unos momentos.'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('El servicio no está disponible en este momento. Inténtalo de nuevo.'); }
  if (!response.ok) {
    if (response.status === 401 && !path.endsWith('/login')) { state.user = null; renderAccount(); }
    const error = new Error(data.error || 'No se pudo completar la operación.'); error.status = response.status; throw error;
  }
  return data;
}
function nights() { return Math.round((Date.parse(state.checkout+'T00:00:00Z')-Date.parse(state.checkin+'T00:00:00Z'))/86400000); }
function visibleHotels() {
  hotels = hotelCatalog.flatMap((hotel) => {
    const options = rooms.filter((room) => room.hotelId === hotel.id && room.capacity >= state.guests && (!state.online || state.availability[room.id] > 0));
    const room = options.find((r) => r.id === state.roomChoice[hotel.id]) || options[0];
    if (!room) return [];
    state.roomChoice[hotel.id] = room.id;
    return [{...hotel, roomId:room.id, room:room.name, capacity:room.capacity, price:room.price, roomOptions:options}];
  });
  return hotels.filter((h) => state.filter === 'all' || h.tags.includes(state.filter)).sort((a,b) => state.sort === 'price' ? a.price-b.price : 0);
}
function renderAccount() {
  $('#login-button').textContent = state.user ? 'Mi cuenta ↗' : 'Ingresar / Registrarse ↗';
  $('#account-note').textContent = state.user ? `Las confirmaciones se asociarán al correo de tu cuenta: ${state.user.email}` : 'Inicia sesión para guardar tus reservas y recibir las confirmaciones en tu correo.';
  updateButton();
}
function updateButton() {
  $('#reserve-button').disabled = !state.selected;
  $('#reserve-button').innerHTML = !state.selected ? 'Sin cupos para estos criterios' : `${state.user ? 'Continuar con la reserva' : 'Iniciar sesión y reservar'} <span aria-hidden="true">→</span>`;
}
function render() {
  const results = visibleHotels();
  if (!results.some((h) => h.id === state.selected)) state.selected = results[0]?.id || null;
  $('#result-description').textContent = `${results.length} ${results.length === 1 ? 'alojamiento disponible' : 'alojamientos disponibles'} · ${dateText(state.checkin)} – ${dateText(state.checkout)} · ${state.guests} ${state.guests === 1 ? 'adulto' : 'adultos'}`;
  $('#hotel-list').innerHTML = results.length ? results.map((h) => `<article class="hotel-card ${h.id === state.selected ? 'selected' : ''}"><div class="hotel-image"><img src="${h.image}" alt="Foto ilustrativa de ${h.photographer}; no corresponde a ${h.name}" loading="lazy" referrerpolicy="no-referrer"><span class="hotel-badge">${h.badge}</span><a class="photo-credit" href="${h.photoPage}" target="_blank" rel="noopener noreferrer">Foto ilustrativa · ${h.photographer} / Unsplash ↗</a></div><div class="hotel-content"><div class="hotel-topline"><span class="hotel-location">Montería · ${h.area}</span><span class="local-badge">Montería</span></div><h3>${h.name}</h3><p class="hotel-address">${h.address}</p><p class="hotel-description">${h.description}</p><a class="official-link" href="${h.source}" target="_blank" rel="noopener noreferrer">Información oficial del hotel ↗</a><label class="room-picker">ELIGE TU HABITACIÓN<select data-room-hotel="${h.id}" aria-label="Habitación en ${h.name}">${h.roomOptions.map((r) => `<option value="${r.id}" ${r.id === h.roomId ? 'selected' : ''}>${r.name} · ${money(r.price)}/noche</option>`).join('')}</select></label><p class="room-type">Hasta ${h.capacity} adultos</p><div class="amenities">${h.amenities.map((a) => `<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>${a}</span>`).join('')}</div><div class="hotel-bottom"><div><p class="price-label">POR NOCHE</p><div class="price">${money(h.price)} <small>/ noche</small></div><span class="availability">Disponible para tus fechas</span></div><button class="select-room" data-hotel="${h.id}" aria-pressed="${h.id === state.selected}" aria-label="${h.id === state.selected ? 'Habitación seleccionada en ' : 'Elegir habitación en '}${h.name}">${h.id === state.selected ? 'Seleccionada <span>✓</span>' : 'Elegir habitación <span>↗</span>'}</button></div></div></article>`).join('') : '<div class="empty"><strong>No encontramos habitaciones con estos criterios.</strong><p>Prueba otras fechas, menos huéspedes o el filtro «Todos los hoteles».</p></div>';
  $('#hotel-list').querySelectorAll('img').forEach((image) => image.addEventListener('error', () => {
    image.hidden = true;
    const fallback = document.createElement('span'); fallback.className = 'no-photo'; fallback.textContent = 'Fotografía de referencia no disponible sin conexión.'; image.parentElement.prepend(fallback);
  }, {once:true}));
  const selected = hotels.find((h) => h.id === state.selected);
  ['.selected-hotel','.booking-details','.price-lines','.total'].forEach((selector) => { $(selector).hidden = !selected; });
  updateButton();
  if (selected) {
    $('#summary-image').src = selected.image; $('#summary-name').textContent = selected.name;
    $('#summary-room').textContent = selected.room;
    $('#summary-checkin').textContent = dateText(state.checkin); $('#summary-checkout').textContent = dateText(state.checkout);
    $('#summary-guests').textContent = `${state.guests} ${state.guests === 1 ? 'adulto' : 'adultos'}`;
    $('#night-label').textContent = `${money(selected.price)} × ${nights()} ${nights() === 1 ? 'noche' : 'noches'}`;
    $('#subtotal').textContent = money(selected.price*nights()); $('#total').innerHTML = `${money(selected.price*nights())} <small>COP</small>`;
  }
}
async function refreshAvailability() {
  const list = $('#hotel-list');
  list.classList.add('loading'); list.setAttribute('aria-busy', 'true');
  $('#result-description').textContent = 'Actualizando disponibilidad…';
  try {
    const [catalogData, roomsData, availabilityData] = await Promise.all([
      api('/hotels'), api('/rooms'), api(`/availability?checkin=${state.checkin}&checkout=${state.checkout}`)
    ]);
    hotelCatalog = catalogData.hotels; rooms = roomsData.rooms;
    state.availability = Object.fromEntries(availabilityData.availability.map((r) => [r.roomId,r.available]));
    state.online = true; $('#connection-note').textContent = '';
  } finally {
    list.classList.remove('loading'); list.removeAttribute('aria-busy'); render();
  }
}
function openModal(html) {
  if (!$('#modal').open) modalOpener = document.activeElement;
  $('#modal-content').innerHTML = html;
  if (!$('#modal').open) $('#modal').showModal();
  const target = $('#modal-content input, #modal-content select') || $('#modal-content h2');
  if (target) { if (target.tagName === 'H2') target.tabIndex = -1; target.focus(); }
}
$('#modal').addEventListener('close', () => { if (modalOpener?.isConnected) modalOpener.focus(); modalOpener = null; });
$('.close-modal').addEventListener('click', () => $('#modal').close());
$('.toast-close').addEventListener('click', hideToast);
$('#modal').addEventListener('click', (event) => {
  if (event.target !== $('#modal')) return;
  const bounds = $('#modal').getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) $('#modal').close();
});
async function withBusy(button, action) {
  const original = button.textContent; button.disabled = true; button.textContent = 'Un momento…';
  try { await action(); } catch (error) { const inline = $('#form-error'); if (inline) inline.textContent = error.message; else toast(error.message, 'error'); }
  finally { if (button.isConnected) { button.disabled = false; button.textContent = original; } }
}
function showAuth(mode='login', continueBooking=false) {
  const register = mode === 'register';
  openModal(`<p class="eyebrow">TU CUENTA EN HOTELS</p><h2>${register ? 'Crea tu cuenta' : 'Qué bueno verte'}</h2><p>Gestiona tus reservas y recibe las confirmaciones en el correo de tu cuenta.</p><div class="auth-tabs"><button class="${!register ? 'active' : ''}" id="login-tab">Ingresar</button><button class="${register ? 'active' : ''}" id="register-tab">Registrarse</button></div><form id="auth-form">${register ? '<label>Nombre completo<input name="name" autocomplete="name" minlength="2" maxlength="80" required placeholder="Tu nombre completo"></label>' : ''}<label>Correo electrónico<input name="email" type="email" autocomplete="email" maxlength="254" required placeholder="nombre@ejemplo.com"></label><label>Contraseña<input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" minlength="10" maxlength="128" required placeholder="Mínimo 10 caracteres"></label><p class="form-error" id="form-error" role="alert"></p><button class="button primary" type="submit">${register ? 'Crear cuenta' : 'Ingresar'}</button></form><p class="modal-hint">Recibirás los avisos de tu cuenta y tus reservas en este correo. Usa una contraseña exclusiva para Hotels.</p>`);
  $('#login-tab').addEventListener('click', () => showAuth('login', continueBooking));
  $('#register-tab').addEventListener('click', () => showAuth('register', continueBooking));
  $('#auth-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.target));
    await withBusy(event.target.querySelector('button[type=submit]'), async () => {
      const result = await api('/auth/' + mode, data); state.user = result.user; renderAccount();
      if (continueBooking && state.selected) showBooking(); else { $('#modal').close(); toast(register ? 'Cuenta creada. Ya puedes gestionar tus reservas.' : 'Sesión iniciada.', 'success'); }
    });
  });
}
function showAccount() {
  if (!state.user) return showAuth();
  openModal(`<p class="eyebrow">TU CUENTA</p><h2>Hola, ${escapeHTML(state.user.name)}</h2><div class="auth-details"><strong>Correo de notificaciones</strong><br>${escapeHTML(state.user.email)}</div><p class="modal-hint">Las confirmaciones y cancelaciones se dirigirán a este correo. Tu cuenta y tus reservas se conservan al reiniciar la aplicación.</p><button class="button secondary" id="logout-button">Cerrar sesión</button>`);
  $('#logout-button').addEventListener('click', (event) => withBusy(event.target, async () => { await api('/auth/logout', {}); state.user = null; renderAccount(); $('#modal').close(); toast('Sesión cerrada.'); }));
}
function showBooking() {
  if (!state.user) return showAuth('login',true);
  const hotel = hotels.find((h) => h.id === state.selected); if (!hotel) return;
  openModal(`<p class="eyebrow">CONFIRMA TU PLAN</p><h2>Tu estancia en Montería</h2><p><strong>${hotel.name}</strong><br>${hotel.room}<br>${dateText(state.checkin)} – ${dateText(state.checkout)}<br>${state.guests} ${state.guests === 1 ? 'adulto' : 'adultos'} · ${nights()} ${nights() === 1 ? 'noche' : 'noches'}</p><p class="modal-total">Total de la estancia: <strong>${money(hotel.price*nights())} COP</strong></p><div class="auth-details"><strong>Huésped</strong>: ${escapeHTML(state.user.name)}<br><strong>Confirmación a</strong>: ${escapeHTML(state.user.email)}</div><form id="reservation-form"><p class="modal-hint">Revisa las fechas y los datos del huésped antes de confirmar. Esta operación no realiza ningún cobro.</p><p class="form-error" id="form-error" role="alert"></p><button type="submit" class="button primary">Confirmar reserva →</button></form>`);
  $('#reservation-form').addEventListener('submit', (event) => {
    event.preventDefault();
    withBusy(event.target.querySelector('button'), async () => {
      const result = await api('/reservations', {hotelId:hotel.id,roomId:hotel.roomId,checkin:state.checkin,checkout:state.checkout,guests:state.guests});
      if (result.reservation.status === 'Pendiente') {
        openModal(`<h2>Reserva en proceso</h2><p>${result.reservation.id}</p><p>La solicitud está guardada. Estamos comprobando la disponibilidad. Consulta el estado en «Mis reservas»; te avisaremos cuando se confirme.</p><button class="button primary" id="pending-reservations">Ver mis reservas</button>`);
        $('#pending-reservations').addEventListener('click',showReservations);
        return;
      }
      openModal(`<div class="success-icon" aria-hidden="true">✓</div><h2>Reserva confirmada</h2><p><strong>${result.reservation.id}</strong><br>${hotel.name}</p><p>Guardamos tu reserva y estamos preparando la confirmación para el correo de tu cuenta.</p><p class="modal-hint">Puedes consultar los detalles y el estado del aviso en «Mis reservas» y «Notificaciones».</p><button class="button primary" id="see-reservations">Ver mis reservas →</button>`);
      $('#see-reservations').addEventListener('click', showReservations);
      await refreshAvailability();
    });
  });
}
async function showReservations() {
  if (!state.user) return showAuth();
  openModal('<h2>Mis reservas</h2><p>Cargando tus reservas…</p>');
  try {
    const data = await api('/reservations');
    openModal(`<p class="eyebrow">TUS PLANES EN MONTERÍA</p><h2>Mis reservas</h2><p>Consulta tus próximas estancias y el estado de tus reservas.</p><button class="button secondary" id="refresh-reservations">Actualizar reservas</button>${data.reservations.length ? data.reservations.map((r) => `<article class="reservation-item"><h3>${escapeHTML(r.hotel)}</h3><p>${r.id} · <strong>${r.status}</strong><br>${escapeHTML(r.room)}<br>${dateText(r.checkin)} – ${dateText(r.checkout)}<br>${r.guests} ${r.guests === 1 ? 'adulto' : 'adultos'} · ${money(r.total)} COP</p>${['Confirmada','Pendiente'].includes(r.status) ? `<button class="cancel-button" data-cancel="${r.id}">Cancelar reserva</button>` : ''}</article>`).join('') : '<div class="reservation-item"><p>Todavía no tienes reservas. Explora los hoteles para empezar.</p></div>'}`);
    $('#refresh-reservations').addEventListener('click',showReservations);
    document.querySelectorAll('[data-cancel]').forEach((button) => button.addEventListener('click', () => confirmCancel(data.reservations.find((r) => r.id === button.dataset.cancel))));
  } catch (error) { openModal(`<h2>Mis reservas</h2><p>${escapeHTML(error.message)}</p>`); }
}
function confirmCancel(r) {
  openModal(`<p class="eyebrow">CANCELAR RESERVA</p><h2>¿Cancelar esta reserva?</h2><p><strong>${escapeHTML(r.hotel)}</strong><br>${escapeHTML(r.room)}<br>${dateText(r.checkin)} – ${dateText(r.checkout)}<br>${escapeHTML(r.id)} · ${money(r.total)} COP</p><p class="modal-hint">La habitación quedará libre para otros huéspedes. Esta acción no se puede deshacer.</p><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button class="button secondary" id="keep-reservation">Volver</button><button class="button danger" id="confirm-cancel">Sí, cancelar</button></div>`);
  $('#keep-reservation').addEventListener('click', showReservations);
  $('#keep-reservation').focus();
  $('#confirm-cancel').addEventListener('click', (event) => withBusy(event.currentTarget, async () => {
    const result = await api(`/reservations/${encodeURIComponent(r.id)}/cancel`, {});
    try { await refreshAvailability(); } catch { /* La cancelación se conserva y será reconciliada. */ }
    await showReservations(); toast(result.status === 'Cancelando' ? 'Cancelación en proceso. Actualiza tus reservas para consultar el resultado.' : 'Reserva cancelada. Estamos preparando el aviso para tu correo.', result.status === 'Cancelando' ? 'info' : 'success');
  }));
}
async function showNotifications() {
  if (!state.user) return showAuth();
  openModal('<h2>Notificaciones</h2><p>Consultando el correo de tu cuenta…</p>');
  try {
    const data = await api('/notifications');
    const status = {vista_previa:'Disponible en Hotels',pendiente:'En cola',reintentando:'Reintentando entrega',error:'No se pudo entregar',aceptado_smtp:'Aceptado por el proveedor de correo'};
    openModal(`<p class="eyebrow">EL CORREO DE TUS RESERVAS</p><h2>Notificaciones</h2><p>${data.smtpConfigured ? 'Consulta los avisos enviados a tu correo. Si no ves un mensaje, revisa también la carpeta de spam. La aceptación del proveedor no confirma la entrega en tu bandeja.' : 'El envío por correo no está disponible en este momento. Puedes consultar tus avisos aquí.'}</p><button class="button secondary" id="refresh-notifications">Actualizar mensajes</button>${data.notifications.length ? data.notifications.map((n) => `<article class="notification-item"><h3>${escapeHTML(n.subject)}</h3><p>Para: ${escapeHTML(n.recipient)}</p><span class="mail-status">${status[n.status] || 'En proceso'}</span><pre>${escapeHTML(n.body)}</pre></article>`).join('') : '<div class="reservation-item"><p>Los mensajes nuevos pueden tardar unos segundos en aparecer. Pulsa «Actualizar mensajes» para consultarlos.</p></div>'}`);
    $('#refresh-notifications').addEventListener('click', showNotifications);
  } catch (error) { openModal(`<h2>Notificaciones</h2><p>${escapeHTML(error.message)}</p>`); }
}
$('#hotel-list').addEventListener('click', (event) => { const button = event.target.closest('[data-hotel]'); if (!button) return; state.selected = button.dataset.hotel; render(); toast('Habitación seleccionada. Revisa el resumen de tu estancia.'); });
$('#hotel-list').addEventListener('change', (event) => {
  const selector = event.target.closest('[data-room-hotel]'); if (!selector) return;
  state.roomChoice[selector.dataset.roomHotel] = selector.value; state.selected = selector.dataset.roomHotel; render();
});
$('.filters').addEventListener('click', (event) => { const button = event.target.closest('[data-filter]'); if (!button) return; state.filter = button.dataset.filter; document.querySelectorAll('[data-filter]').forEach((b) => { b.classList.toggle('active',b === button); b.setAttribute('aria-pressed',String(b === button)); }); render(); });
$('#sort').addEventListener('change', (event) => { state.sort = event.target.value; render(); });
$('#search-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const a = $('#checkin').value, b = $('#checkout').value;
  const length = (Date.parse(b+'T00:00:00Z')-Date.parse(a+'T00:00:00Z'))/86400000;
  if (a < hotelToday() || !Number.isFinite(length) || length < 1 || length > 30) { $('#search-error').textContent = 'Selecciona una estancia de 1 a 30 noches, con llegada desde hoy.'; $('#search-error').hidden = false; return; }
  $('#search-error').hidden = true;
  Object.assign(state,{checkin:a,checkout:b,guests:Number($('#guests').value)});
  if (state.online) { try { await refreshAvailability(); } catch (error) { toast(error.message, 'error'); } } else render();
  $('#hoteles').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
});
$('#checkin').addEventListener('change', () => { if (Number.isNaN(new Date($('#checkin').value+'T12:00:00').getTime())) return; $('#checkout').min = addDays($('#checkin').value, 1); });
$('#checkout').min = addDays($('#checkin').value, 1);
$('#reserve-button').addEventListener('click', showBooking);
$('#my-reservations').addEventListener('click', showReservations);
$('#notifications-button').addEventListener('click', showNotifications);
$('#login-button').addEventListener('click', showAccount);
render(); renderAccount();
(async () => {
  try { await refreshAvailability(); } catch { $('#connection-note').textContent = 'No pudimos actualizar la disponibilidad. Los datos visibles son una vista previa; vuelve a intentarlo antes de reservar.'; }
  try { const data = await api('/auth/me'); state.user = data.user; renderAccount(); } catch { /* Visitante sin sesión. */ }
})();
