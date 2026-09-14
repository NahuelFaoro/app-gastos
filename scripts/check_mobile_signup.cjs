const {chromium}=require(process.env.PLAYWRIGHT_PATH||'C:/Users/nnfao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:320,height:740}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let calls=0,reply,release;
 await page.route('https://vqngomcfkijfjydzqebz.supabase.co/**',async route=>{
  if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'*'}});
  calls++;assert.equal(new URL(route.request().url()).pathname,'/auth/v1/signup');
  await new Promise(resolve=>release=resolve);
  await route.fulfill({status:reply.status,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(reply.body)});
 });
 try{
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8767/');
  await page.locator('#bottom-nav [data-view=more]').click();await page.locator('#content [data-view=settings]').click();
  await page.locator('[data-cloud=signup]').click();await page.getByRole('heading',{name:'Crear tu cuenta',exact:true}).waitFor();assert.equal(calls,0);
  await page.locator('[data-cloud=register]').click();await page.getByRole('alert').filter({hasText:'email válida'}).waitFor();assert.equal(calls,0);
  await page.locator('#cloud-email').fill('signup@example.invalid');await page.locator('#cloud-password').fill('Synthetic-Test-Only');await page.locator('#cloud-password-confirm').fill('Different-Test-Only');
  await page.locator('[data-cloud=register]').click();await page.getByRole('alert').filter({hasText:'no coinciden'}).waitFor();assert.equal(calls,0);
  await page.locator('#cloud-password-confirm').fill('Synthetic-Test-Only');await page.locator('[data-cloud=register]').click();
  await page.getByText('Creando tu cuenta…',{exact:true}).waitFor();assert.equal(await page.locator('[data-cloud=register]').isDisabled(),true);
  while(!release)await new Promise(r=>setTimeout(r,10));reply={status:400,body:{code:'email_address_not_authorized'}};release();release=null;
  await page.getByRole('alert').filter({hasText:'servicio de emails'}).waitFor();assert.equal(await page.locator('#cloud-email').inputValue(),'signup@example.invalid');assert.equal(await page.locator('#cloud-password').inputValue(),'Synthetic-Test-Only');
  await page.locator('#cloud-password-confirm').press('Enter');while(!release)await new Promise(r=>setTimeout(r,10));reply={status:200,body:{id:'synthetic-user'}};release();
  await page.getByRole('status').filter({hasText:'Solicitud recibida'}).waitFor();assert.equal(await page.locator('#cloud-password').inputValue(),'');assert.equal(calls,2);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);console.log('SIGNUP_FORM_VALIDATION_PENDING_ERROR_AND_SUCCESS_OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
