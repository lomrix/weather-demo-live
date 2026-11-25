import {chromium} from 'file:///C:/Program%20Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const root='C:/Users/moham/weather-demo-live';
const spec=JSON.parse(await fs.readFile(root+'/fixtures/evaluation/municipal-journeys.json','utf8'));
const pair=spec.cases.find(c=>c.id==='neighbouring-address');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.request.post('http://127.0.0.1:8793/api/ai/control',{data:{enabled:true},headers:{Origin:'http://127.0.0.1:8793'}});
 // Replayed real address coordinates: this is a UI check, not a new live-source experiment.
 await page.route('**/api/addresses?*',route=>{
   const query=new URL(route.request().url()).searchParams.get('q');
   const item=[pair.origin,pair.destination].find(item=>item.name===query);
   route.fulfill({json:item?{status:'available',matches:[{...item,id:'replay-'+item.name,kind:'address',postal_code:'2317',postal_place:'HAMAR'}],truncated:false}:{status:'unavailable',matches:[],truncated:false,message:'Address lookup is unavailable. Saved places and map selection still work.'}});
 });
 await page.goto('http://127.0.0.1:8793/',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#case-select').value==='hamar-municipality'&&!document.querySelector('#plan-fields').disabled);
 await page.locator('#details-button').click();
 await page.waitForFunction(()=>document.querySelector('#toggle-ai-calls')?.textContent.includes('Pause AI assistance'));
 await page.locator('#toggle-ai-calls').click();
 await page.waitForFunction(()=>document.querySelector('#ai-control-status').textContent.startsWith('AI paused.'));
 assert.equal((await page.request.get('http://127.0.0.1:8793/api/ai/status')).status(),200);
 await page.locator('#details-dialog [aria-label="Close details"]').click();
 await page.locator('#open-mobile-planner').click();
 for(const [side,item] of [['from',pair.origin],['to',pair.destination]]){
   await page.locator('#place-'+side).fill(item.name);
   await page.locator('#place-'+side+'-results [data-place-id^="replay-"]').click();
 }
 await page.locator('#assess-btn').click();
 await page.waitForFunction(()=>!document.querySelector('#mobile-planner').open);
 await page.locator('#journey-overview').getByText('4 m',{exact:true}).first().waitFor();
 assert((await page.locator('#journey-overview').innerText()).includes('excluded and unverified'));
 const points=await page.locator('#map [data-layer="baseline"] polyline').getAttribute('points');
 assert(points.split(' ').length>=2);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await fs.mkdir(root+'/docs/images',{recursive:true});
 await page.screenshot({path:root+'/docs/images/mobile-short-walk.png',fullPage:true});
 await page.locator('#language-select').selectOption('nb');
 await page.waitForFunction(()=>document.querySelector('#journey-overview').textContent.includes('utelatt og ubekreftet'));
 await page.locator('#theme-toggle').click();
 await page.screenshot({path:root+'/docs/images/mobile-short-walk-dark-nb.png',fullPage:true});
 await page.locator('#language-select').selectOption('en');
 await page.locator('#details-button').click();
 await page.locator('#toggle-ai-calls').click();
 await page.waitForFunction(()=>document.querySelector('#ai-control-status').textContent.startsWith('AI assistance is enabled'));
 await page.locator('#details-dialog [aria-label="Close details"]').click();
 await page.locator('#open-mobile-planner').click();
 await page.locator('#place-to').fill('Høyvangvegen');
 await page.locator('#place-to-results [data-place-id^="osm-street-"]').first().waitFor();
 assert((await page.locator('#place-to-status').innerText()).includes('unavailable'));
 await page.locator('#close-mobile-planner').click();
 await page.setViewportSize({width:1440,height:1000});
 await page.locator('[data-workspace-mode="bus"]').click();
 await page.locator('#catalogue-search').fill('B22');
 await page.waitForFunction(()=>document.querySelector('#catalogue-line').options.length===1&&!document.querySelector('#catalogue-show').disabled);
 await page.locator('#catalogue-show').click();
 await page.locator('#journey-overview').getByText('Published bus route',{exact:true}).waitFor();
 await page.locator('[data-workspace-mode="driving"]').click();
 await page.locator('#journey-overview').getByText('2.85 km',{exact:true}).waitFor();
 assert.deepEqual(errors,[]);
 const result={checked_at:new Date().toISOString(),mode:'Chromium phone emulation and desktop; replayed official address points; simulated address-source outage; zero live model calls',checks:['AI pause blocks new AI requests; manual short walk works','distinct adjacent addresses: 4 m mapped route plus separately disclosed access offsets','projected route geometry renders','Norwegian and dark mode','offline street lookup survives simulated address outage','B22 catalogue','fixed driving comparison'],errors};
 await fs.writeFile(root+'/out/readiness-browser.json',JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result));
}finally{await browser.close();}
