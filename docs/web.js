'use strict';
// This page displays stored observations. It never solves or interpolates a scenario.
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {chi:'7.5',window:'short',group:'growth',sigmas:['0.9','1','1.1','1.5'],index:0};
const palette = {'0.9':'#2b506a','1':'#c0802f','1.1':'#59866d','1.5':'#a85048'};
const dash = {'0.9':'','1':'2 5','1.1':'8 5','1.5':'10 4 2 4'};
const groups = {
  growth:['output_per_person_growth','output_effective_labor_growth','ai_services_effective_labor_growth','capital_effective_labor_growth'],
  prices:['wage_growth','net_interest','ai_service_price'],
  shares:['labor_income_share','ai_revenue_output_share','profit_output_share','inference_output_share','research_output_share'],
  efficiency:['capability_frontier_ratio']
};
const titles = {output_per_person_growth:'Output per worker',output_effective_labor_growth:'Output / effective labor',ai_services_effective_labor_growth:'AI services / effective labor',capital_effective_labor_growth:'Capital / effective labor',wage_growth:'Wage growth',net_interest:'Net interest rate',ai_service_price:'AI-service price',labor_income_share:'Labor income',profit_output_share:'Developer net profit',inference_output_share:'Inference expenditure',research_output_share:'Research expenditure',ai_revenue_output_share:'AI-industry revenue',capability_frontier_ratio:'AI efficiency / upper bound'};
const units = {instantaneous_percent_per_year:'Growth · % per year',percent_per_year:'% per year',percent_of_output:'% of output',percent_of_upper_bound:'% of upper bound',final_good_per_ai_service:'Final-good units per AI service · log scale'};
let data, fields, shownIndices=[], readerReady=false, readerPromise, dataPromise, mathDone=false;

