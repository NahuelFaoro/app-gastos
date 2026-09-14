import test from 'node:test';
import assert from 'node:assert/strict';
import {fresh,validate} from '../mobile/model.mjs';
import {advance,registerDue,dueItems} from '../mobile/planning.mjs';
const category=()=>fresh().categories.find(c=>c.name==='Comida').id;
test('recurrentes mensuales preservan el día ancla después de febrero',()=>{
 assert.equal(advance('2026-01-31','monthly',1,31),'2026-02-28');
 assert.equal(advance('2026-02-28','monthly',1,31),'2026-03-31');
 const s=fresh();s.recurring.push({id:'rent',amount:10000,account:'cash',category:category(),kind:'expense',next_date:'2026-01-31',frequency:'monthly',interval:1,anchor:31,active:true});
 registerDue(s,'2026-03-31');validate(s);assert.equal(s.transactions.length,3);registerDue(s,'2026-03-31');assert.equal(s.transactions.length,3);assert.equal(s.recurring[0].next_date,'2026-04-30');
});
test('cuotas suman el importe original y no se duplican al registrar otra vez',()=>{
 const s=fresh();s.installments.push({id:'plan',account:'cash',category:category(),total:10000,count:3,first_date:'2026-01-31',next_number:1,active:true});
 registerDue(s,'2026-12-31');validate(s);assert.equal(s.transactions.reduce((n,t)=>n+t.amount,0),10000);assert.equal(s.transactions.length,3);assert.equal(s.installments[0].active,false);registerDue(s,'2026-12-31');assert.equal(s.transactions.length,3);
});
test('respaldo inicial se amplía sin eliminar registros anteriores',()=>{
 const s=fresh();delete s.recurring;delete s.installments;delete s.budgets;delete s.review;delete s.workFields;delete s.adjustments;const id=s.accounts[0].id;validate(s);assert.equal(s.accounts[0].id,id);assert.deepEqual(s.recurring,[]);
});
test('planes rechazan fechas, cuentas y cantidades inválidas',()=>{
 const s=fresh();s.installments.push({id:'bad',account:'cash',category:category(),total:1000,count:0,first_date:'2026-01-01',next_number:1,active:true});assert.throws(()=>validate(s));
});
