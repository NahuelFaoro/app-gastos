import {cloudURL,publishableKey} from './cloud-config.mjs';
export function authErrorMessage(result,status){
 const code=result.code||result.error_code;
 if(code==='email_address_not_authorized')return 'El registro no pudo enviar el correo: falta habilitar el servicio de emails de App Gastos para esta dirección. No es un problema de tu contraseña.';
 if(code==='over_email_send_rate_limit'||status===429)return 'Se alcanzó el límite temporal de intentos o correos. Esperá antes de volver a intentarlo.';
 if(code==='email_not_confirmed')return 'Confirmá tu email antes de iniciar sesión. Revisá también la carpeta de spam.';
 if(code==='invalid_credentials')return 'El email o la contraseña no son correctos.';
 if(status===401)return 'La sesión venció. Volvé a iniciar sesión.';
 return result.msg||result.message||result.error_description||'No se pudo conectar con la nube. Volvé a intentar.';
}
export class CloudClient {
 constructor({fetcher=(...args)=>fetch(...args),url=cloudURL,key=publishableKey,onSession=()=>{}}={}){this.fetcher=fetcher;this.url=url;this.key=key;this.session=null;this.onSession=onSession;this.refreshing=null;}
 async request(path,body,token,method){const response=await this.fetcher(this.url+path,{method:method||(body===undefined?'GET':'POST'),headers:{apikey:this.key,'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body===undefined?{}:{body:JSON.stringify(body)}),cache:'no-store',signal:AbortSignal.timeout(20000)});const result=await response.json().catch(()=>({}));if(!response.ok){const error=new Error(authErrorMessage(result,response.status));error.status=response.status;throw error;}return result;}
 async setSession(session){this.session=session;await this.onSession(session);return session;}
 async login(email,password){const s=await this.request('/auth/v1/token?grant_type=password',{email,password});return this.setSession({...s,expires_at:Date.now()/1000+s.expires_in});}
 async signup(email,password){return this.request('/auth/v1/signup',{email,password});}
 async verify(email,token){const s=await this.request('/auth/v1/verify',{email,token,type:'signup'});return this.setSession({...s,expires_at:Date.now()/1000+s.expires_in});}
 async token(){if(!this.session)throw Error('Iniciá sesión para sincronizar.');if(this.session.expires_at>Date.now()/1000+60)return this.session.access_token;if(!this.refreshing)this.refreshing=this.request('/auth/v1/token?grant_type=refresh_token',{refresh_token:this.session.refresh_token}).then(s=>this.setSession({...s,expires_at:Date.now()/1000+s.expires_in})).finally(()=>this.refreshing=null);return (await this.refreshing).access_token;}
 async copy(){const token=await this.token();const rows=await this.request('/rest/v1/app_gastos_copies?select=revision,document&limit=1',undefined,token);return rows[0]||null;}
 async save(document,revision,operation){const token=await this.token();return this.request('/rest/v1/rpc/save_app_gastos_copy',{payload:document,expected_revision:revision,request_id:operation},token);}
 async logout(){try{if(this.session)await this.request('/auth/v1/logout?scope=local',{},await this.token());}finally{await this.setSession(null);}}
}
