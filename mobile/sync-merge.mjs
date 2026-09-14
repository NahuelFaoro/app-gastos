// Three-way record merge. Deletion is represented by absence relative to base.
// Never use device clocks or silently prefer a conflicting financial value.
export const syncCollections=['accounts','categories','transactions','trips','extras','mileage','zones','deliveries','recurring','installments','budgets','review','adjustments','workFields'];
export function canonical(value){if(value===undefined)return 'undefined';if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).filter(k=>value[k]!==undefined).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
export function mergeCopies(base,local,remote){
 const merged=structuredClone(local),conflicts=[];
 for(const collection of syncCollections){
  const index=s=>new Map((s?.[collection]||[]).map(r=>[r.id,r])),b=index(base),l=index(local),r=index(remote),result=[];
  for(const id of new Set([...l.keys(),...r.keys(),...b.keys()])){
   const original=b.get(id),left=l.get(id),right=r.get(id);let value;
   if(canonical(left)===canonical(right))value=left;
   else if(canonical(left)===canonical(original))value=right;
   else if(canonical(right)===canonical(original))value=left;
   else {conflicts.push({collection,id,base:original??null,local:left??null,remote:right??null});value=left;}
   if(value!==undefined)result.push(structuredClone(value));
  }
  merged[collection]=result;
 }
 // Preserve desktop-only records; concurrent edits to that snapshot require review.
 for(const key of ['desktop_snapshot']){
  if(canonical(local[key])===canonical(base?.[key]))merged[key]=structuredClone(remote[key]);
  else if(canonical(remote[key])!==canonical(base?.[key])&&canonical(local[key])!==canonical(remote[key]))conflicts.push({collection:key,id:key,base:base?.[key]??null,local:local[key]??null,remote:remote[key]??null});
 }
 return {merged,conflicts};
}
