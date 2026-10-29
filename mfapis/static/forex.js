/* MFAPIs Forex workspace. Browser talks only to the same-origin local API. */
'use strict';

const $ = id => document.getElementById(id);
const currencies = {
  EUR:'Euro',USD:'US Dollar',INR:'Indian Rupee',GBP:'British Pound',JPY:'Japanese Yen',
  CHF:'Swiss Franc',AUD:'Australian Dollar',CAD:'Canadian Dollar',NZD:'New Zealand Dollar',
  SGD:'Singapore Dollar',HKD:'Hong Kong Dollar',CNY:'Chinese Yuan'
};
const state = { quotes:[], allowed:[], maxAge:120, timer:null, loading:false, latestError:'', token:0, hasConverted:false };
const decimal = (value, places=5) => new Intl.NumberFormat('en-US', { maximumFractionDigits:places, minimumFractionDigits:0 }).format(value);
const money = (value, code) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `${decimal(number, 2)} ${code}`;
};
const timeLabel = iso => {
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? new Intl.DateTimeFormat('en-US', {dateStyle:'medium', timeStyle:'short'}).format(new Date(ms)) : '—';
};
const ageOf = r => Math.floor((Date.now() - Date.parse(r.observed_at))/1000);
const fresh = r => r && Number.isFinite(ageOf(r)) && ageOf(r) >= 0 && ageOf(r) <= state.maxAge && r.fresh !== false;
const quoteSymbols = () => new Set(state.quotes.map(q => q.symbol));

async function api(path) {
  const response = await fetch(path, { cache:'no-store', credentials:'same-origin', headers:{Accept:'application/json'} });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const reason = typeof data?.detail === 'string' ? data.detail : `API error (${response.status})`;
    throw new Error(reason);
  }
  return data;
}

