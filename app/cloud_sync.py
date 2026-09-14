"""Authenticated synchronization; session tokens live in the OS credential store."""
import json
import time
import uuid
import sqlite3
import re
from contextlib import closing
from datetime import datetime
import keyring
import requests
from .cloud_bridge import export_cloud, apply_cloud, merge_copies, meta, put_meta, initialize_cloud_ids
from .constants import APP_VERSION

URL='https://vqngomcfkijfjydzqebz.supabase.co'
PUBLIC_KEY='sb_publishable_TF3OUJo7PUxawlf6TCYn-A_ghBC3xgp'

def cloud_error(response):
    try:
        payload=response.json()
    except ValueError:
        payload={}
    code=(payload.get('error_code') or payload.get('code')) if isinstance(payload,dict) else None
    messages={
        'email_not_confirmed':'Tu email todavía no está confirmado. Abrí el enlace del correo de App Gastos antes de iniciar sesión.',
        'invalid_credentials':'No se pudo validar la cuenta de App Gastos. Revisá el email y la contraseña. La cuenta del panel de Supabase es independiente; si aún no te registraste en App Gastos, elegí «Crear o confirmar cuenta en la app».',
        'email_address_not_authorized':'No se pudo enviar el correo a esta dirección: falta configurar el servicio de emails de App Gastos.',
        'signup_disabled':'El registro de nuevas cuentas está deshabilitado en el servidor.',
        'user_banned':'Esta cuenta está temporalmente bloqueada por el servidor.',
        'over_request_rate_limit':'Hubo demasiados intentos. Esperá unos minutos antes de volver a iniciar sesión.',
        'over_email_send_rate_limit':'Se alcanzó el límite de correos de confirmación. Esperá antes de volver a intentarlo.',
        'refresh_token_not_found':'La sesión guardada venció. Volvé a iniciar sesión.',
        'refresh_token_already_used':'La sesión guardada ya no es válida. Volvé a iniciar sesión.',
    }
    if code in messages:return messages[code]
    if response.status_code==429:return 'Hubo demasiados intentos. Esperá unos minutos antes de volver a intentar.'
    if response.status_code==401:return 'La sesión venció. Volvé a iniciar sesión.'
    return 'No se pudo completar la conexión con Supabase (HTTP '+str(response.status_code)+').'

