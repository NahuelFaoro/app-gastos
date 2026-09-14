import {canonical,mergeCopies} from './sync-merge.mjs';
import {validate} from './model.mjs';
export class SyncConflict extends Error {constructor(conflicts){super('Hay cambios simultáneos para revisar.');this.conflicts=conflicts;}}
export async function synchronize({client,transaction,operation=()=>crypto.randomUUID()}){
 const initial=await transaction();if(!initial.meta.enabled)return {disabled:true};
 const remote=await client.copy(),server=remote?.document||initial.meta.base||initial.state;
 const {merged,conflicts}=mergeCopies(initial.meta.base,initial.state,server);
 if(conflicts.length)throw new SyncConflict(conflicts);validate(merged);
 let revision=remote?.revision||0;
 if(!remote||canonical(merged)!==canonical(server)){
  const result=await client.save(merged,revision,operation());
  if(!result.ok)throw Error('Otro dispositivo acaba de guardar. Volvé a sincronizar para recibir sus cambios.');revision=result.revision;
 }
 await transaction(current=>{const latest=mergeCopies(initial.state,current.state,merged);if(latest.conflicts.length)throw new SyncConflict(latest.conflicts);validate(latest.merged);return {state:latest.merged,meta:{...current.meta,base:merged,revision,lastSync:new Date().toISOString()}};});
 return {revision};
}
