/* Administración: las APIs verifican el rol en cada operación. */
const select = (query) => document.querySelector(query);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const currency = (value) => new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(value);
const data = { hotels:[],rooms:[],guests:[],inventory:[] };
const names = {hotels:'hotel',rooms:'habitación',guests:'huésped'};
const newNames = {hotels:'Nuevo hotel',rooms:'Nueva habitación',guests:'Nuevo huésped'};
let tab = 'hotels';
let editorOpener = null;

async function request(path,method='GET',body) {
  let response;
  try { response = await fetch('/api'+path,{method,credentials:'same-origin',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)}); }
  catch { throw new Error('No hay conexión con Hotels. Inténtalo de nuevo.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
  return result;
}

function showStatus(message) { select('#admin-status').textContent = message; }
function showEditor(title,html) {
  editorOpener = document.activeElement;
  select('#editor-body').innerHTML = `<h2 id="editor-title">${escapeHTML(title)}</h2>${html}`;
  select('#admin-editor').showModal();
  const first = select('#editor-body input:not(:disabled), #editor-body select, #editor-body button');
  first?.focus();
}
select('#close-editor').addEventListener('click',()=>select('#admin-editor').close());
select('#admin-editor').addEventListener('close',()=>{ if(editorOpener?.isConnected) editorOpener.focus(); });

async function reload() {
  const [hotels,rooms,guests,inventory] = await Promise.all([request('/hotels?includeInactive=true'),request('/rooms?includeInactive=true'),request('/guests'),request('/inventory')]);
  Object.assign(data,{hotels:hotels.hotels,rooms:rooms.rooms,guests:guests.guests,inventory:inventory.inventory});
  select('#admin-stats').innerHTML = [['hotels','Hoteles activos'],['rooms','Habitaciones activas'],['guests','Huéspedes activos']].map(([key,label])=>`<div><strong>${data[key].filter(r=>r.active).length}</strong><span>${label}</span></div>`).join('');
  render();
}

function render() {
  select('#add-record').textContent = newNames[tab];
  document.querySelectorAll('[data-tab]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.tab===tab)));
  const query = select('#admin-search').value.trim().toLocaleLowerCase('es');
  const rows = data[tab].filter(r=>(r.active || select('#include-archived').checked) && [r.name,r.email,r.address,r.area,data.hotels.find(h=>h.id===r.hotelId)?.name].filter(Boolean).join(' ').toLocaleLowerCase('es').includes(query));
  select('#admin-records').innerHTML = rows.length ? rows.map(row=>{
    let description;
    if(tab==='hotels') description=`${escapeHTML(row.address)}<br>${escapeHTML(row.area)}<br>${data.rooms.filter(r=>r.hotelId===row.id).length} tipos de habitación`;
    if(tab==='rooms') description=`${escapeHTML(data.hotels.find(h=>h.id===row.hotelId)?.name || row.hotelId)}<br>Hasta ${row.capacity} huéspedes · ${currency(row.price)} / noche<br>${data.inventory.find(i=>i.roomId===row.id)?.total ?? 'Pendiente'} unidades · ${row.inventory_ready?'Inventario sincronizado':'Alta de inventario pendiente'}`;
    if(tab==='guests') description=`${escapeHTML(row.email)}<br>${escapeHTML(row.phone || 'Sin teléfono registrado')}<br>${row.user_id?'Cuenta vinculada':'Sin cuenta de acceso'}`;
    return `<article class="admin-record"><div class="admin-record-header"><h2>${escapeHTML(row.name)}</h2><span class="admin-pill ${row.active?'':'off'}">${row.active?'Activo':'Inactivo'}</span></div><p>${description}</p><div class="admin-record-actions"><button data-action="edit" data-id="${escapeHTML(row.id)}">Editar</button>${tab==='rooms'?`<button data-action="inventory" data-id="${escapeHTML(row.id)}" ${row.inventory_ready?'':'disabled'}>Inventario</button>`:''}<button data-action="${row.active?'archive':'restore'}" data-id="${escapeHTML(row.id)}">${row.active?'Retirar':'Reactivar'}</button></div></article>`;
  }).join('') : '<p class="admin-empty">No hay registros con estos criterios.</p>';
}

const input = (name,label,value='',type='text',extra='')=>`<label>${label}<input name="${name}" type="${type}" value="${escapeHTML(value)}" ${extra}></label>`;
function fields(row) {
  if(tab==='hotels') return input('name','Nombre',row?.name,'text','required maxlength="120"')+input('area','Sector',row?.area,'text','required maxlength="100"')+input('address','Dirección',row?.address,'text','required maxlength="180"')+`<label>Descripción<textarea name="description" required maxlength="1000">${escapeHTML(row?.description)}</textarea></label>`+input('source','Sitio oficial o de referencia',row?.source,'url','required')+input('amenities','Comodidades separadas por comas',row?.amenities?.join(', '),'text','maxlength="600"')+`<label>Servicios<select name="services" multiple aria-label="Servicios del hotel"><option value="wifi" ${row?.tags.includes('wifi')?'selected':''}>Wi-Fi</option><option value="restaurant" ${row?.tags.includes('restaurant')?'selected':''}>Restaurante</option><option value="work" ${row?.tags.includes('work')?'selected':''}>Zona de trabajo</option></select></label><p class="modal-hint">Se conserva la fotografía ilustrativa con su crédito. Las habitaciones y unidades se administran por separado.</p>`;
  if(tab==='rooms') return row ? input('name','Nombre del tipo',row.name,'text','required maxlength="120"')+input('capacity','Capacidad',row.capacity,'number','required min="1" max="20"')+input('price','Tarifa por noche en COP',row.price,'number','required min="1" max="100000000"') : `<label>Hotel<select name="hotelId" required><option value="">Seleccionar hotel</option>${data.hotels.filter(h=>h.active).map(h=>`<option value="${escapeHTML(h.id)}">${escapeHTML(h.name)}</option>`).join('')}</select></label>`+input('name','Nombre del tipo','','text','required maxlength="120"')+input('capacity','Capacidad',2,'number','required min="1" max="20"')+input('price','Tarifa por noche en COP','','number','required min="1" max="100000000"')+input('total','Unidades iniciales',1,'number','required min="1" max="1000"');
  return input('name','Nombre completo',row?.name,'text','required minlength="2" maxlength="80"')+input('email','Correo electrónico',row?.email,'email',`required maxlength="254" ${row?.user_id?'disabled':''}`)+input('phone','Teléfono',row?.phone,'tel','maxlength="30"')+`<p class="modal-hint">${row?.user_id?'El correo vinculado al acceso se conserva. Al retirar este huésped se revocan sus sesiones.':'Este registro no crea una contraseña ni envía un correo. El huésped podrá registrarse en Hotels con esta dirección.'}</p>`;
}

function edit(row) {
  showEditor(row?`Editar ${names[tab]}`:newNames[tab],`<form class="admin-form" id="edit-form">${fields(row)}<p class="form-error" role="alert" id="editor-error"></p><button type="submit" class="button primary">Guardar ${names[tab]}</button></form>`);
  select('#edit-form').addEventListener('submit',event=>{
    event.preventDefault();
    const form = new FormData(event.target), body = Object.fromEntries(form);
    if(tab==='hotels') { body.tags=form.getAll('services'); delete body.services; body.amenities=body.amenities.split(',').map(v=>v.trim()).filter(Boolean); }
    if(tab==='rooms') { for(const key of ['capacity','price','total']) if(key in body) body[key]=Number(body[key]); }
    save(event.target.querySelector('button[type=submit]'),`/${tab}${row?'/'+encodeURIComponent(row.id):''}`,row?'PATCH':'POST',body);
  });
}

async function save(button,path,method,body) {
  button.disabled=true;
  try {
    const result=await request(path,method,body);
    select('#admin-editor').close();
    await reload();
    showStatus(result.room?.inventory_ready===false?'Habitación guardada. El alta de inventario sigue en proceso; pulsa Actualizar para consultar el estado.':'Cambio guardado correctamente.');
  } catch(error) { if(select('#admin-editor').open) select('#editor-error').textContent=error.message; else showStatus(error.message); }
  finally { if(button.isConnected) button.disabled=false; }
}

function archive(row,restore) {
  showEditor(`${restore?'Reactivar':'Retirar'} ${names[tab]}`,`<p>${escapeHTML(row.name)}</p><p>${restore?'El registro volverá a estar activo.':'Se retirará del uso futuro. El historial de reservas se conserva.'}</p><form class="admin-form" id="archive-form"><p class="form-error" id="editor-error" role="alert"></p><button type="submit" class="button primary">${restore?'Reactivar':'Confirmar retiro'}</button></form>`);
  select('#archive-form').addEventListener('submit',event=>{event.preventDefault();save(event.target.querySelector('button'),`/${tab}/${encodeURIComponent(row.id)}`,restore?'PATCH':'DELETE',restore?{active:true}:undefined);});
}

function inventory(row) {
  const total=data.inventory.find(i=>i.roomId===row.id)?.total ?? 1;
  showEditor('Unidades de inventario',`<p>${escapeHTML(row.name)}</p><p>No se puede reducir el inventario por debajo de las unidades comprometidas por reservas vigentes.</p><form class="admin-form" id="inventory-form">${input('total','Unidades disponibles en el inventario',total,'number','required min="1" max="1000"')}<p class="form-error" id="editor-error" role="alert"></p><button type="submit" class="button primary">Guardar inventario</button></form>`);
  select('#inventory-form').addEventListener('submit',event=>{event.preventDefault();save(event.target.querySelector('button'),'/inventory/'+encodeURIComponent(row.id),'PUT',{total:Number(new FormData(event.target).get('total'))});});
}

document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{tab=button.dataset.tab;select('#admin-search').value='';render();}));
select('#admin-search').addEventListener('input',render);
select('#include-archived').addEventListener('change',render);
select('#add-record').addEventListener('click',()=>edit(null));
select('#reload-records').addEventListener('click',async()=>{try{await reload();showStatus('Datos actualizados.');}catch(error){showStatus(error.message);}});
select('#admin-records').addEventListener('click',event=>{
  const button=event.target.closest('button[data-action]');if(!button)return;
  const row=data[tab].find(r=>r.id===button.dataset.id);if(!row)return;
  if(button.dataset.action==='edit')edit(row);
  else if(button.dataset.action==='inventory')inventory(row);
  else archive(row,button.dataset.action==='restore');
});
(async()=>{
  try {
    const {user}=await request('/auth/me');
    if(user.role!=='admin')throw new Error('Esta sección requiere una cuenta administradora. Regresa a Hotels para gestionar tus reservas.');
    select('#admin-user').textContent=user.name;
    await reload();select('#admin-workspace').hidden=false;showStatus('');
  }catch(error){select('#admin-user').textContent='Acceso restringido';showStatus(error.message+' Inicia sesión desde la página principal.');}
})();
