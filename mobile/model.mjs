import {desktopCategories} from './design.mjs';
import {validatePlanning} from './planning.mjs';
export const VERSION = '0.2.0';
export const collections = ['accounts','categories','transactions','trips','extras','mileage','zones','deliveries'];
export const uid = () => crypto.randomUUID();
export const today = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
export const cents = value => { const n=Number(value); if(!Number.isFinite(n)) throw Error('Ingresá un importe válido.'); return Math.round(n*100); };
export function fresh(){return {format:'app-gastos-mobile',schema:1,accounts:[{id:'cash',name:'Efectivo',initial:0,type:'Efectivo',include:true,color:'#3DA477',icon:'coins'}],categories:structuredClone(desktopCategories),transactions:[],trips:[],extras:[],mileage:[],zones:[{id:'zone-1',name:'Zona 1',rate:0}],deliveries:[],recurring:[],installments:[],budgets:[],review:[],adjustments:[],workFields:[]};}
const integer=n=>Number.isSafeInteger(n)&&Math.abs(n)<1e14;
const validDate=s=>typeof s==='string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s)) && new Date(s).toISOString().slice(0,10)===s;
export function validate(s){
 if(s?.format!=='app-gastos-mobile'||s.schema!==1)throw Error('Respaldo móvil incompatible.');
 for(const key of collections){if(!Array.isArray(s[key])||s[key].length>100000)throw Error('Colección inválida: '+key);const seen=new Set();for(const r of s[key]){if(!r||typeof r.id!=='string'||! /^[a-zA-Z0-9:_-]+$/.test(r.id)||seen.has(r.id))throw Error('Identificador inválido o repetido.');seen.add(r.id);}}
 const has=(key,id)=>s[key].some(r=>r.id===id);
 const name=r=>{if(typeof r.name!=='string'||!r.name.trim()||r.name.length>200)throw Error('El nombre es obligatorio (máximo 200 caracteres).');};
 for(const a of s.accounts){name(a);if(!integer(a.initial))throw Error('Saldo inicial inválido.');}
 for(const c of s.categories){name(c);if(!['expense','income'].includes(c.kind))throw Error('Tipo de categoría inválido.');let parent=c.parent;const seen=new Set([c.id]);while(parent){const p=s.categories.find(x=>x.id===parent);if(!p||p.kind!==c.kind||seen.has(parent))throw Error('Jerarquía de categorías inválida.');seen.add(parent);parent=p.parent;}}
 for(const t of s.transactions){if(!validDate(t.date)||!integer(t.amount)||t.amount<=0||!has('accounts',t.account))throw Error('Revisá fecha, importe y cuenta.');if(!['expense','income','transfer'].includes(t.kind))throw Error('Tipo de movimiento inválido.');if(t.kind==='transfer'){if(!has('accounts',t.to)||t.to===t.account)throw Error('Elegí dos cuentas distintas.');}else{const c=s.categories.find(c=>c.id===t.category);if(t.category&&(!c||c.kind!==t.kind))throw Error('Elegí una categoría del tipo correcto.');}}
 for(const key of ['trips','extras','mileage','deliveries'])for(const r of s[key]){if(!validDate(r.date))throw Error('Fecha inválida.');}
 for(const r of s.trips){if(typeof r.client!=='string'||!r.client.trim()||!integer(r.amount)||r.amount<0||!Array.isArray(r.destinations)||r.destinations.some(x=>typeof x!=='string')||!integer(r.stops)||r.stops<1)throw Error('Datos del viaje inválidos.');}
 for(const r of s.extras){if(!r.app||!integer(r.minutes)||r.minutes<0||!integer(r.orders)||r.orders<0||!integer(r.amount)||r.amount<0)throw Error('Datos del extra inválidos.');}
 for(const r of s.mileage){if(!Number.isFinite(r.start)||!Number.isFinite(r.end)||r.start<0||r.end<r.start)throw Error('El odómetro final debe ser mayor o igual al inicial.');}
 if(new Set(s.mileage.map(r=>r.date)).size!==s.mileage.length)throw Error('Hay dos registros de kilometraje para el mismo día.');
 for(const z of s.zones){name(z);if(!integer(z.rate)||z.rate<0)throw Error('Tarifa inválida.');}
 for(const d of s.deliveries){if(!has('zones',d.zone)||!integer(d.amount)||d.amount<0)throw Error('Envío inválido.');}
 return validatePlanning(s);
}
export function rawBalance(s,id){return s.transactions.reduce((n,t)=>n+(t.to===id&&t.kind==='transfer'?t.amount:0)+(t.account===id?(t.kind==='income'?t.amount:-t.amount):0),(s.accounts.find(a=>a.id===id)?.initial||0)+(s.adjustments||[]).filter(a=>a.account===id).reduce((n,a)=>n+a.amount,0));}
export function balance(s,id){const value=rawBalance(s,id);return s.accounts.find(a=>a.id===id)?.type==='Tarjeta'?Math.min(0,value):value;}
export function historyRows(s){return (s.desktop_snapshot?.historical_monthly||[]).map(r=>({id:'history:'+r.id,kind:r.kind,date:`${r.year}-${String(r.month).padStart(2,'0')}-01`,amount:cents(r.amount),category:r.category_id!=null?'desktop:categories:'+r.category_id:(s.categories.find(c=>c.name===(r.subcategory_name||r.category_name)&&c.kind===r.kind)?.id||''),historical:true}));}
export function totals(s,month){const rows=[...s.transactions,...historyRows(s)].filter(t=>t.date.startsWith(month));const income=rows.filter(t=>t.kind==='income').reduce((n,t)=>n+t.amount,0);const expense=rows.filter(t=>t.kind==='expense').reduce((n,t)=>n+t.amount,0);return {income,expense,net:income-expense};}
export function upsert(s,key,row){const i=s[key].findIndex(r=>r.id===row.id);if(i<0)s[key].push(row);else s[key][i]=row;return validate(s);}
export function remove(s,key,id){
 if(['accounts','categories'].includes(key)&&['recurring','installments','budgets','adjustments'].some(k=>(s[k]||[]).some(r=>(key==='accounts'?(r.account===id||r.to===id):r.category===id))))throw Error('Hay registros vinculados. Modificalos primero.');
 if(key==='accounts'&&s.transactions.some(t=>t.account===id||t.to===id))throw Error('Esta cuenta tiene movimientos.');
 if(key==='categories'&&(s.transactions.some(t=>t.category===id)||s.categories.some(c=>c.parent===id)))throw Error('La categoría tiene movimientos o subcategorías.');
 if(key==='zones'&&s.deliveries.some(d=>d.zone===id))throw Error('La zona tiene envíos registrados.');
 s[key]=s[key].filter(r=>r.id!==id);return validate(s);
}
