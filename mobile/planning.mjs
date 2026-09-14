// Fechas sin UTC y centavos enteros, equivalentes al calendario del escritorio.
export function advance(date,frequency='monthly',interval=1,anchor=Number(date.slice(8))){
 const [y,m,d]=date.split('-').map(Number);let result;
 if(frequency==='daily'||frequency==='weekly'){result=new Date(y,m-1,d+interval*(frequency==='weekly'?7:1),12);}
 else {result=new Date(y,m-1+interval*(frequency==='yearly'?12:1),1,12);result.setDate(Math.min(anchor,new Date(result.getFullYear(),result.getMonth()+1,0).getDate()));}
 return `${result.getFullYear()}-${String(result.getMonth()+1).padStart(2,'0')}-${String(result.getDate()).padStart(2,'0')}`;
}
export function dueItems(s,until){
 const result=[];
 for(const r of s.recurring||[]){if(!r.active)continue;let date=r.next_date;let count=0;while(date<=until&&count++<500){result.push({...r,id:`recurring:${r.id}:${date}`,source:r.id,sourceType:'recurring',date});date=advance(date,r.frequency,r.interval,r.anchor);}}
 for(const p of s.installments||[]){if(!p.active)continue;for(let n=p.next_number;n<=p.count;n++){const date=p.next_date?advance(p.next_date,'monthly',n-p.next_number,Number(p.next_date.slice(8))):advance(p.first_date,'monthly',n-1,Number(p.first_date.slice(8)));if(date>until)break;const base=p.base??Math.floor(p.total/p.count);result.push({...p,id:`installment:${p.id}:${n}`,source:p.id,sourceType:'installments',date,kind:'expense',amount:n===p.count?p.total-base*(p.count-1):base,number:n});}}
 return result.sort((a,b)=>a.date.localeCompare(b.date));
}
export function registerDue(s,until){
 const items=dueItems(s,until);
 for(const item of items){
  if(!s.transactions.some(t=>t.id===item.id))s.transactions.push({id:item.id,kind:item.kind,amount:item.amount,account:item.account,to:item.to||'',category:item.category||'',date:item.date,description:item.description||item.name||'',note:item.note||'',recurring:item.sourceType==='recurring'?item.source:null,installment:item.sourceType==='installments'?item.source:null,number:item.number||null});
  const source=s[item.sourceType].find(r=>r.id===item.source);
  if(item.sourceType==='recurring')source.next_date=advance(item.date,source.frequency,source.interval,source.anchor);
  else {if(source.next_date)source.next_date=advance(item.date,'monthly',1,Number(source.first_date.slice(8)));source.next_number=item.number+1;source.active=source.next_number<=source.count;}
 }
 return s;
}
export function descendants(s,id){const result=new Set([id]);let previous;do{previous=result.size;for(const c of s.categories)if(result.has(c.parent))result.add(c.id);}while(result.size!==previous);return result;}
export function categoryPath(s,id){const parts=[],seen=new Set();while(id&&!seen.has(id)){seen.add(id);const c=s.categories.find(c=>c.id===id);if(!c)break;parts.unshift(c.name);id=c.parent;}return parts.join(' / ');}
export function validatePlanning(s){
 const date=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 const money=v=>Number.isSafeInteger(v)&&v>0&&v<1e14;
 for(const key of ['recurring','installments','budgets','review','adjustments','workFields']){s[key]??=[];if(!Array.isArray(s[key]))throw Error('Colección inválida: '+key);const ids=new Set();for(const r of s[key]){if(!r||typeof r.id!=='string'||! /^[a-zA-Z0-9:_-]+$/.test(r.id)||ids.has(r.id))throw Error('Identificador inválido en '+key);ids.add(r.id);}}
 for(const key of ['recurring','installments'])for(const r of s[key]){
  if(!s.accounts.some(a=>a.id===r.account))throw Error('Elegí una cuenta válida.');
  const kind=key==='installments'?'expense':r.kind;
  if(!['expense','income','transfer'].includes(kind))throw Error('Tipo inválido.');
  if(kind==='transfer'){if(r.to===r.account||!s.accounts.some(a=>a.id===r.to))throw Error('Elegí una cuenta de destino distinta.');}
  else if(r.category&&!s.categories.some(c=>c.id===r.category&&c.kind===kind))throw Error('Elegí una categoría del tipo correcto.');
  if(key==='recurring'&&(!money(r.amount)||!date(r.next_date)||!['daily','weekly','monthly','yearly'].includes(r.frequency)||!Number.isInteger(r.interval)||r.interval<1||r.interval>365||!Number.isInteger(r.anchor)||r.anchor<1||r.anchor>31))throw Error('Revisá importe, frecuencia y fecha.');
  if(key==='installments'&&(!money(r.total)||!date(r.first_date)||!Number.isInteger(r.count)||r.count<2||r.count>360||r.total<r.count||!Number.isInteger(r.next_number)||r.next_number<1||r.next_number>r.count+1))throw Error('Revisá el importe y las cuotas.');
 }
 for(const b of s.budgets)if(!b.name?.trim()||!money(b.amount)||!date(b.date)||(b.account&&!s.accounts.some(a=>a.id===b.account))||(b.category&&!s.categories.some(c=>c.id===b.category&&c.kind==='expense')))throw Error('Presupuesto inválido.');
 for(const r of s.adjustments)if(!date(r.date)||!Number.isSafeInteger(r.amount)||!s.accounts.some(a=>a.id===r.account))throw Error('Ajuste inválido.');
 for(const f of s.workFields)if(!f.name?.trim()||!['check','text','number','money','email','tel','options'].includes(f.type))throw Error('Campo personalizado inválido.');
 return s;
}
