const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'C:/Users/nnfao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.BASE_URL || 'http://127.0.0.1:8767/';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1});
 const page=await context.newPage(),errors=[],external=[];
 page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')console.log('BROWSER',m.text());});page.on('requestfailed',r=>console.log('REQUEST_FAILED',r.url(),r.failure()));
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(base))external.push(r.url());});
 try {
 await page.goto(base);
 await page.getByRole('button',{name:'＋ Movimiento',exact:true}).waitFor();
 await page.evaluate(()=>navigator.serviceWorker.ready);
 await page.waitForFunction(()=>navigator.serviceWorker.controller!==null);
 await page.getByRole('button',{name:'＋ Movimiento',exact:true}).click();
 await page.locator('[name=amount]').fill('1234.50');
 await page.locator('[name=description]').fill('Compra de prueba');
 await page.getByRole('button',{name:'Guardar',exact:true}).click();
 await page.waitForFunction(()=>!document.querySelector('dialog').open);
 assert.equal(await page.evaluate(async()=>{const {read}=await import('./storage.mjs');return (await read()).transactions.length;}),1);
 await context.setOffline(true);await page.reload();
 await page.getByText('Compra de prueba',{exact:true}).waitFor();
 console.log('OFFLINE_RELOAD_AND_PERSISTENCE_OK');
 await page.getByRole('button',{name:'Trabajo',exact:true}).click();
 await page.getByRole('button',{name:'＋ Registro',exact:true}).click();
 await page.locator('[name=client]').fill('Cliente móvil');await page.locator('[name=destinations]').fill('Olivos\nRetiro');
 await page.locator('[name=stops]').fill('2');await page.getByRole('button',{name:'Guardar',exact:true}).click();
 await page.locator('summary').filter({hasText:'Cliente móvil'}).click();
 await page.locator('[data-check=flex]').check();
 await page.waitForFunction(async()=>{const {read}=await import('./storage.mjs');return (await read()).trips[0]?.flex;});
 await page.reload();await page.getByRole('button',{name:'Trabajo',exact:true}).click();
 await page.getByText('Cliente móvil',{exact:true}).waitFor();
 console.log('OFFLINE_TRIPS_OK');
 for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`);await page.screenshot({path:`build/mobile-${width}.png`,fullPage:true});}
 await page.getByRole('button',{name:'Inicio',exact:true}).click();
 for(const ext of ['png','pdf']){
 await page.locator('#scan-file').setInputFiles(`build/mobile-receipt.${ext}`);
 await page.waitForFunction(()=>document.querySelector('dialog').open||document.querySelector('#toast').textContent.startsWith('No se pudo leer'),null,{timeout:120000});
 assert(await page.locator('dialog').evaluate(d=>d.open),await page.locator('#toast').textContent());
 const note=await page.locator('[name=note]').inputValue();assert.match(note,/TOTAL/i);assert.match(note,/1234/);
 console.log('OFFLINE_OCR_'+ext.toUpperCase()+'_OK');await page.locator('#close').click();
 }
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
 console.log('APP_GASTOS_MOBILE_OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
