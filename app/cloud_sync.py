"""Authenticated synchronization; session tokens live in the OS credential store."""
import json
import time
import uuid
import sqlite3
from contextlib import closing
from datetime import datetime
import keyring
import requests
from .cloud_bridge import export_cloud, apply_cloud, merge_copies, meta, put_meta, initialize_cloud_ids

URL='https://vqngomcfkijfjydzqebz.supabase.co'
PUBLIC_KEY='sb_publishable_TF3OUJo7PUxawlf6TCYn-A_ghBC3xgp'

class CloudSync:
    def __init__(self, db):
        self.db=db; self.session=None
        self.credential=str(db.path.resolve())

    def restore(self):
        value=keyring.get_password('AppGastos.Cloud',self.credential)
        self.session=json.loads(value) if value else None
        return self.session

    def _save_session(self, session):
        keyring.set_password('AppGastos.Cloud',self.credential,json.dumps(session))
        self.session=session

    def request(self,path,body=None,authenticated=False):
        headers={'apikey':PUBLIC_KEY,'Content-Type':'application/json'}
        if authenticated:headers['Authorization']='Bearer '+self.token()
        response=requests.request('GET' if body is None else 'POST',URL+path,json=body,headers=headers,timeout=20,allow_redirects=False)
        if not response.ok:
            if response.status_code==401:raise ValueError('La sesión venció. Volvé a iniciar sesión.')
            raise ValueError('No se pudo completar la conexión con Supabase (HTTP '+str(response.status_code)+').')
        return response.json() if response.content else None

    def login(self,email,password):
        session=self.request('/auth/v1/token?grant_type=password',{'email':email,'password':password})
        initialize_cloud_ids(self.db)
        bound=meta(self.db,'user')
        if bound and bound!=session['user']['id']:raise ValueError('Esta base está vinculada a otra cuenta. Usá una base distinta para otro usuario.')
        session['expires_at']=time.time()+session['expires_in'];self._save_session(session)
        return 'Sesión iniciada: '+email

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