async function readJSON(path){const r=await fetch(path);if(!r.ok)throw Error(`Cannot load ${path}`);return r.json();}
function fail(where,error){$(where).innerHTML=`<p class="error">This part of the digital edition could not load. You can still <a href="paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf">read the PDF</a> or <a href="https://github.com/oliverpardo1979/ai-growth-and-labor">open the repository</a>.</p>`;console.error(error);}
function loadReader(){return readerPromise ||= (async()=>{
  const [meta,r]=await Promise.all([readJSON('generated/manuscript-meta.json'),fetch('generated/manuscript.html')]);
  if(!r.ok)throw Error('Manuscript unavailable');
  $('#manuscript').innerHTML=await r.text();
  $('#abstract-preview').innerHTML=`<p>${esc(meta.abstract)}</p>`;
  $('#paper-date').textContent=meta.date || 'Working paper';
  $('#source-stamp').textContent='Generated from the manuscript source. The PDF remains the typeset reference.';
  $('#contents').innerHTML=meta.sections.filter(s=>s.level<=2).map(s=>`<a class="level-${s.level}" href="#${encodeURIComponent(s.id)}">${esc(s.number ? `${s.number} ${s.title}`:s.title)}</a>`).join('');
  $$('#manuscript table').forEach(t=>{const w=document.createElement('div');w.className='table-wrapper';t.before(w);w.append(t);});
  if(matchMedia('(max-width:700px)').matches) $('.reader-sidebar details').open=false;
  readerReady=true; return meta;
})().catch(e=>{fail('#manuscript',e);fail('#abstract-preview',e);});}
async function typeset(){if(mathDone || !readerReady)return; if(window.MathJax?.startup?.promise){await MathJax.startup.promise;await MathJax.typesetPromise([$('#manuscript')]);mathDone=true;}}
async function route(){
  const hash=decodeURIComponent(location.hash.slice(1)) || 'overview';
  if(hash==='main'){ $('#main').scrollIntoView(); return; }
  const view=['overview','paper','explore','replicate'].includes(hash)?hash:'paper';
  $$('.view').forEach(n=>n.hidden=n.id!==view);$$('[data-view]').forEach(a=>a.setAttribute('aria-current',a.dataset.view===view?'page':'false'));
  if(view==='paper'){await loadReader();await typeset();if(hash!=='paper')document.getElementById(hash)?.scrollIntoView();}
  if(view==='explore')await loadData();
  if(['overview','paper','explore','replicate'].includes(hash)) window.scrollTo(0,0);
}
function selected(){return state.sigmas.map(s=>data.datasets[state.chi].scenarios[s]);}
function pretty(value,key){const f=fields[key];if(f.axis_scale==='log')return value<0.01?value.toExponential(2):value.toPrecision(3);return `${(value*f.display_scale).toFixed(1)}%`;}
function val(s,key,index){return index<0?s.pre_event[key]:s.columns[key][index];}
function timeAt(index){return index<0?-2:data.times[index];}
function nearest(t){if(t<0)return -1;let lo=0,hi=data.times.length-1;while(lo<hi){const m=(lo+hi)>>1;if(data.times[m]<t)lo=m+1;else hi=m;}if(lo>0&&Math.abs(data.times[lo-1]-t)<Math.abs(data.times[lo]-t))lo--;return lo;}
function inspect(index){state.index=index;$('#time-label').textContent=index<0?'Before RSI':`Year ${data.times[index].toFixed(1)}`;const p=shownIndices.indexOf(index);if(p>=0)$('#time-inspect').value=p;
  $('#values-table').innerHTML=`<table><caption class="sr-only">Stored values at ${index<0?'the pre-RSI reference':`year ${data.times[index]}`}</caption><thead><tr><th scope="col">Variable</th>${state.sigmas.map(s=>`<th scope="col">σ = ${Number(s).toFixed(1)}</th>`).join('')}</tr></thead><tbody>${groups[state.group].map(k=>`<tr><th scope="row">${titles[k]}</th>${selected().map(s=>`<td>${pretty(val(s,k,index),k)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function pathFor(points,x,y){return points.map(([t,v],i)=>`${i?'L':'M'}${x(t).toFixed(3)},${y(v).toFixed(3)}`).join('');}
function chart(key){
  const f=fields[key], scale=f.display_scale, log=f.axis_scale==='log', range=data.windows[state.window];
  const samples=shownIndices.filter(i=>i>=0), series=selected().map(s=>({s,points:samples.map(i=>[data.times[i],s.columns[key][i]])}));
  let values=series.flatMap(o=>o.points.map(p=>p[1]));if(state.window==='short')values.push(...selected().map(s=>s.pre_event[key]));
  const convert=v=>log?Math.log10(v):v*scale;
  let lo=Math.min(...values.map(convert)),hi=Math.max(...values.map(convert));
  if(!log&&lo>=0&&hi>0)lo=0;
  if(hi-lo<1e-10){const pad=Math.max(Math.abs(hi)*.1,0.1);lo-=pad;hi+=pad;}else{const pad=(hi-lo)*.06;lo-=pad;hi+=pad;}
  const W=440,H=300,L=78,R=18,T=14,B=48, pw=W-L-R, ph=H-T-B;
  const x=t=>L+(t-range[0])/(range[1]-range[0])*pw,y=v=>T+(hi-convert(v))/(hi-lo)*ph;
  const rough=(hi-lo)/4, mag=10**Math.floor(Math.log10(rough));
  const step=log?Math.max(1,Math.ceil(rough)):Math.max(.1,[1,2,2.5,5,10].find(v=>v*mag>=rough)*mag);
  lo=Math.floor(lo/step)*step;hi=Math.ceil(hi/step)*step;
  if(!log&&Math.min(...values)>=0)lo=0;
  const ticks=Array.from({length:Math.round((hi-lo)/step)+1},(_,i)=>lo+i*step);
  const xTicks=state.window==='short'?[-2,0,2,4,6,8,10]:[10,100,200,300,400,500];
  const tickLabel=v=>log?(10**v).toExponential(0):v.toFixed(1)+'%';
  const card=document.createElement('section');card.className='chart-card';
  card.innerHTML=`<h2>${titles[key]}</h2><p class="unit">${units[f.unit]}</p><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(titles[key]+': '+f.definition)}"><title>${esc(f.definition)}</title>${ticks.map(v=>{const yy=T+(hi-v)/(hi-lo)*ph;return `<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="#e5e8e4"/><text x="${L-10}" y="${yy+4}" text-anchor="end">${tickLabel(v)}</text>`;}).join('')}${xTicks.map(t=>`<text x="${x(t)}" y="${H-22}" text-anchor="middle">${t}</text>`).join('')}<text x="${L+pw/2}" y="${H-2}" text-anchor="middle">Years after RSI activation</text>${state.window==='short'?`<line x1="${x(0)}" x2="${x(0)}" y1="${T}" y2="${H-B}" stroke="#9fa8a3" stroke-dasharray="3 4"/>`:''}${series.map(({s,points})=>{const sig=String(s.sigma),style=`fill="none" stroke="${palette[sig]}" stroke-width="2.3" stroke-dasharray="${dash[sig]}"`;return `${state.window==='short'?`<path d="${pathFor([[-2,s.pre_event[key]],[0,s.pre_event[key]]],x,y)}" ${style} opacity=".6"/><path d="M${x(0)},${y(s.pre_event[key])}L${x(0)},${y(points[0][1])}" ${style} opacity=".6"/>`:''}<path d="${pathFor(points,x,y)}" ${style}/>`;}).join('')}<line class="crosshair" y1="${T}" y2="${H-B}" stroke="#97a7a1" visibility="hidden"/></svg><p class="chart-tip">Point to a curve or use the observation slider below.</p>`;
  const svg=card.querySelector('svg');svg.addEventListener('pointermove',e=>{const rect=svg.getBoundingClientRect();const raw=(e.clientX-rect.left)/rect.width*W;const t=range[0]+(Math.max(L,Math.min(W-R,raw))-L)/pw*(range[1]-range[0]);const index=nearest(t);inspect(index);const cross=svg.querySelector('.crosshair');cross.setAttribute('x1',x(index<0?t:data.times[index]));cross.setAttribute('x2',x(index<0?t:data.times[index]));cross.setAttribute('visibility','visible');card.querySelector('.chart-tip').textContent=selected().map(s=>`σ ${s.sigma.toFixed(1)}: ${pretty(val(s,key,index),key)}`).join(' · ');});
  return card;
}
function render(){if(!data)return;const range=data.windows[state.window];shownIndices=data.times.map((_,i)=>i).filter(i=>data.times[i]>=Math.max(0,range[0])&&data.times[i]<=range[1]);if(state.window==='short')shownIndices.unshift(-1);
  if(!shownIndices.includes(state.index))state.index=shownIndices[0];
  const keys=groups[state.group];$('#chart-grid').className=`chart-grid ${keys.length===1?'single':keys.length!==3?'four':''}`;$('#chart-grid').replaceChildren(...keys.map(chart));
  $('#time-inspect').max=shownIndices.length-1;inspect(state.index);
  const groupNote=state.group==='growth'?'Growth of Y/(AL), X/(AL), and K/(AL) is measured relative to effective labor. Output-per-worker growth adds the exogenous rate γ to growth of Y/(AL).':state.group==='shares'?'AI-industry revenue pays for inference compute and research, and leaves the developer’s net profit. Revenue is not profit; expenditure shares are measured against output.':state.group==='prices'?'The price panel uses a logarithmic scale. Wage growth and the interest rate are annual rates.':'The upper bound limits services per unit of compute, not total compute or AI services.';
  $('#scenario-note').textContent=`${groupNote} Axes fit the displayed observations and may change across selections; no theoretical limit is used to expand the short-run scale.`;
  const d=data.datasets[state.chi];$('#chart-source').innerHTML=`Source: <a href="${esc(d.provenance.raw_csv_url)}">download the original χ = ${state.chi} CSV</a> · <a href="#sec:rewrite-quantitative">Read the simulation design</a>. Values are stored observations; lines connect them without smoothing.`;
  const labels={alpha:'Capital output elasticity · α',rho:'Time preference · ρ',delta:'Depreciation · δ',eta:'Research elasticity · η',omega_x:'AI weight · ωX',omega_l:'Labor weight · ωL',population_growth:'Population growth · n',labor_productivity_growth:'Labor-augmenting progress · γ'};
  $('#data-details').innerHTML=`<p>Only the two published illustrative research productivities and four elasticities are selectable. No interpolation across parameters, no new equilibrium computation, and no extrapolation beyond year 500.</p><table>${Object.entries(data.parameters).map(([k,v])=>`<tr><td>${esc(labels[k]||k)}</td><td>${esc(typeof v==='number'?Number(v.toPrecision(6)):JSON.stringify(v))}</td></tr>`).join('')}</table><p>Current CSV SHA-256: <code style="overflow-wrap:anywhere">${esc(d.provenance.csv_sha256)}</code></p><p>The finite-cap equilibrium proposition gives local existence results under its stated conditions; these simulations do not establish global uniqueness. Household inequality is not identified by functional income shares in this representative-household model.</p>`;
}
function saveSelection(){const p=new URLSearchParams({chi:state.chi,window:state.window,group:state.group,sigma:state.sigmas.join(',')});history.replaceState(null,'',`${location.pathname}?${p}#explore`);}
function setupControls(){
  $$('[data-chi]').forEach(b=>b.addEventListener('click',()=>{state.chi=b.dataset.chi;$$('[data-chi]').forEach(n=>n.setAttribute('aria-pressed',n===b));render();saveSelection();}));
  $$('[data-window]').forEach(b=>b.addEventListener('click',()=>{state.window=b.dataset.window;$$('[data-window]').forEach(n=>n.setAttribute('aria-pressed',n===b));render();saveSelection();}));
  $$('[data-group]').forEach(b=>b.addEventListener('click',()=>{state.group=b.dataset.group;$$('[data-group]').forEach(n=>n.setAttribute('aria-pressed',n===b));render();saveSelection();}));
  $$('#sigma-controls input').forEach(c=>c.addEventListener('change',()=>{let sel=$$('#sigma-controls input:checked').map(n=>n.value);if(!sel.length){c.checked=true;return;}state.sigmas=sel;render();saveSelection();}));
  $('#time-inspect').addEventListener('input',e=>inspect(shownIndices[Number(e.target.value)]));
}
function restoreSelection(){const p=new URLSearchParams(location.search);for(const [k,valid]of Object.entries({chi:['7.5','1.5'],window:['short','long'],group:Object.keys(groups)}))if(valid.includes(p.get(k)))state[k]=p.get(k);const sig=(p.get('sigma')||'').split(',').filter(v=>Object.hasOwn(palette,v));if(sig.length)state.sigmas=[...new Set(sig)];for(const k of ['chi','window','group'])$$(`[data-${k}]`).forEach(b=>b.setAttribute('aria-pressed',b.dataset[k]===state[k]));$$('#sigma-controls input').forEach(c=>c.checked=state.sigmas.includes(c.value));}
function loadData(){return dataPromise ||= readJSON('generated/simulations.json').then(d=>{data=d;fields=Object.fromEntries(d.fields.map(f=>[f.key,f]));restoreSelection();render();}).catch(e=>fail('#chart-grid',e));}
setupControls();loadReader();window.addEventListener('hashchange',route);route();
