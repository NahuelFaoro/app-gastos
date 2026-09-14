// Local calendar dates: never shift a selected day through UTC.
const dateOf=value=>new Date(value+'T12:00:00');
const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export function periodRange(mode,anchor){
 const d=dateOf(anchor);
 if(mode==='month')return [iso(new Date(d.getFullYear(),d.getMonth(),1,12)),iso(new Date(d.getFullYear(),d.getMonth()+1,0,12))];
 d.setDate(d.getDate()-(d.getDay()+6)%7);const start=iso(d);d.setDate(d.getDate()+6);return [start,iso(d)];
}
export function shiftPeriod(mode,anchor,delta){const d=dateOf(anchor);if(mode==='month'){d.setDate(1);d.setMonth(d.getMonth()+delta);}else d.setDate(d.getDate()+7*delta);return iso(d);}
export function periodLabel(mode,anchor){const [a,b]=periodRange(mode,anchor);const format=v=>dateOf(v).toLocaleDateString('es-AR',{day:'2-digit',month:'short'});return mode==='month'?dateOf(a).toLocaleDateString('es-AR',{month:'long',year:'numeric'}):`${format(a)} — ${format(b)} · ${b.slice(0,4)}`;}
export function periodControls(mode,anchor,scope='month'){
 return `<div class="period-control" data-period-scope="${scope}"><button data-action="period-prev" data-scope="${scope}" aria-label="Período anterior">‹</button><label class="period-label"><span>${periodLabel(mode,anchor)}</span><input id="${scope==='work'?'work-date':'month'}" aria-label="${scope==='work'?'Ir a fecha':'Mes'}" type="${scope==='work'?'date':'month'}" value="${scope==='work'?anchor:anchor.slice(0,7)}"></label><button data-action="period-next" data-scope="${scope}" aria-label="Período siguiente">›</button><button data-action="period-today" data-scope="${scope}">Hoy</button></div>`;
}
