const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const {chromium}=require(path.join(ROOT,'frontend/node_modules/@playwright/test'));
const AxeBuilder=require(path.join(ROOT,'frontend/node_modules/@axe-core/playwright')).default;
const fs=require('node:fs');
const target=path.join(ROOT,'docs/screenshots');
fs.mkdirSync(target,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata'});
 const page=await context.newPage();
 const report={page_errors:[],accessibility:[],responsive:[]};
 page.on('pageerror',e=>report.page_errors.push(e.message));
 const shot=async(name)=>page.screenshot({path:target+'/'+name+'.png',fullPage:true,animations:'disabled'});
 const audit=async(name)=>{const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();report.accessibility.push({page:name,violations:result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>n.target)}))})};
 const nav=async(name)=>{if(page.viewportSize().width<=760)await page.getByRole('button',{name:'Open navigation'}).click();const pattern=new RegExp('^'+name+'(?: \\d+)?$');await page.getByRole('navigation',{name:'Project navigation'}).getByRole('button',{name:pattern}).click();await page.getByRole('heading',{level:1}).waitFor();};
 await page.goto('http://127.0.0.1:5173');await page.getByRole('button',{name:'View demo'}).waitFor();await shot('landing');await audit('landing');
 await page.getByRole('button',{name:'View demo'}).click();await page.getByRole('heading',{name:'Complaint workspace',exact:true}).waitFor();await shot('overview');await audit('overview');
 for(const name of ['Claim Ledger','Evidence','Ask Project','Consistency','Viva','Documentation','Deployment Audit','Settings']){
  await nav(name);
  if(name==='Ask Project'){await page.getByRole('button',{name:'Which database does this project use?'}).click();await page.getByText('The project references PostgreSQL in its source or configuration.').waitFor();}
  if(name==='Viva'){await page.getByRole('combobox',{name:'Examiner perspective'}).selectOption('ADVERSARIAL EXAMINER');await page.getByRole('button',{name:'Start practice'}).click();await page.getByRole('button',{name:'Reveal suggested answer'}).click();}
  if(name==='Documentation'){await page.getByRole('combobox',{name:'Output format'}).selectOption('presentation');await page.getByRole('button',{name:'Generate draft'}).click();await page.locator('.document-preview pre').waitFor();}
  if(name==='Evidence')await page.getByLabel('Source code').waitFor();
  await shot(name.toLowerCase().replaceAll(' ','-'));await audit(name);
 }
 await nav('Overview');await page.getByRole('button',{name:'Toggle color theme'}).click();await shot('overview-light');await audit('overview-light');await page.getByRole('button',{name:'Toggle color theme'}).click();
 for(const width of [320,390,768,1024]){
  await page.setViewportSize({width,height:844});
  for(const name of ['Overview','Claim Ledger','Evidence','Ask Project','Consistency','Viva','Documentation','Deployment Audit','Settings']){
   await nav(name);
   const sizes=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));report.responsive.push({page:name,width,...sizes});
   if(width===390&&['Overview','Claim Ledger','Evidence'].includes(name))await shot('mobile-'+name.toLowerCase().replaceAll(' ','-'));
  }
 }
 fs.writeFileSync(path.join(ROOT,'docs/ui-review-results.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({page_errors:report.page_errors,accessibility:report.accessibility.filter(a=>a.violations.length),overflow:report.responsive.filter(r=>r.document>r.viewport)},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
