import {test} from 'node:test';
import assert from 'node:assert/strict';
import {periodRange,shiftPeriod} from '../mobile/periods.mjs';
import {dashboardData} from '../mobile/dashboard.mjs';
import {fresh} from '../mobile/model.mjs';
test('weeks cross year boundaries and months include leap days',()=>{
 assert.deepEqual(periodRange('week','2026-01-01'),['2025-12-29','2026-01-04']);
 assert.deepEqual(periodRange('month','2024-02-19'),['2024-02-01','2024-02-29']);
 assert.equal(shiftPeriod('month','2026-01-31',1),'2026-02-01');
 assert.equal(shiftPeriod('week','2026-01-01',-1),'2025-12-25');
});
test('dashboard includes descendants and uncategorized amounts without double counting',()=>{
 const s=fresh();s.categories=[{id:'home',name:'Casa',kind:'expense'},{id:'services',name:'Servicios',parent:'home',kind:'expense'},{id:'wifi',name:'Wifi',parent:'services',kind:'expense'}];
 s.transactions=[{kind:'expense',category:'wifi',date:'2026-01-10',amount:200},{kind:'expense',category:'',date:'2026-01-10',amount:50},{kind:'income',date:'2026-01-10',amount:900}];
 const {groups,trend}=dashboardData(s,'2026-01');assert.deepEqual(groups.map(g=>[g.name,g.total]),[['Casa',200],['Sin categoría',50]]);
 assert.equal(trend[0].month,'2025-08');assert.equal(trend[5].expense,250);assert.equal(trend[5].income,900);
});