class CloudSync:
    def __init__(self, db):
        self.db=db; self.session=None; self.session_persistent=False
        self.credential=str(db.path.resolve())

    def restore(self):
        value=keyring.get_password('AppGastos.Cloud',self.credential)
        self.session=json.loads(value) if value else None
        self.session_persistent=bool(self.session)
        return self.session

    def _save_session(self, session):
        # Windows limits each credential to 2560 bytes (keyring writes UTF-16).
        # The full Supabase response includes a JWT and repeated user metadata.
        # Persist only what is needed to renew it; keep the access token in RAM.
        saved={'refresh_token':session['refresh_token'],
               'user':{'id':session['user']['id'],'email':session['user'].get('email','')},
               'expires_at':0}
        self.session=session
        self.session_persistent=False
        try:
            value=json.dumps(saved,ensure_ascii=False,separators=(',',':'))
            if len(value.encode('utf-16-le'))>2560:raise ValueError('Credential too large')
            keyring.set_password('AppGastos.Cloud',self.credential,value)
            self.session_persistent=True
        except Exception:
            # A local vault failure must not undo successful authentication.
            # Never fall back to storing session secrets in an unencrypted file.
            pass

    def request(self,path,body=None,authenticated=False):
        headers={'apikey':PUBLIC_KEY,'Content-Type':'application/json','X-Client-Info':'app-gastos-desktop/'+APP_VERSION}
        if authenticated:headers['Authorization']='Bearer '+self.token()
        response=requests.request('GET' if body is None else 'POST',URL+path,json=body,headers=headers,timeout=20,allow_redirects=False)
        if not response.ok:
            message=cloud_error(response)
            # Correlate failures with server logs without recording credentials or tokens.
            reference=response.headers.get('sb-request-id','')
            if isinstance(reference,str) and re.fullmatch(r'[0-9a-fA-F-]{36}',reference):
                message+='\nReferencia Desktop '+APP_VERSION+': '+reference
            raise ValueError(message)
        return response.json() if response.content else None

    def login(self,email,password):
        email=email.strip().lower()
        if not email or '@' not in email:raise ValueError('Ingresá el email de tu cuenta de App Gastos.')
        if not password:raise ValueError('Ingresá tu contraseña de App Gastos.')
        session=self.request('/auth/v1/token?grant_type=password',{'email':email,'password':password})
        initialize_cloud_ids(self.db)
        bound=meta(self.db,'user')
        if bound and bound!=session['user']['id']:raise ValueError('Esta base está vinculada a otra cuenta. Usá una base distinta para otro usuario.')
        session['expires_at']=time.time()+session['expires_in'];self._save_session(session)
        message='Sesión iniciada: '+email
        if not self.session_persistent:
            message+=' · Windows no pudo recordar la sesión. Podés usarla ahora; al cerrar la app tendrás que volver a ingresar.'
        return message

    def token(self):
        if not self.session:raise ValueError('Iniciá sesión primero.')
        if self.session.get('expires_at',0)<time.time()+60:
            s=self.request('/auth/v1/token?grant_type=refresh_token',{'refresh_token':self.session['refresh_token']})
            s['expires_at']=time.time()+s['expires_in'];self._save_session(s)
        return self.session['access_token']

    def logout(self):
        try:
            if self.session:self.request('/auth/v1/logout?scope=local',{},True)
        finally:
            try:keyring.delete_password('AppGastos.Cloud',self.credential)
            except keyring.errors.PasswordDeleteError:pass
            self.session=None;self.db.set_setting('cloud_enabled','0')
        return 'Sesión cerrada. La copia de Desktop sigue intacta.'

    def backup(self):
        target=self.db.path.parent/'backups';target.mkdir(exist_ok=True)
        path=target/('antes-sync-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
        with closing(sqlite3.connect(self.db.path)) as source,closing(sqlite3.connect(path)) as destination:source.backup(destination)
        return path

    def remote(self):
        rows=self.request('/rest/v1/app_gastos_copies?select=revision,document&limit=1',authenticated=True)
        return rows[0] if rows else None

    def sync(self,enable=False):
        if not self.session:raise ValueError('Iniciá sesión primero.')
        initialize_cloud_ids(self.db)
        bound=meta(self.db,'user')
        if bound and bound!=self.session['user']['id']:raise ValueError('La cuenta no coincide con esta base.')
        local=export_cloud(self.db);base=meta(self.db,'base');remote=self.remote()
        if base is None:
            if remote:raise ValueError('La nube ya tiene datos. Para vincular esta PC, usá «Recibir copia de la nube» y revisá el respaldo que se genera.')
            if not enable:raise ValueError('Activá la sincronización desde esta PC.')
            self.backup()
        merged,conflicts=merge_copies(base,local,remote['document'] if remote else local)
        if conflicts:raise ValueError('Cambios simultáneos: '+', '.join(k for k,_ in conflicts[:5])+'. Usá las opciones de resolución para conservar la copia elegida.')
        revision=remote['revision'] if remote else 0
        if not remote or merged!=remote['document']:
            result=self.request('/rest/v1/rpc/save_app_gastos_copy',{'payload':merged,'expected_revision':revision,'request_id':str(uuid.uuid4())},True)
            if not result['ok']:raise ValueError('Otro dispositivo guardó cambios. Reintentá la sincronización.')
            revision=result['revision']
        apply_cloud(self.db,merged,local,merged,revision)
        with self.db.connect() as c:put_meta(c,'user',self.session['user']['id'])
        if enable:self.db.set_setting('cloud_enabled','1')
        return 'Sincronizado · '+datetime.now().strftime('%H:%M')

    def resolve(self,choice):
        if not self.session:raise ValueError('Iniciá sesión primero.')
        initialize_cloud_ids(self.db);bound=meta(self.db,'user')
        if bound and bound!=self.session['user']['id']:raise ValueError('La cuenta no coincide con esta base.')
        remote=self.remote()
        if not remote:raise ValueError('Todavía no hay copia en la nube.')
        backup=self.backup();backup.with_suffix('.cloud.json').write_text(json.dumps(remote['document'],ensure_ascii=False),encoding='utf-8');local=export_cloud(self.db)
        if choice=='remote':
            # Desktop-only historical/import configuration cannot be replaced partially.
            snapshot=remote['document'].get('desktop_snapshot')
            exclusive=('historical_imports','historical_monthly','import_rules','imported_movements','work_rate_schemes','work_rate_options','flex_income_links')
            if snapshot and any(snapshot.get(k,[])!=(local.get('desktop_snapshot') or {}).get(k,[]) for k in exclusive):
                raise ValueError('Esta copia contiene histórico o configuración exclusiva de otra base Desktop. No se puede reemplazar parcialmente; conservamos el respaldo y no modificamos tus registros.')
            apply_cloud(self.db,remote['document'],local,remote['document'],remote['revision'])
        else:
            with self.db.connect() as c:put_meta(c,'base',remote['document'])
            self.sync(enable=True)
        with self.db.connect() as c:put_meta(c,'user',self.session['user']['id'])
        self.db.set_setting('cloud_enabled','1')
        return 'Copia conservada y sincronización activada.'
