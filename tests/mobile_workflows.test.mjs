import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fresh,validate} from '../mobile/model.mjs';
import {filterTransactions} from '../mobile/transactions-ui.mjs';
import {addDelivery,removeDelivery,setZoneRate,zoneRate,fieldSummary,moveCategory} from '../mobile/work-model.mjs';
test('combined movement filters include child categories and destination accounts',()=>{
 const s=fresh();s.categories=[{id:'a',kind:'expense'},{id:'b',parent:'a',kind:'expense'}];s.accounts=[{id:'cash',name:'Efectivo'},{id:'bank',name:'Banco'}];s.transactions=[{id:'1',kind:'expense',date:'2026-01-02',amount:100,account:'cash',category:'b',description:'Café'},{id:'2',kind:'transfer',date:'2026-01-03',amount:500,account:'cash',to:'bank'},{id:'3',kind:'expense',date:'2025-12-01',amount:600,account:'cash',category:'b'}];
 assert.deepEqual(filterTransactions(s,{month:'2026-01',category:'a',query:'cafe',min:50,max:200}).map(t=>t.id),['1']);
 assert.deepEqual(filterTransactions(s,{account:'bank'}).map(t=>t.id),['2']);assert.deepEqual(filterTransactions(s,{from:'2025-12-01',until:'2026-01-03',sort:'amount-desc'}).map(t=>t.id),['3','2','1']);
});
test('Flex rates apply by date; removing one from imported batch preserves others',()=>{
 const s=fresh(),z=s.zones[0];z.rate=499000;setZoneRate(z,'2026-02-01',599000);assert.equal(zoneRate(z,'2026-01-10'),499000);addDelivery(s,z.id,'2026-01-10','old');addDelivery(s,z.id,'2026-02-10','new');setZoneRate(z,'2026-02-01',699000);assert.equal(s.deliveries[1].amount,599000);
 s.deliveries.push({id:'batch',zone:z.id,date:'2026-02-11',quantity:3,amount:1800000});removeDelivery(s,z.id,'2026-02-01','2026-02-28');assert.deepEqual(s.deliveries.at(-1),{id:'batch',zone:z.id,date:'2026-02-11',quantity:2,amount:1200000});validate(s);
});
test('custom summaries and category moves do not copy records',()=>{
 assert.equal(fieldSummary({id:'x',type:'check'},[{custom:{x:true}},{custom:{x:1}},{custom:{x:false}}]),2);
 assert.equal(fieldSummary({id:'x',type:'number'},[{custom:{x:'20'}},{custom:{x:'abc'}},{}]),20);
 const s=fresh();s.categories=[{id:'a',kind:'expense'},{id:'b',kind:'expense',parent:'a'},{id:'c',kind:'expense',parent:'b'}];assert.throws(()=>moveCategory(s,'a','c'));moveCategory(s,'c','a');assert.equal(s.categories.length,3);assert.equal(s.categories[2].parent,'a');
});
