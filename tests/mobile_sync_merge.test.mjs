import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mergeCopies} from '../mobile/sync-merge.mjs';
import {fresh,validate} from '../mobile/model.mjs';
test('sync merges independent edits and preserves deletion relative to base',()=>{
 const base=fresh();base.extras=[{id:'a',app:'A',date:'2026-01-01',minutes:60,orders:1,amount:100},{id:'b',app:'B',date:'2026-01-01',minutes:60,orders:1,amount:100}];const local=structuredClone(base),remote=structuredClone(base);local.extras[0].amount=200;remote.extras=remote.extras.filter(x=>x.id!=='b');const result=mergeCopies(base,local,remote);assert.equal(result.conflicts.length,0);assert.deepEqual(result.merged.extras,[local.extras[0]]);validate(result.merged);
});
test('sync exposes concurrent edits and delete-versus-edit without overwriting',()=>{
 const base=fresh();base.accounts[0].initial=100;const local=structuredClone(base),remote=structuredClone(base);local.accounts[0].initial=200;remote.accounts[0].initial=300;assert.equal(mergeCopies(base,local,remote).conflicts.length,1);local.accounts=[];assert.equal(mergeCopies(base,local,remote).conflicts.length,1);
});
test('record object property ordering does not cause false conflicts',()=>{
 const base=fresh(),local=structuredClone(base),remote=structuredClone(base);remote.accounts[0]=Object.fromEntries(Object.entries(remote.accounts[0]).reverse());assert.equal(mergeCopies(base,local,remote).conflicts.length,0);
});