function showAlert(message) {
  $('global-error').hidden = !message;
  $('global-error').textContent = message || '';
}
function setConnection(message, kind) {
  $('connection-status').textContent = message;
  $('connection-beacon').className = 'status-beacon' + (kind ? ` ${kind}` : '');
  $('last-checked').textContent = 'Checked ' + new Date().toLocaleTimeString();
}
function addOption(select, code) {
  const opt = document.createElement('option');
  opt.value = code;
  opt.textContent = `${code}  ·  ${currencies[code] || code}`;
  select.append(opt);
}
function fillCurrencies() {
  const base = $('base').value || 'EUR';
  const quote = $('quote').value || 'USD';
  const fromData = [...new Set(state.quotes.flatMap(q => q.symbol.split('/')))];
  const codes = [...new Set([...fromData, ...state.allowed])].sort();
  $('base').replaceChildren(); $('quote').replaceChildren();
  codes.forEach(code => { addOption($('base'),code); addOption($('quote'),code); });
  $('base').value = codes.includes(base) ? base : (codes.includes('EUR') ? 'EUR' : codes[0]);
  $('quote').value = codes.includes(quote) ? quote : (codes.includes('USD') ? 'USD' : codes.find(c => c !== $('base').value) || codes[0]);
  $('base').disabled = codes.length < 2;
  $('quote').disabled = codes.length < 2;
  $('convert').disabled = codes.length < 2;
  $('amount-code').textContent = $('base').value || '—';
}
function td(value, className='') {
  const cell = document.createElement('td');
  cell.textContent = value;
  cell.className = className;
  return cell;
}
function renderRows() {
  const tbody=$('quote-rows');
  tbody.replaceChildren();
  if(!state.quotes.length) {
    const row=document.createElement('tr');
    const cell=td('No recorded live quotes yet. Run your SiftingIO local demo to import observations.','no-data');
    cell.colSpan=5;row.append(cell);tbody.append(row);
    return;
  }
  for(const q of state.quotes) {
    const row=document.createElement('tr');
    row.dataset.symbol=q.symbol;
    row.tabIndex=0;
    row.setAttribute('aria-label',`Select ${q.symbol} for conversion`);
    const pair=td(q.symbol,'pair-name');
    const sub=document.createElement('small'); sub.className='pair-sub';
    sub.textContent=q.source || 'Market quote'; pair.append(sub); row.append(pair);
    const bid=Number(q.bid),ask=Number(q.ask);
    row.append(td(Number.isFinite(bid)?decimal(bid,6):'—','right'));
    row.append(td(Number.isFinite(ask)?decimal(ask,6):'—','right'));
    row.append(td(Number.isFinite(bid)&&Number.isFinite(ask)?decimal((bid+ask)/2,6):'—','right price-mid'));
    const status=td('','center');
    const label=document.createElement('span');
    const ok=fresh(q),age=ageOf(q);
    label.className='badge '+(ok?'fresh':'stale');
    label.textContent=ok?`${Math.max(0,age)}s · Fresh`:`${Math.max(0,age)}s · Stale`;
    status.append(label);row.append(status);
    const selectRow=()=>{
      const [base,quote]=q.symbol.split('/');
      $('base').value=base; $('quote').value=quote; $('amount-code').textContent=base;
      if($('converter').reportValidity())convert();
    };
    row.addEventListener('click',selectRow);
    row.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();selectRow();}});
    tbody.append(row);
  }
}
function renderStats() {
  const count=state.quotes.filter(fresh).length;
  $('stat-pairs').textContent=String(state.quotes.length);
  $('stat-fresh').textContent=`${count} / ${state.quotes.length}`;
  $('board-caption').textContent=`${count} fresh ${count===1?'pair':'pairs'} · local observations`;
  $('threshold-note').textContent=`Freshness threshold: ${state.maxAge} seconds`;
  const epochs=state.quotes.map(q=>Date.parse(q.observed_at)).filter(Number.isFinite);
  if(epochs.length){const latest=new Date(Math.max(...epochs));$('stat-observed').textContent=latest.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});$('stat-observed-date').textContent=latest.toLocaleDateString([], {dateStyle:'medium'});}else{$('stat-observed').textContent='—';$('stat-observed-date').textContent='No quote timestamps available';}
  if(!state.latestError) {
    $('connection-status').textContent=count > 0 ? 'Market quotes fresh' : 'Quotes stale / missing';
    $('connection-beacon').className='status-beacon ' + (count > 0 ? 'good' : 'bad');
  }
}
function showConversionError(message) {
  $('converted-amount').textContent='Unavailable';
  $('unit-rate').textContent=message;
  $('conversion-source').textContent='—';
  $('conversion-time').textContent='—';
  $('conversion-status').textContent='No fresh conversion';
}
async function convert() {
  if(!$('converter').reportValidity()) return;
  const base=$('base').value,quote=$('quote').value,amount=$('amount').value;
  const token=++state.token;
  $('amount-code').textContent=base;
  $('converted-amount').textContent='Calculating…';
  $('convert').disabled=true;
  try {
    if(base===quote){
      $('converted-amount').textContent=money(amount,quote);
      $('unit-rate').textContent=`1 ${base} = 1 ${quote} · identity conversion`;
      $('conversion-source').textContent='Identity';
      $('conversion-time').textContent='Not required';
      $('conversion-status').textContent='No market rate needed';
      return;
    }
    const params=new URLSearchParams({base,quote,amount});
    const result=await api('/v1/fx/convert?'+params.toString());
    if(token!==state.token) return;
    $('converted-amount').textContent=money(result.converted_amount,quote);
    $('unit-rate').textContent=`1 ${base} = ${decimal(Number(result.rate),8)} ${quote}`;
    $('conversion-source').textContent=result.source || result.provider || '—';
    $('conversion-time').textContent=timeLabel(result.as_of);
    $('conversion-status').textContent=`Fresh (${result.quote_age_seconds ?? '?'}s) · ${result.rate_type==='observed_bid_ask_midpoint'?'bid/ask midpoint':'market quote'}`;
  } catch(error) {
    if(token!==state.token) return;
    showConversionError(error.message + '. Fetch newer quotes in your running demo if needed.');
  } finally { if(token===state.token)$('convert').disabled=false; }
}
async function refreshQuotes() {
  if(state.loading) return;
  state.loading=true;
  $('refresh').disabled=true;
  try {
    const [quotes,capabilities]=await Promise.all([
      api('/v1/fx/quotes'),api('/v1/fx/currencies')
    ]);
    if(!Array.isArray(quotes.quotes))throw new Error('Invalid quote list from local MFAPIs API');
    state.quotes=quotes.quotes.filter(q=>q && typeof q.symbol==='string' && /^[A-Z]{3}\/[A-Z]{3}$/.test(q.symbol));
    state.allowed=Array.isArray(capabilities.currencies) ? capabilities.currencies.map(c=>c.code).filter(c=>/^[A-Z]{3}$/.test(c)) : [];
    state.maxAge=Number(capabilities.max_quote_age_seconds)||120;
    state.latestError='';
    fillCurrencies();renderRows();renderStats();showAlert('');
    $('last-checked').textContent='Checked ' + new Date().toLocaleTimeString();
    await convert();
  }catch(error){
    state.latestError=error.message;
    showAlert('Unable to read local Forex data: '+error.message+'. Start your local MFAPIs demo or check its configuration.');
    setConnection('Data unavailable','bad');
    $('board-caption').textContent='Local API unavailable';
    showConversionError('No live data from the local API.');
  }finally{state.loading=false;$('refresh').disabled=false;}
}
function schedule() {
  clearInterval(state.timer);
  if($('auto-refresh').checked) {
    state.timer=setInterval(()=>{if(!document.hidden)refreshQuotes();},Number($('refresh-interval').value)||15000);
  }
}
$('converter').addEventListener('submit',event=>{event.preventDefault();convert();});
$('base').addEventListener('change',()=>{$('amount-code').textContent=$('base').value;convert();});
$('quote').addEventListener('change',convert);
let debounce;
$('amount').addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>{if($('amount').checkValidity())convert();},350);});
$('swap').addEventListener('click',()=>{const b=$('base').value;$('base').value=$('quote').value;$('quote').value=b;$('amount-code').textContent=$('base').value;convert();});
let providerRefreshing=false;
async function fetchLatestRates(){
  if(providerRefreshing)return;
  providerRefreshing=true;
  const button=$('fetch-latest');
  button.disabled=true;
  button.textContent='Fetching…';
  showAlert('');
  try{
    const response=await fetch('/v1/local/sifting/refresh',{
      method:'POST',cache:'no-store',credentials:'same-origin',
      headers:{'X-MFAPIS-Local-Action':'refresh','Accept':'application/json'}
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.detail || `Fetch error (${response.status})`);
    await refreshQuotes();
    if(result.errors?.length){
      showAlert(`Received ${result.updated} of ${result.requested} provider snapshots. `+result.errors.join(' · '));
    }else{
      showAlert(`Received ${result.updated} of ${result.requested} provider snapshots. Refreshing the local board.`);
    }
  }catch(error){showAlert('Unable to fetch new SiftingIO quotes: '+error.message);}
  finally{
    providerRefreshing=false;
    button.disabled=false;
    button.textContent='↡ Fetch latest rates';
  }
}
$('fetch-latest').addEventListener('click',fetchLatestRates);
$('refresh').addEventListener('click',refreshQuotes);
$('auto-refresh').addEventListener('change',schedule);
$('refresh-interval').addEventListener('change',schedule);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshQuotes();});
setInterval(()=>{if(state.quotes.length){renderRows();renderStats();}},1000);
refreshQuotes();schedule();
