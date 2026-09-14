import {fresh,validate} from './model.mjs';
const request = r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
let connection;
async function open(){if(connection)return connection;const r=indexedDB.open('app-gastos-independent',1);r.onupgradeneeded=()=>r.result.createObjectStore('data');connection=await request(r);connection.onversionchange=()=>{connection.close();connection=null;};return connection;}
export async function read(){const db=await open();const result=await request(db.transaction('data').objectStore('data').get('state'));return result?validate(result):fresh();}
export async function mutate(fn){const db=await open();return new Promise((resolve,reject)=>{const tx=db.transaction('data','readwrite');const store=tx.objectStore('data');let result;const r=store.get('state');r.onsuccess=()=>{try{result=validate(fn(r.result||fresh()));store.put(result,'state');}catch(e){reject(e);tx.abort();}};tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('No se guardó el cambio.'));});}
