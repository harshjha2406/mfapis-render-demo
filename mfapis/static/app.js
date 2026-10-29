'use strict';
const $ = id => document.getElementById(id);
const names = {IND:'India',USA:'United States',GBR:'United Kingdom'};
const config = {
  worldbank:{name:'Macroeconomics',provider:'WORLD BANK',title:'GDP growth',description:'Annual percentage change in gross domestic product.',label:'Country',frequency:'Annual',default:'IND',url:'https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG',note:'December 31 labels the annual period; it is not the publication date. Only India, the United States and the United Kingdom are included.'},
  ecb:{name:'Foreign exchange',provider:'EUROPEAN CENTRAL BANK',title:'Exchange-rate history',description:'Daily reference rates: units of the selected currency per one euro.',label:'Currency pair',frequency:'Daily reference',default:'EUR/USD',url:'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html',note:'Source data are available free from the ECB. MFAPIs normalizes these observations. Informational reference rates are not executable trading prices.'},
  treasury:{name:'Treasury yields',provider:'U.S. DEPARTMENT OF THE TREASURY',title:'Treasury yield history',description:'Daily nominal par yields for a selected U.S. Treasury maturity.',label:'Maturity',frequency:'Daily',default:'par_yield_10Y',url:'https://home.treasury.gov/resource-center-data-chart-center/interest-rates',note:'Values are annual percentages: 4.2 means 4.2%. These are nominal par curve observations, not individual bond prices or zero-coupon yields.'}
};
let source='ecb', datasets={}, rows=[], tablePage=0, nextOffset=null, requestId=0, query='';
const fmt=(x,d=4)=>Number(x).toLocaleString('en-US',{maximumFractionDigits:d});
const displayDate=s=>s ? new Date(s.slice(0,10)+'T00:00:00Z').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}) : '—';
function message(id,text){$(id).textContent=text;$(id).hidden=!text;}
async function get(url){const response=await fetch(url,{headers:{Accept:'application/json'}});const result=await response.json();if(!response.ok){const error=new Error(typeof result.detail==='string'?result.detail:'The request could not be completed. Check the selected values.');error.retryAfter=Number(response.headers.get('Retry-After')||0);throw error;}return result;}
function option(value,label){const o=document.createElement('option');o.value=value;o.textContent=label;return o;}
function seriesTitle(s){if(source==='worldbank')return names[s.entity]||s.entity;if(source==='ecb')return s.entity;const code=s.metric.replace('par_yield_','');return code.replace(/M$/,' month').replace(/Y$/,' year');}
function unitLabel(unit){if(unit==='percent_yoy')return '% annual growth';if(unit==='percent_per_year')return '% per year';return unit.replace('_per_EUR',' per EUR');}
function selectSource(next){
  source=next;const c=config[source],d=datasets[source];
  document.querySelectorAll('.tab').forEach(b=>{const active=b.dataset.source===source;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('breadcrumb').textContent=c.name;$('dataset-provider').textContent=c.provider;$('dataset-title').textContent=c.title;
  $('dataset-description').textContent=c.description;$('series-label').textContent=c.label;$('frequency').textContent=c.frequency;
  $('source-label').textContent=c.provider;$('source-link').href=c.url;$('source-note').textContent=c.note;
  $('converter-panel').hidden=source!=='ecb';
  $('series').replaceChildren();
  if(!d){message('series-error','This dataset is not yet available.');clearData('No observations available.');return;}
  $('source-count').textContent=fmt(d.count,0);$('coverage').textContent=d.first_date.slice(0,4)+'–'+d.last_date.slice(0,4);
  $('coverage-dates').textContent=displayDate(d.first_date)+' – '+displayDate(d.last_date);
  $('retrieval-date').textContent=displayDate(d.last_retrieved_at);renderRefreshStatus();$('attribution').textContent=d.attribution;
  let series=[...d.series];if(source==='treasury')series.sort((a,b)=>tenor(a.metric)-tenor(b.metric));
  series.forEach(s=>{const o=option(s.entity+'|'+s.metric,seriesTitle(s));if(s.entity===c.default||s.metric===c.default)o.selected=true;$('series').append(o);});
  $('start').value=d.first_date;$('end').value=d.last_date;
  ['series','start','end','apply'].forEach(id=>$(id).disabled=false);
  loadSeries();
}
function tenor(metric){const m=metric.match(/(\d+)([MY])$/);return m?Number(m[1])*(m[2]==='Y'?12:1):0;}
function clearData(text){rows=[];tablePage=0;nextOffset=null;$('rows').replaceChildren();$('chart').replaceChildren();const p=document.createElement('p');p.className='empty';p.textContent=text;$('chart').append(p);$('latest-value').textContent='—';$('value-unit').textContent='';$('latest-date').textContent='';$('series-range').textContent='';$('row-count').textContent='0 observations';$('table-page').textContent='';$('record-json').textContent='No record selected.';$('download').disabled=true;$('previous').disabled=true;$('next').disabled=true;$('load-more').hidden=true;}
async function loadSeries(append=false){
  const token=++requestId;
  if($('start').value>$('end').value){clearData('Choose a valid date range.');message('series-error','The start date must be on or before the end date.');return;}
  const [entity,metric]=$('series').value.split('|');
  const params=append?new URLSearchParams(query.split('?')[1]):new URLSearchParams({source,entity,metric,start:$('start').value,end:$('end').value,limit:'1000'});
  params.set('offset',String(append?nextOffset:0));
  query='/v1/observations?'+params.toString();$('json-link').href=query;
  if(!append)clearData('Loading observations…');
  message('series-error','');$('apply').disabled=true;$('load-more').disabled=true;
  try{
    const result=await get(query);if(token!==requestId)return;
    rows=append?rows.concat(result.data):result.data;nextOffset=result.next_offset;tablePage=0;
    $('attribution').textContent=result.attribution;$('row-count').textContent=fmt(rows.length,0)+' observations loaded'+(nextOffset!==null?' · more available':'');
    $('load-more').hidden=nextOffset===null;$('download').disabled=!rows.length;
    $('record-json').textContent=rows.length?JSON.stringify(rows[rows.length-1],null,2):'No observations match these filters.';
    renderChart();renderTable();
  }catch(error){if(token!==requestId)return;clearData('Unable to load observations.');message('series-error',error.message);}
  finally{if(token===requestId){$('apply').disabled=false;$('load-more').disabled=false;}}
}
function svgEl(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;}
function renderChart(){
  const points=rows.filter(r=>r.value!==null&&Number.isFinite(Number(r.value)));
  $('chart').replaceChildren();
  if(!points.length){const p=document.createElement('p');p.className='empty';p.textContent='No numeric observations for these filters.';$('chart').append(p);$('chart-note').textContent='Missing values are not replaced with zero.';return;}
  const last=points[points.length-1],values=points.map(r=>Number(r.value));
  $('latest-value').textContent=fmt(last.value,4);$('value-unit').textContent=unitLabel(last.unit);$('latest-date').textContent=displayDate(last.observation_date);
  $('series-range').textContent='Low '+fmt(Math.min(...values),4)+' · High '+fmt(Math.max(...values),4);
  $('chart-note').textContent=(source==='worldbank'?'Annual observations; connecting lines do not represent additional measurements. ':'Non-trading dates are absent; lines connect available observations. ')+(nextOffset!==null?'Showing a partial result. Load more to extend the chart. ':'')+'Chart values are rounded for display; JSON retains decimal strings.';
  const W=Math.max(300,$('chart').clientWidth),H=245,L=55,R=24,T=24,B=35;
  const dates=rows.map(r=>Date.parse(r.observation_date)),minX=Math.min(...dates),maxX=Math.max(...dates);
  let low=Math.min(...values),high=Math.max(...values),pad=(high-low)*.15||Math.abs(high)*.05||1;low-=pad;high+=pad;
  const x=r=>minX===maxX?(W+L-R)/2:L+(Date.parse(r.observation_date)-minX)/(maxX-minX)*(W-L-R);
  const y=r=>T+(high-Number(r.value))/(high-low)*(H-T-B);
  const svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':`${config[source].title}, ${points.length} numeric observations. Exact values follow in the table.`});
  for(let i=0;i<5;i++){const yy=T+i*(H-T-B)/4;svg.append(svgEl('line',{x1:L,y1:yy,x2:W-R,y2:yy,stroke:'#e5ebe3','stroke-dasharray':'3 5'}));svg.append(svgEl('text',{x:L-12,y:yy+4,'text-anchor':'end',fill:'#859087','font-size':11},fmt(high-i*(high-low)/4,2)));}
  let path='',broken=true;
  rows.forEach(r=>{if(r.value===null){broken=true;return;}path+=(broken?'M':'L')+x(r).toFixed(2)+','+y(r).toFixed(2)+' ';broken=false;});
  svg.append(svgEl('path',{d:path,fill:'none',stroke:'#267e5c','stroke-width':2.5,'stroke-linejoin':'round','stroke-linecap':'round'}));
  if(points.length<=24)points.forEach(r=>{const dot=svgEl('circle',{cx:x(r),cy:y(r),r:4,fill:'#267e5c',stroke:'white','stroke-width':2});dot.append(svgEl('title',{},r.observation_date+': '+r.value+' '+r.unit));svg.append(dot);});
  const indices=[...new Set([0,Math.floor((rows.length-1)/2),rows.length-1])];
  indices.forEach(i=>svg.append(svgEl('text',{x:x(rows[i]),y:H-7,'text-anchor':i===0?'start':i===rows.length-1?'end':'middle',fill:'#859087','font-size':11},rows[i].observation_date)));
  $('chart').append(svg);
}
function renderTable(){
  const start=tablePage*20,subset=rows.slice(start,start+20);$('rows').replaceChildren();
  subset.forEach(r=>{const tr=document.createElement('tr');[r.observation_date,names[r.entity]||r.entity,r.value===null?'Missing':fmt(r.value,6),r.unit,r.quality].forEach((value,i)=>{const td=document.createElement('td');if(i===2)td.className='numeric';if(i===4){const badge=document.createElement('span');badge.className='quality';badge.textContent=value;td.append(badge);}else td.textContent=value;tr.append(td);});$('rows').append(tr);});
  $('table-page').textContent=rows.length?`${start+1}–${Math.min(start+20,rows.length)} of ${fmt(rows.length,0)} loaded`:'No matching records';
  $('previous').disabled=tablePage===0;$('next').disabled=start+20>=rows.length;
}
function csvCell(value){const s=value===null?'':String(value);return '"'+s.replace(/"/g,'""')+'"';}
$('download').addEventListener('click',()=>{if(!rows.length)return;const columns=Object.keys(rows[0]);const csv=[columns.map(csvCell).join(','),...rows.map(r=>columns.map(k=>csvCell(r[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`mfapis_${source}_${$('start').value}_${$('end').value}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('filters').addEventListener('submit',e=>{e.preventDefault();loadSeries();});
$('previous').addEventListener('click',()=>{tablePage--;renderTable();});$('next').addEventListener('click',()=>{tablePage++;renderTable();});
$('load-more').addEventListener('click',()=>loadSeries(true));
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>selectSource(b.dataset.source)));
let fxCapabilities=null, historyRefresh={}, fxToken=0, fxBusy=false, fxTimer=null, retryAt=0;
const currencyNames=typeof Intl.DisplayNames==='function'?new Intl.DisplayNames(['en'],{type:'currency'}):null;
const currencyLabel=c=>c+' · '+(currencyNames?.of(c)||c);
function mode(){return $('fx-mode').value;}
function availableCurrencies(){return mode()==='latest'?(fxCapabilities?.currencies.map(c=>c.code)||[]):[...new Set(['EUR',...(datasets.ecb?.series.map(s=>s.entity.split('/')[1])||[])])].sort();}
function quoteOptions(preferred){
  const base=$('base').value;
  let codes=availableCurrencies();
  if(mode()==='latest')codes=codes.filter(c=>c!==base&&fxCapabilities.cross_rates||fxCapabilities.pairs.some(p=>p===base+'/'+c||p===c+'/'+base));
  $('quote').replaceChildren(...codes.map(c=>option(c,currencyLabel(c))));
  if(codes.includes(preferred))$('quote').value=preferred;
  $('quote').disabled=!codes.length;
}
function configureCurrencies(base='USD',quote='INR'){
  const codes=availableCurrencies();$('base').replaceChildren(...codes.map(c=>option(c,currencyLabel(c))));
  if(codes.includes(base))$('base').value=base;
  quoteOptions(quote);$('base').disabled=!codes.length;$('convert-button').disabled=!codes.length;
}
function invalidateFX(){fxToken++;fxBusy=false;clearTimeout(fxTimer);$('conversion-result').textContent='Selection changed. Request a rate for these currencies.';$('conversion-json').textContent='No result for the current selection.';$('fx-updated').textContent='Source observation timestamp will appear with the result.';$('fx-status').textContent=mode()==='latest'?'Live quote pending':'Historical reference';$('fx-status').classList.remove('warning');message('conversion-error','');$('convert-button').disabled=!$('base').value;}
function scheduleFX(delay=15000){clearTimeout(fxTimer);if(mode()==='latest'&&$('auto-refresh').checked)fxTimer=setTimeout(()=>{if(!document.hidden&&source==='ecb')convertFX();else scheduleFX(delay);},Math.max(delay,retryAt-Date.now()));}
async function convertFX(){
  if(fxBusy||!$('converter').reportValidity())return;
  if(mode()==='latest'&&Date.now()<retryAt){message('conversion-error','Please wait for the retry delay before requesting another quote.');scheduleFX();return;}
  const token=++fxToken;fxBusy=true;clearTimeout(fxTimer);$('convert-button').disabled=true;
  message('conversion-error','');$('conversion-result').classList.remove('unavailable');$('conversion-result').textContent='Requesting latest market quote…';
  const requestedMode=mode();
  const params=new URLSearchParams({base:$('base').value,quote:$('quote').value,amount:$('amount').value});
  if(requestedMode==='historical')params.set('on',$('conversion-date').value);
  const url='/v1/fx/convert?'+params;
  $('fx-json-link').href=url;
  try{
    const r=await get(url);if(token!==fxToken)return;
    $('conversion-result').textContent=`${fmt(r.amount,4)} ${r.base} = ${fmt(r.converted_amount,2)} ${r.quote}`;
    const small=document.createElement('small');small.textContent=`1 ${r.base} = ${fmt(r.rate,8)} ${r.quote}`;$('conversion-result').append(small);
    $('conversion-json').textContent=JSON.stringify(r,null,2);$('fx-status').classList.remove('warning');
    if(requestedMode==='latest'){
      $('fx-status').textContent='Fresh market observation';
      $('fx-updated').textContent=`Source: ${r.source} · Market observation: ${new Date(r.as_of).toLocaleString()} · Age: ${r.quote_age_seconds}s · Received by MFAPIs: ${new Date(r.fetched_at).toLocaleString()} · Bid/ask midpoint`;
      scheduleFX(Math.max(5000,(fxCapabilities?.refresh_seconds||15)*1000));
    }else{$('fx-status').textContent='Historical reference';$('fx-updated').textContent='ECB observation date: '+displayDate(r.observation_date);}
  }catch(error){if(token!==fxToken)return;
    $('conversion-result').textContent='No current conversion available for this request.';$('conversion-result').classList.add('unavailable');
    $('conversion-json').textContent=JSON.stringify({error:error.message},null,2);$('fx-updated').textContent='No successful quote for the current request.';
    $('fx-status').textContent='Unavailable';$('fx-status').classList.add('warning');message('conversion-error',error.message);
    retryAt=Date.now()+Math.max(0,error.retryAfter||0)*1000;scheduleFX(Math.max(15000,(error.retryAfter||15)*1000));
  }finally{if(token===fxToken){fxBusy=false;$('convert-button').disabled=false;}}
}
$('converter').addEventListener('submit',e=>{e.preventDefault();convertFX();});
$('base').addEventListener('change',()=>{const prior=$('quote').value;invalidateFX();quoteOptions(prior);});
for(const id of ['quote','amount','conversion-date'])$(id).addEventListener('input',invalidateFX);
$('swap').addEventListener('click',()=>{const base=$('base').value,quote=$('quote').value;invalidateFX();configureCurrencies(quote,base);convertFX();});
$('auto-refresh').addEventListener('change',()=>{clearTimeout(fxTimer);if($('auto-refresh').checked)scheduleFX();});
$('fx-mode').addEventListener('change',()=>{
  const base=$('base').value,quote=$('quote').value;invalidateFX();configureCurrencies(base,quote);
  const historical=mode()==='historical';$('conversion-date-label').hidden=!historical;$('conversion-date').required=historical;$('auto-refresh').disabled=historical;
  $('convert-button').textContent=historical?'Convert on this date →':'Get live quote →';
  $('converter-description').textContent=historical?'Cross-rates calculated from stored ECB daily reference rates.':'MFAPIs computes values from authenticated, authorized source observations and shows the actual quote timestamp.';
  $('fx-attribution').hidden=historical;
  $('fx-note').textContent=historical?'Source: European Central Bank. Exact observation date; no hidden carry-forward for weekends or holidays. Informational rates only.':'MFAPIs stores, verifies and converts authorized market quotes. The values update only when the upstream feed publishes new observations. Stale or missing data cannot be called live. Not executable rates.';
  convertFX();
});
async function initFX(){
  try{fxCapabilities=await get('/v1/fx/currencies');configureCurrencies();
    $('auto-refresh').parentNode.lastChild.textContent=' Auto-refresh every '+fxCapabilities.refresh_seconds+' seconds';
    if(!fxCapabilities.configured){$('fx-status').textContent='Feed not configured';$('conversion-result').textContent='Connect an authorized market quote source to MFAPIs. Daily ECB history remains available separately; it is not live forex.';return;}
    convertFX();
  }catch(error){message('conversion-error',error.message);$('fx-status').textContent='Unavailable';}
}
async function init(){
  try{const result=await get('/v1/catalogue');datasets=Object.fromEntries(result.datasets.map(d=>[d.source,d]));if(!Object.keys(config).every(s=>datasets[s]))throw new Error('Dataset initialization is incomplete. Please retry shortly.');
    $('total-count').textContent=fmt(result.datasets.reduce((n,d)=>n+d.count,0),0);$('connection').textContent='Database connected';
    historyRefresh=result.refresh||{};$('conversion-date').value=datasets.ecb.last_date;
    selectSource('ecb');
  }catch(error){$('connection').textContent='Data unavailable';message('global-error',error.message+' Refresh this page after the service finishes starting.');clearData('Waiting for the database.');}
}
init();
initFX();
window.addEventListener('resize',()=>{if(rows.length)renderChart();});

function renderRefreshStatus(){
  const r=historyRefresh[source];
  $('refresh-status').textContent=r?(r.status==='error'?'Last refresh failed; stored observations retained.':r.status==='running'?'Checking for source updates…':'Last successful check: '+new Date(r.last_success_at*1000).toLocaleString()):'Retrieval date, not publication date';
}
async function pollCatalogue(){
  if(document.hidden)return;
  try{
    const result=await get('/v1/catalogue'),old=datasets[source];
    const updated=Object.fromEntries(result.datasets.map(d=>[d.source,d]));
    historyRefresh=result.refresh||{};datasets=updated;renderRefreshStatus();
    $('total-count').textContent=fmt(result.datasets.reduce((n,d)=>n+d.count,0),0);
    const d=datasets[source];if(!d)return;
    $('source-count').textContent=fmt(d.count,0);$('coverage').textContent=d.first_date.slice(0,4)+'–'+d.last_date.slice(0,4);
    $('coverage-dates').textContent=displayDate(d.first_date)+' – '+displayDate(d.last_date);$('retrieval-date').textContent=displayDate(d.last_retrieved_at);
    if(old&&old.last_retrieved_at!==d.last_retrieved_at){
      if($('end').value===old.last_date)$('end').value=d.last_date;
      if($('conversion-date').value===old.last_date&&source==='ecb')$('conversion-date').value=d.last_date;
      loadSeries();
    }
  }catch(error){$('refresh-status').textContent='Could not check for new records. Displayed records may be out of date.';}
}
setInterval(pollCatalogue,60000);
