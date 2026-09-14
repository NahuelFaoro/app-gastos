export const VERSION = '0.1.0';
export const collections = ['accounts','categories','transactions','trips','extras','mileage','zones','deliveries'];
export const uid = () => crypto.randomUUID();
export const today = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
export const cents = value => { const n=Number(value); if(!Number.isFinite(n)) throw Error('Ingresá un importe válido.'); return Math.round(n*100); };
export function fresh(){return {format:'app-gastos-mobile',schema:1,accounts:[{id:'cash',name:'Efectivo',initial:0}],categories:[['food','Comida','expense'],['home','Casa','expense'],['transport','Transporte','expense'],['health','Salud','expense'],['other','Otros','expense'],['salary','Sueldo','income'],['work','Trabajo','income']].map(([id,name,kind])=>({id,name,kind,parent:''})),transactions:[],trips:[],extras:[],mileage:[],zones:[{id:'zone-1',name:'Zona 1',rate:0}],deliveries:[]};}
const integer=n=>Number.isSafeInteger(n)&&Math.abs(n)<1e14;
const validDate=s=>typeof s==='string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s)) && new Date(s).toISOString().slice(0,10)===s;
export function validate(s){
 if(s?.format!=='app-gastos-mobile'||s.schema!==1)throw Error('Respaldo móvil incompatible.');
 for(const key of collections){if(!Array.isArray(s[key])||s[key].length>100000)throw Error('Colección inválida: '+key);const seen=new Set();for(const r of s[key]){if(!r||typeof r.id!=='string'||!r.id||seen.has(r.id))throw Error('Identificador inválido o repetido.');seen.add(r.id);}}
 const has=(key,id)=>s[key].some(r=>r.id===id);
 const name=r=>{if(typeof r.name!=='string'||!r.name.trim()||r.name.length>200)throw Error('El nombre es obligatorio (máximo 200 caracteres).');};
 for(const a of s.accounts){name(a);if(!integer(a.initial))throw Error('Saldo inicial inválido.');}
 for(const c of s.categories){name(c);if(!['expense','income'].includes(c.kind))throw Error('Tipo de categoría inválido.');let parent=c.parent;const seen=new Set([c.id]);while(parent){const p=s.categories.find(x=>x.id===parent);if(!p||p.kind!==c.kind||seen.has(parent))throw Error('Jerarquía de categorías inválida.');seen.add(parent);parent=p.parent;}}
 for(const t of s.transactions){if(!validDate(t.date)||!integer(t.amount)||t.amount<=0||!has('accounts',t.account))throw Error('Revisá fecha, importe y cuenta.');if(!['expense','income','transfer'].includes(t.kind))throw Error('Tipo de movimiento inválido.');if(t.kind==='transfer'){if(!has('accounts',t.to)||t.to===t.account)throw Error('Elegí dos cuentas distintas.');}else{const c=s.categories.find(c=>c.id===t.category);if(!c||c.kind!==t.kind)throw Error('Elegí una categoría del tipo correcto.');}}
 for(const key of ['trips','extras','mileage','deliveries'])for(const r of s[key]){if(!validDate(r.date))throw Error('Fecha inválida.');}
 for(const r of s.trips){if(typeof r.client!=='string'||!r.client.trim()||!integer(r.amount)||r.amount<0||!Array.isArray(r.destinations)||r.destinations.some(x=>typeof x!=='string')||!integer(r.stops)||r.stops<1)throw Error('Datos del viaje inválidos.');}
 for(const r of s.extras){if(!r.app||!integer(r.minutes)||r.minutes<0||!integer(r.orders)||r.orders<0||!integer(r.amount)||r.amount<0)throw Error('Datos del extra inválidos.');}
 for(const r of s.mileage){if(!Number.isFinite(r.start)||!Number.isFinite(r.end)||r.start<0||r.end<r.start)throw Error('El odómetro final debe ser mayor o igual al inicial.');}
 if(new Set(s.mileage.map(r=>r.date)).size!==s.mileage.length)throw Error('Hay dos registros de kilometraje para el mismo día.');
 for(const z of s.zones){name(z);if(!integer(z.rate)||z.rate<0)throw Error('Tarifa inválida.');}
 for(const d of s.deliveries){if(!has('zones',d.zone)||!integer(d.amount)||d.amount<0)throw Error('Envío inválido.');}
 return s;
}
export function balance(s,id){return s.transactions.reduce((n,t)=>n+(t.to===id&&t.kind==='transfer'?t.amount:0)+(t.account===id?(t.kind==='income'?t.amount:-t.amount):0),s.accounts.find(a=>a.id===id)?.initial||0);}
export function totals(s,month){const rows=s.transactions.filter(t=>t.date.startsWith(month));const income=rows.filter(t=>t.kind==='income').reduce((n,t)=>n+t.amount,0);const expense=rows.filter(t=>t.kind==='expense').reduce((n,t)=>n+t.amount,0);return {income,expense,net:income-expense};}
export function upsert(s,key,row){const i=s[key].findIndex(r=>r.id===row.id);if(i<0)s[key].push(row);else s[key][i]=row;return validate(s);}
export function remove(s,key,id){
 if(key==='accounts'&&s.transactions.some(t=>t.account===id||t.to===id))throw Error('Esta cuenta tiene movimientos.');
 if(key==='categories'&&(s.transactions.some(t=>t.category===id)||s.categories.some(c=>c.parent===id)))throw Error('La categoría tiene movimientos o subcategorías.');
 if(key==='zones'&&s.deliveries.some(d=>d.zone===id))throw Error('La zona tiene envíos registrados.');
 s[key]=s[key].filter(r=>r.id!==id);return validate(s);
}
