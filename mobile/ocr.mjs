export async function scan(file,progress=()=>{}){
 if(file.size>20*1024*1024)throw Error('Elegí un archivo de hasta 20 MB.');
 const {default:Tesseract}=await import('./vendor/tesseract.js/dist/tesseract.esm.min.js');
 const {createWorker}=Tesseract;
 const root=new URL('./vendor/',import.meta.url);
 const worker=await createWorker('spa',1,{workerPath:new URL('tesseract.js/dist/worker.min.js',root).href,corePath:new URL('tesseract.js-core/',root).href,langPath:new URL('languages/',root).href,logger:m=>progress(`${m.status==='recognizing text'?'Reconociendo texto':'Preparando OCR'} ${Math.round((m.progress||0)*100)} %`)});
 let pdf,task;
 try{
  if(file.type==='application/pdf'||file.name.toLowerCase().endsWith('.pdf')){
   const pdfjs=await import('./vendor/pdfjs-dist/build/pdf.mjs');pdfjs.GlobalWorkerOptions.workerSrc=new URL('pdfjs-dist/build/pdf.worker.mjs',root).href;
   task=pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,wasmUrl:new URL('pdfjs-dist/wasm/',root).href,standardFontDataUrl:new URL('pdfjs-dist/standard_fonts/',root).href});pdf=await task.promise;
   if(pdf.numPages>10)throw Error('Esta versión admite hasta 10 páginas por PDF. Dividilo en partes.');
   const result=[];
   for(let i=1;i<=pdf.numPages;i++){progress(`Página ${i} de ${pdf.numPages}`);const page=await pdf.getPage(i);const base=page.getViewport({scale:1});const viewport=page.getViewport({scale:Math.min(2,2000/Math.max(base.width,base.height))});const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);await page.render({canvas,canvasContext:canvas.getContext('2d'),viewport}).promise;result.push((await worker.recognize(canvas)).data.text);canvas.width=canvas.height=0;page.cleanup();}return result.join('\n');
  }
  // Decodificar y reducir antes del OCR evita copias gigantes del bitmap.
  const url=URL.createObjectURL(file);let image;
  try{image=new Image();image.src=url;await image.decode();const scale=Math.min(1,2200/Math.max(image.naturalWidth,image.naturalHeight));const canvas=document.createElement('canvas');canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);return (await worker.recognize(canvas)).data.text;}finally{URL.revokeObjectURL(url);}
 }finally{await worker.terminate();if(task)await task.destroy();}
}
