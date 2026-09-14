import {CloudClient} from './cloud-client.mjs';
import {synchronize} from './sync-engine.mjs';
import {canonical} from './sync-merge.mjs';
import {read,mutate,useWorkspace,currentWorkspace,localValue,syncTransaction} from './storage.mjs';
import {fresh,validate} from './model.mjs';
import {esc} from './desktop-ui.mjs';
let recovering=false;
let authMode='login',authBusy=false,authEmail='';
let status='',working=false,enabled=false,conflicts=[];
let changed=()=>{};
const sessions=typeof BroadcastChannel==='function'?new BroadcastChannel('ag-cloud-session'):null;
sessions?.addEventListener('message',()=>location.reload());
export const cloudClient=new CloudClient({onSession:s=>localValue('auth-session',s)});
export async function initializeCloud(callback){
 changed=callback;cloudClient.session=await localValue('auth-session')||null;
 const hash=new URLSearchParams(location.hash.slice(1));
 if(hash.has('access_token')&&hash.has('refresh_token')){
  recovering=hash.get('type')==='recovery';const token=hash.get('access_token');history.replaceState(null,'',location.pathname+location.search);
  try{const user=await cloudClient.request('/auth/v1/user',undefined,token);await cloudClient.setSession({access_token:token,refresh_token:hash.get('refresh_token'),expires_at:Date.now()/1000+Number(hash.get('expires_in')||3600),user});}catch{status='No se pudo confirmar la cuenta. Iniciá sesión nuevamente.';}
 }
 if(cloudClient.session){useWorkspace(cloudClient.session.user.id);enabled=!!(await syncTransaction()).meta.enabled;}
 window.addEventListener('online',()=>syncNow());
 setInterval(()=>{if(document.visibilityState==='visible'&&enabled)syncNow();},60000);
 document.addEventListener('click',handleClick);
 document.addEventListener('submit',event=>{if(event.target.id==='cloud-auth-form'){event.preventDefault();handleAuth(authMode==='signup'?'register':'login');}});
 if(enabled)setTimeout(()=>syncNow(),1500);
 return hash.has('access_token');
}
async function backup(value){
 const key='backup:'+currentWorkspace()+':'+Date.now();
 await localValue(key,value);await localValue('last-backup:'+currentWorkspace(),key);
}
export function cloudPanel(){
 const user=cloudClient.session?.user;
 if(user&&recovering)return `<section class="card cloud-panel"><h2>Nueva contraseña</h2><label>Contraseña nueva<input type="password" id="cloud-new-password" autocomplete="new-password" minlength="8"></label><button data-cloud="password" class="primary">Guardar contraseña</button><p role="status">${esc(status)}</p></section>`;
 if(!user)return `<section class="card cloud-panel cloud-auth"><h2>${authMode==='signup'?'Crear tu cuenta':'Tu cuenta · PC y teléfonos'}</h2><p>${authMode==='signup'?'Usá un email al que tengas acceso. Te enviaremos un enlace para confirmarlo.':'Iniciá sesión con la misma cuenta en tus dispositivos. Tu copia sin cuenta permanece separada.'}</p><form id="cloud-auth-form" novalidate><label>Email<input id="cloud-email" type="email" autocomplete="email" autocapitalize="none" spellcheck="false" required value="${esc(authEmail)}"></label><label>Contraseña<input id="cloud-password" type="password" autocomplete="${authMode==='signup'?'new-password':'current-password'}" minlength="8" required aria-describedby="cloud-password-help"></label><small id="cloud-password-help">Al menos 8 caracteres.</small>${authMode==='signup'?'<label>Repetir contraseña<input id="cloud-password-confirm" type="password" autocomplete="new-password" required></label>':''}<p id="cloud-auth-status" class="cloud-auth-status" role="status" aria-live="polite" tabindex="-1" ${status?'':'hidden'}>${esc(status)}</p><div class="cloud-auth-actions"><button type="submit" data-cloud="${authMode==='signup'?'register':'login'}" class="primary">${authMode==='signup'?'Registrarme':'Iniciar sesión'}</button><button type="button" data-cloud="${authMode==='signup'?'show-login':'signup'}">${authMode==='signup'?'Ya tengo cuenta':'Crear cuenta'}</button></div>${authMode==='login'?'<button type="button" class="quiet" data-cloud="recover">Olvidé mi contraseña</button>':''}</form></section>`;
 return `<section class="card cloud-panel"><h2>Cuenta y sincronización</h2><p>${esc(user.email)}</p><span class="badge">${enabled?'Sincronización activada':'Copia privada en este dispositivo'}</span><p class="muted">${enabled?'Los cambios se guardan primero aquí y se envían al conectarse.':'Activá para enviar esta copia a tu espacio privado en Supabase y recibir la de tus otros dispositivos.'}</p><div class="toolbar"><button data-cloud="${enabled?'sync':'enable'}" class="primary" ${working?'disabled':''}>${working?'Sincronizando…':enabled?'Sincronizar ahora':'Activar sincronización'}</button>${enabled?'<button data-cloud="pause">Pausar</button>':''}<button data-cloud="logout" ${working?'disabled':''}>Cerrar sesión</button></div><button class="quiet" data-cloud="bring-local">Traer mi copia sin cuenta</button><button class="quiet" data-cloud="backup">Descargar respaldo anterior</button><p role="status">${esc(status)}</p>${conflicts.length?`<p>Se conservaron ambas copias. Revisá estos registros antes de continuar:</p><ul>${conflicts.map(c=>`<li>${esc(c.collection)} · ${esc(c.local?.description||c.local?.name||c.local?.client||c.remote?.description||c.remote?.name||c.id)}</li>`).join('')}</ul><p class="muted">Exportá un respaldo antes de resolver. Cada botón conserva una copia completa y guarda la otra como respaldo local.</p><div class="toolbar"><button data-cloud="keep-local">Conservar esta copia</button><button data-cloud="keep-remote">Conservar la nube</button></div>`:''}</section>`;
}
export function scheduleSync(){clearTimeout(scheduleSync.timer);if(enabled)scheduleSync.timer=setTimeout(()=>syncNow(),2500);}
export async function syncNow(){
 if(working||!enabled||!cloudClient.session||!navigator.onLine||conflicts.length)return;
 working=true;const key=currentWorkspace();status='Sincronizando…';
 try{
  const run=async()=>{cloudClient.session=await localValue('auth-session');if(!cloudClient.session||'user:'+cloudClient.session.user.id!==key)throw Error('La sesión cambió. Volvé a abrir la app.');await synchronize({client:cloudClient,transaction:fn=>{if(currentWorkspace()!==key)throw Error('La cuenta cambió durante la sincronización.');return syncTransaction(fn);}});};
  if(navigator.locks)await navigator.locks.request('ag-cloud-sync',run);else await run();
  status='Sincronizado · '+new Date().toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'});
 }catch(e){status=e.message||'Sin conexión. Tus cambios siguen guardados aquí.';conflicts=e.conflicts||[];}
 finally{working=false;await changed();}
}
function authFeedback(message,error=false){
 status=message;const output=document.getElementById('cloud-auth-status');if(!output)return;
 output.textContent=message;output.hidden=false;output.classList.toggle('negative',error);output.setAttribute('role',error?'alert':'status');output.scrollIntoView({block:'nearest'});
}
async function handleAuth(action){
 if(authBusy)return;
 const emailInput=document.getElementById('cloud-email'),passwordInput=document.getElementById('cloud-password');
 authEmail=emailInput.value.trim();emailInput.value=authEmail;
 if(!authEmail||!emailInput.validity.valid){authFeedback('Ingresá una dirección de email válida.',true);emailInput.focus();return;}
 const password=passwordInput.value;
 if(action!=='recover'&&password.length<8){authFeedback('La contraseña debe tener al menos 8 caracteres.',true);passwordInput.focus();return;}
 if(action==='register'&&password!==document.getElementById('cloud-password-confirm').value){authFeedback('Las contraseñas no coinciden.',true);return;}
 authBusy=true;const buttons=[...document.querySelectorAll('.cloud-auth button')];buttons.forEach(b=>b.disabled=true);
 authFeedback(action==='register'?'Creando tu cuenta…':action==='recover'?'Solicitando el correo…':'Iniciando sesión…');
 try{
  if(action==='recover'){await cloudClient.request('/auth/v1/recover',{email:authEmail});authFeedback('Si la cuenta existe, recibirás un correo para recuperar el acceso.');return;}
  if(action==='register'){
   const result=await cloudClient.signup(authEmail,password);
   if(!result.access_token){passwordInput.value='';document.getElementById('cloud-password-confirm').value='';authFeedback('Solicitud recibida. Revisá tu correo y la carpeta de spam para confirmar tu cuenta; después elegí «Ya tengo cuenta».');return;}
   await cloudClient.setSession({...result,expires_at:Date.now()/1000+result.expires_in});
  }else await cloudClient.login(authEmail,password);
  passwordInput.value='';useWorkspace(cloudClient.session.user.id);enabled=!!(await syncTransaction()).meta.enabled;
  status='Sesión iniciada. Tu copia anterior sigue disponible al cerrar sesión.';sessions?.postMessage('changed');await changed();
 }catch(e){authFeedback(e.message||'No se pudo completar la operación. Volvé a intentar.',true);}
 finally{authBusy=false;buttons.forEach(b=>b.disabled=false);}
}
async function handleClick(event){
 const button=event.target.closest('[data-cloud]');if(!button||working)return;const action=button.dataset.cloud;
 if(authBusy)return;
 if(['signup','show-login'].includes(action)){authEmail=document.getElementById('cloud-email')?.value.trim()||'';authMode=action==='signup'?'signup':'login';status='';await changed();document.getElementById('cloud-email')?.focus();return;}
 if(['login','register','recover'].includes(action)){event.preventDefault();await handleAuth(action);return;}
 try{
  if(action==='password'){const password=document.getElementById('cloud-new-password').value;if(password.length<8)throw Error('Usá al menos 8 caracteres.');await cloudClient.request('/auth/v1/user',{password},await cloudClient.token(),'PUT');recovering=false;status='Contraseña actualizada.';}
  if(action==='logout'){try{await cloudClient.logout();}finally{useWorkspace(null);enabled=false;conflicts=[];status='Sesión cerrada.';sessions?.postMessage('changed');}}
  if(action==='pause'){await syncTransaction(c=>({...c,meta:{...c.meta,enabled:false}}));enabled=false;status='Pausada. Los cambios nuevos se guardan en este dispositivo.';}
  if(action==='enable'){
   if(!confirm('La sincronización enviará tus registros de esta cuenta a tu espacio privado en Supabase. ¿Activar?'))return;
   const remote=await cloudClient.copy(),current=await syncTransaction();
   if(!current.meta.base&&remote){
    if(canonical(current.state)!==canonical(fresh())&&!confirm('La nube ya tiene una copia. Se guardará un respaldo local antes de abrirla. ¿Continuar?'))return;
    validate(remote.document);await backup(current.state);
    await syncTransaction(c=>({state:remote.document,meta:{...c.meta,enabled:true,base:remote.document,revision:remote.revision}}));
   }else await syncTransaction(c=>({...c,meta:{...c.meta,enabled:true}}));
   enabled=true;conflicts=[];await syncNow();
  }
  if(action==='backup'){
   const key=await localValue('last-backup:'+currentWorkspace()),value=key&&await localValue(key);
   if(!value)throw Error('Todavía no hay un respaldo anterior de esta cuenta.');
   for(const [name,copy] of value.format?[['copia',value]]:Object.entries(value)){
    const url=URL.createObjectURL(new Blob([JSON.stringify(copy,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='AppGastos-respaldo-'+name+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   }
  }
  if(action==='sync')await syncNow();
  if(action==='bring-local'){
   if(!confirm('Esto reemplaza la copia de esta cuenta en el dispositivo por tu copia sin cuenta. Se respaldará la actual y se pausará la sincronización. ¿Continuar?'))return;
   const guest=await localValue('state')||fresh(),current=await read();validate(guest);await backup(current);
   await syncTransaction(c=>({state:guest,meta:{...c.meta,enabled:false}}));enabled=false;status='Copia local incorporada. Activá la sincronización cuando quieras enviarla.';
  }
  if(action==='keep-local'||action==='keep-remote'){
   if(!confirm('¿Resolver usando la copia completa elegida? La otra quedará respaldada en este dispositivo.'))return;
   const remote=await cloudClient.copy();if(!remote)throw Error('No hay copia remota.');validate(remote.document);const current=await read();
   await backup({local:current,remote:remote.document});
   await syncTransaction(c=>({state:action==='keep-local'?c.state:remote.document,meta:{...c.meta,base:remote.document,revision:remote.revision}}));conflicts=[];await syncNow();
  }
 }catch(e){status=e.message||'No se pudo completar la operación.';}
 finally{button.disabled=false;await changed();}
}
