const snapshotNode = document.getElementById('saved-snapshot');
const $ = id => document.getElementById(id);
let data = null, busy = false, requesting = false, loading = false, activeTask = null;
const number = (v,d=2) => v == null ? '—' : Number(v).toLocaleString('en-GB',{maximumFractionDigits:d,minimumFractionDigits:d});
const price = v => v > 0 ? number(v) : '—';
const pct = v => v == null ? '—' : number(v*100,1)+'%';
function text(id,value) { $(id).textContent = value; }
function el(tag,content,cls) { const n=document.createElement(tag); n.textContent=content; if(cls)n.className=cls; return n; }
function renderResearch(){
  const p=data.paper||{},r=data.research||{},perf=r.performance||{},feed=data.disclosures||{};
  text('paper-status',(p.session?'Session '+p.session+' · ':'')+(p.status||'No prospective plan yet. The next pre-open scan starts the ledger.')+(p.sessions?' · '+p.sessions+' resolved sessions; '+p.trades+' scenario fills.':''));
  text('paper-equity',number(p.equity));text('paper-return',p.net_return_pct==null?'—':number(p.net_return_pct)+'%');text('paper-drawdown',p.max_drawdown_pct==null?'—':number(p.max_drawdown_pct)+'%');text('paper-expectancy',number(p.expectancy_egp));
  $('paper-rows').replaceChildren();
  for(const order of p.orders||[]){const tr=el('tr'),o=order.outcome;tr.append(el('td',order.symbol),el('td',order.decision==='paper_eligible'?'Paper eligible':'Watch only'),el('td',number(order.quantity,0),'num'),el('td',o?o.status.replaceAll('_',' ')+(o.pnl!=null?' · '+number(o.pnl)+' EGP':''):'Pending'),el('td',(order.reasons||[]).join('. ')));$('paper-rows').append(tr);}
  $('paper-table-wrap').classList.toggle('hidden',!(p.orders||[]).length);text('paper-caption','Frozen risk decisions · '+(p.policy_hash||'Policy pending'));
  text('research-status',(perf.status||'Evidence accumulating')+(r.updated_at?' · Updated '+new Date(r.updated_at).toLocaleString('en-GB'):' · The outcome-learning job will publish the first report.'));
  text('research-sessions',perf.sessions==null?'—':String(perf.sessions));
  for(const [id,value] of [['research-return',perf.mean_net_return_pct],['research-baseline',perf.universe_mean_net_return_pct],['research-stress',perf.stressed_net_return_pct]])text(id,value==null?'—':number(value)+'%');
  const ci=perf.excess_95pct_interval;text('research-interval',ci?'95% session-block interval for mean excess: '+number(ci[0])+'% to '+number(ci[1])+'%. This sample does not establish a durable edge.':'Too few complete sessions for an excess-return confidence interval.');
  $('data-health').replaceChildren();const health=r.data_health||{};
  for(const [key,value] of Object.entries(health)){const dt=el('dt',key.replaceAll('_',' ')),dd=el('dd',typeof value==='object'?Object.entries(value).map(([k,v])=>k+': '+v).join(' · '):String(value));$('data-health').append(dt,dd);}
  if(!Object.keys(health).length)$('data-health').append(el('dd','No data audit snapshot yet.'));
  $('event-cohorts').replaceChildren();for(const c of r.event_cohorts||[])$('event-cohorts').append(el('p',c.event_type.replaceAll('_',' ')+' · '+c.selections+' selections / '+c.sessions+' sessions · '+number(c.mean_net_return_pct)+'% scenario mean. '+c.status));
  if(!(r.event_cohorts||[]).length)$('event-cohorts').append(el('p','No outcomes linked to announcements known before publication yet. Backfilled news does not count.'));
  text('disclosure-status',(feed.status||'Not collected')+' · '+(feed.message||'The scheduled collector will archive the latest official records.')+(feed.last_success_at?' · Last success '+new Date(feed.last_success_at).toLocaleString('en-GB'):''));
  $('disclosure-list').replaceChildren();
  for(const event of feed.events||[]){const row=el('article','','disclosure-row'),heading=el('h3',(event.symbol?event.symbol+' · ':'')+event.title);heading.dir='auto';row.append(heading);
    if(event.title_ar){const ar=el('p',event.title_ar,'small');ar.dir='auto';row.append(ar);}
    row.append(el('p',event.event_type.replaceAll('_',' ')+' · Published '+new Date(event.published_at).toLocaleString('en-GB')+' · First seen '+new Date(event.first_seen_at).toLocaleString('en-GB'),'small muted'));
    try{const url=new URL(event.source_url);if(url.protocol==='https:'&&url.hostname==='beta.egx.com.eg'){const link=el('a','Read the original disclosure ↗','button');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';row.append(link);}}catch(e){}
    $('disclosure-list').append(row);
  }
  if(!(feed.events||[]).length)$('disclosure-list').append(el('p','No official records saved yet. Missing coverage is not evidence that no announcement exists.','state'));
}
function render() {
  if(!data)return;
  const picks=data.signals.filter(r=>r.candidate_rank).sort((a,b)=>a.candidate_rank-b.candidate_rank);
  text('shortlist-note','For '+(data.target_session||'the next session')+' · '+picks.length+'/5 eligible candidates. Scores rank setups; they are not win probabilities.');
  $('shortlist').replaceChildren();
  for(const r of picks){
    const card=el('article','','shortlist-row'), head=el('div','','shortlist-head');
    const button=el('button','#'+r.candidate_rank+' '+r.symbol,'row-button');button.onclick=()=>showDetail(r);
    head.append(button,el('span','Score '+number(r.next_day_score,1)+' / 100','mono'));
    card.append(head,el('p',r.company,'muted'),el('p','Close '+price(r.latest_close)+' · Target '+price(r.next_day_target)+' · Stop '+price(r.next_day_stop_loss),'mono small'));
    const reasons=el('ul');for(const reason of r.selection_reasons||[])reasons.append(el('li',reason));
    card.append(reasons,el('p',r.source_status||'Source confirmation unavailable','small muted'));
    const paper=data.paper?.session===data.target_session?(data.paper.orders||[]).find(o=>o.symbol===r.symbol):null;
    if(paper)card.append(el('p',paper.decision==='paper_eligible'?'Paper risk checks passed · '+paper.quantity+' planned shares':'Watch only · '+paper.reasons.join('. '),'small'));
    $('shortlist').append(card);
  }
  const h=$('horizon').value, f=$('filter').value;
  text('rankings-title',h==='next_day'?'Next-day opportunity list':'20-session opportunity list');
  let list=data.signals.filter(r=>(r.symbol+' '+r.company).toLowerCase().includes($('search').value.toLowerCase()));
  if(f!=='all')list=list.filter(r=>(r[h+'_label']||'').toLowerCase().includes(f));
  list.sort((a,b)=>(b[h+'_score']||0)-(a[h+'_score']||0));
  const fragment=document.createDocumentFragment();
  for(const r of list){
    const tr=document.createElement('tr'),name=document.createElement('td');
    const b=el('button',r.symbol,'row-button'); b.onclick=()=>showDetail(r);
    b.setAttribute('aria-label','Inspect '+r.symbol+' — '+r.company);
    name.append(b,el('span',r.company,'company'));
    tr.append(name,el('td',number(r.latest_close),'num'),el('td',number(r[h+'_score'],1),'num'),el('td',price(h==='next_day'?r.next_day_target:r.swing_target),'num'),el('td',price(r[h+'_stop_loss']),'num'));
    const assessment=document.createElement('td');assessment.append(el('span',r.legacy?'Legacy scan':(r[h+'_label']||'Unclassified'),'badge'));tr.append(assessment);fragment.append(tr);
  }
  $('rows').replaceChildren(fragment);$('empty').classList.toggle('hidden',list.length>0);$('table').classList.toggle('hidden',!list.length);
  text('list-note',list.length+(list.length===1?' symbol shown · ':' symbols shown · ')+(data.stale?'Saved historical scan':'Current completed session')+' · Select a symbol for details.');
}
let historyPage=0;
function renderHistory(reset=false){
  if(!data)return;
  if(reset)historyPage=0;
  const rows=data.history||[], query=$('history-search').value.trim().toLowerCase();
  const session=$('history-session').value, result=$('history-result').value;
  const filtered=rows.filter(r=>(r.symbol+' '+r.company).toLowerCase().includes(query)&&(session==='all'||r.session===session)&&(result==='all'||r.status===result));
  const counts={hit:0,miss:0,pending:0,unverified:0};for(const r of filtered)counts[r.status]++;
  text('history-summary',filtered.length+' predictions · '+counts.hit+' hits · '+counts.miss+' misses · '+counts.pending+' pending · '+counts.unverified+' unverified');
  historyPage=Math.min(historyPage,Math.max(0,Math.ceil(filtered.length/25)-1));
  const start=historyPage*25, fragment=document.createDocumentFragment();
  const labels={hit:'✓ Hit',miss:'× Miss',pending:'… Pending',unverified:'? Unverified'};
  const explanations={missing_or_conflicting_candle:'Missing or conflicting prices',corporate_action_review:'Corporate action needs review',invalid_levels:'Invalid recorded target'};
  for(const r of filtered.slice(start,start+25)){
    const tr=document.createElement('tr'), sessionCell=el('td',r.session,'num'), name=el('td','#'+r.candidate_rank+' '+r.symbol);
    if(!r.session_confirmed)sessionCell.append(el('span','Expected session','company'));
    name.append(el('span',r.company,'company'),el('span','Published '+r.published_at.slice(0,10),'company'));
    tr.append(sessionCell,name);
    for(const key of ['reference','target','actual_high','actual_close'])tr.append(el('td',r[key]>0?number(r[key],3):'—','num'));
    tr.append(el('td',r.close_change_pct==null?'—':(r.close_change_pct>0?'+':'')+number(r.close_change_pct,2)+'%','num'));
    const outcome=document.createElement('td');outcome.append(el('span',labels[r.status],'badge outcome-'+r.status));
    if(r.status==='unverified')outcome.append(el('span',explanations[r.outcome_status]||'Result not verified','company'));
    const tradeLabels={profitable:'Profitable after assumed costs',loss:'Loss after assumed costs',breakeven:'Break-even after assumed costs',not_filled:'Not filled · cash',ambiguous:'Ambiguous target/stop order',unresolved:'Trade unresolved'};
    outcome.append(el('span',tradeLabels[r.trade_category]||'Trade unresolved','company'));
    if(r.net_return_pct!=null)outcome.append(el('span','Scenario net '+number(r.net_return_pct,2)+'%','company'));
    tr.append(outcome);fragment.append(tr);
  }
  $('history-rows').replaceChildren(fragment);$('history-table-wrap').classList.toggle('hidden',!filtered.length);$('history-empty').classList.toggle('hidden',!!filtered.length);
  text('history-empty',rows.length?'No matching predictions. Try another session or result filter.':'No dated predictions saved yet. History appears after a market scan is saved.');
  text('history-page',filtered.length?'Showing '+(start+1)+'–'+Math.min(start+25,filtered.length)+' of '+filtered.length:'0 predictions');
  $('history-prev').disabled=historyPage===0;$('history-next').disabled=start+25>=filtered.length;
}
function loadHistory(){
  const previous=$('history-session').value, sessions=[...new Set((data.history||[]).map(r=>r.session))].sort().reverse();
  const all=el('option','All sessions');all.value='all';$('history-session').replaceChildren(all);
  for(const day of sessions){const option=el('option',day);option.value=day;$('history-session').append(option);}
  $('history-session').value=previous==='latest'?(sessions[0]||'all'):sessions.includes(previous)?previous:'all';renderHistory();
}
function showDetail(r) {
  const h=$('horizon').value;text('detail-title',r.symbol);text('detail-company',r.company);$('levels').replaceChildren();
  const values=[['Reference close',number(r.latest_close)],['Target',price(h==='next_day'?r.next_day_target:r.swing_target)],['Stop',price(r[h+'_stop_loss'])],['Target-touch probability',pct(h==='next_day'?r.next_day_probability:r.swing_probability)],['Data quality',number(r.data_quality_score,0)+' / 100'],['Close consensus',r.consensus_confidence>0?number(r.consensus_confidence,0)+' / 100':'Unverified'],['Feature session',r.feature_session||'Legacy record'],['Evidence',r.legacy?'Legacy · not recalibrated':(h==='next_day'?r.model_version:r.swing_model_version)||'Technical only']];
  for(const [k,v]of values){const group=document.createElement('div');group.append(el('dt',k),el('dd',v));$('levels').append(group);}
  $('reasons').replaceChildren();
  const reasons=h==='next_day'?[...(r.selection_reasons||[]),...(r.next_day_reasons||'No saved reasoning available.').split(';')]:['20-session target and stop are shown when recorded. Consult the swing validation report for independent evidence.'];
  const shadow = (r.adaptive_levels||[]).find(note=>note.startsWith(h==='next_day'?'Shadow · 1 session ·':'Shadow · 20 sessions ·'));
  if(shadow)reasons.push(shadow);
  for(const reason of reasons)$('reasons').append(el('div',reason.trim(),'reason'));
  $('detail').showModal();
}
function validation(id,v) {
  const n=$(id);n.replaceChildren();
  if(!v){n.append(el('p','No validated model yet. Evaluate updated models after collecting enough history.'));return;}
  n.append(el('p',v.promoted?'Validated model eligible for future sessions':'Technical scoring remains active'));
  if(v.metrics){const m=v.metrics;n.append(el('p','Top-five target precision: '+pct(m.precision_at_5)+' across '+m.sessions+' test sessions. '+m.selected+' selections; session coverage '+pct(m.session_coverage)+'. '+(m.unresolved_selected||0)+' unresolved selections.'));n.append(el('p','Conservative net return per selection: '+number(m.net_expectancy_pct)+'%. Test period '+v.test_start+' to '+v.test_end+'.'));}
  n.append(el('p',v.reason||(v.promotion_reasons||[]).join('. ')||v.provenance||''));
}
async function load(feedback=false) {
  if(loading)return;loading=true;$('refresh').disabled=true;$('refresh').setAttribute('aria-busy','true');
  try{
    if(snapshotNode)data=JSON.parse(snapshotNode.textContent);
    else{const response=await fetch('/api/overview');if(!response.ok)throw new Error('Cannot read saved data ('+response.status+')');data=await response.json();}
    text('session',data.price_session||'—');text('scanned',data.scan?'Scan saved '+data.scan.generated_at.slice(0,10):'No scan saved');text('symbols',data.signals.length);text('hit-rate',pct(data.outcomes.target_hit_rate));text('hits',(data.outcomes.hits||0)+' / '+(data.outcomes.total||0)+' distinct resolved signals');text('trade-count',data.outcomes.executable_trades||0);text('trade-note',data.outcomes.executable_trades?'Trade win rate '+pct(data.outcomes.trade_win_rate):'Historical stops unavailable or outcomes pending');
    text('notice',data.stale?'Saved data or features need refreshing. Run a market scan for the latest completed session.':'Prices and saved features match the latest completed session.');
    if(data.scan&&data.scan.error_count)text('notice',$('notice').textContent+' '+data.scan.error_count+' symbols failed the scan checks.');
    $('notice').classList.toggle('good',!data.stale);validation('next-validation',data.validation.next_day);validation('swing-validation',data.validation.swing);render();loadHistory();renderResearch();
    if(feedback)notifyUser('View refreshed · '+data.signals.length+' saved symbols.');
  }catch(e){if(!data)text('history-summary','Could not load prediction history. Use Refresh view to retry.');text('notice',e.message+'. Use Refresh view to retry.');$('notice').classList.remove('good');if(feedback)notifyUser('Refresh failed. Your saved view is still available.');}
  finally{loading=false;$('loading').classList.add('hidden');$('refresh').disabled=false;$('refresh').setAttribute('aria-busy','false');}
}
function setBusy(value,task=activeTask){
  busy=value;
  for(const id of ['scan','train']){$(id).disabled=value;$(id).setAttribute('aria-busy',String(value&&id===task));}
  $('scan').querySelector('span').textContent=value&&task==='scan'?'Scanning market…':'Run market scan';
  $('train').querySelector('span').textContent=value&&task==='train'?'Evaluating models…':'Evaluate updated models';
}
async function action(path,task){
  if(busy||requesting)return;requesting=true;activeTask=task;setBusy(true);
  text('progress',task==='scan'?'Starting market scan…':'Starting model evaluation…');$('progress').classList.remove('hidden');
  try{
    const r=await fetch(path,{method:'POST',headers:{'X-Praecursor':'local'}}),d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Could not start');
    text('progress',d.status);notifyUser(d.status==='already running'?'A task is already running.':task==='scan'?'Market scan started. Progress appears above.':'Model evaluation started. This may take a while.');
  }catch(e){text('progress',e.message);notifyUser('Could not start: '+e.message);setBusy(false);activeTask=null;}
  finally{requesting=false;}
}
async function status(){
  if(requesting||document.hidden)return;
  try{
    const r=await fetch('/api/status');if(!r.ok)throw new Error('Status unavailable');const s=await r.json();
    if(requesting)return;
    const was=busy; if(s.running&&!activeTask)activeTask=(s.stage_name||'').includes('model')?'train':'scan';
    setBusy(!!s.running);$('progress').classList.toggle('hidden',!busy&&!s.error);
    text('progress',s.error||(s.stage_name||'Processing')+' · '+(s.processed||0)+'/'+(s.total||0)+' symbols');
    if(was&&!busy){notifyUser(s.error?'Task stopped: '+s.error:'Task finished. Saved results updated.');activeTask=null;await load();}
  }catch(e){if(busy){$('progress').classList.remove('hidden');text('progress','Connection interrupted. The task may still be running; reconnecting…');}}
}
$('history-search').oninput=()=>renderHistory(true);
for(const id of ['history-session','history-result'])$(id).onchange=()=>renderHistory(true);
$('history-prev').onclick=()=>{historyPage--;renderHistory();};$('history-next').onclick=()=>{historyPage++;renderHistory();};
$('refresh').onclick=()=>load(true);$('scan').onclick=()=>action('/api/scan','scan');$('train').onclick=()=>action('/api/train','train');
$('search').oninput=render;$('filter').onchange=render;$('horizon').onchange=render;$('close-detail').onclick=()=>$('detail').close();
$('detail').addEventListener('click',event=>{if(event.target!==$('detail'))return;const r=$('detail').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('detail').close();});
load();
if(snapshotNode){for(const id of ['scan','train','refresh'])$(id).classList.add('hidden');document.querySelectorAll('.live-only').forEach(n=>n.classList.add('hidden'));document.querySelector('.brand').removeAttribute('href');}
else{status();let statusTimer=setInterval(status,3000);window.addEventListener('pagehide',()=>clearInterval(statusTimer));window.addEventListener('pageshow',event=>{if(event.persisted){status();statusTimer=setInterval(status,3000);}});}
