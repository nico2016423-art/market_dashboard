(function(){
'use strict';
if(document.getElementById('market-overview'))return;
var style=document.createElement('style');
style.textContent='#market-overview{flex:0 0 auto;margin:8px 12px 0;border:1px solid #35435a;border-radius:8px;background:#171d28;color:#e5eaf3;font:12px Arial,"Microsoft JhengHei",sans-serif}#market-overview summary{cursor:pointer;padding:9px 12px;font-size:13px;font-weight:600}#market-overview .mo-body{padding:0 12px 10px;max-height:34vh;overflow:auto}#market-overview .mo-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:16px}#market-overview table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}#market-overview th,#market-overview td{padding:5px 6px;border-bottom:1px solid #303a4b;text-align:right}#market-overview th:first-child,#market-overview td:first-child{text-align:left}#market-overview .mo-states td:last-child{text-align:left}#market-overview .mo-up{color:#5ee2ae}#market-overview .mo-down{color:#ff9292}#market-overview .mo-neutral,#market-overview .mo-note{color:#a8b7cd}#market-overview .mo-note{font-size:11px;line-height:1.6;margin:6px 0}#market-overview .mo-brief{margin:3px 0 9px;line-height:1.6}#market-overview .mo-name{font-size:10px;color:#a8b7cd}#market-overview a{color:#a5cbff}#market-overview .mo-warn{color:#ffcd85;font-size:10px}#market-overview h2{font-size:12px;margin:0 0 5px}#market-overview button{font:inherit}@media(max-width:1050px){#market-overview .mo-grid{grid-template-columns:1fr}#market-overview .mo-body{max-height:55dvh}#market-overview{margin:8px 8px 0}}';
document.head.append(style);
var box=document.createElement('details');box.id='market-overview';box.open=!window.matchMedia('(max-width:1050px)').matches;box.innerHTML='<summary>市況總結／宏觀風險 <span id="mo-date"></span></summary><div class="mo-body" id="mo-content" role="status">正在載入獨立市況快照……</div>';
var workspace=document.querySelector('.workspace');if(workspace)workspace.before(box);else document.body.prepend(box);
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function number(v,dp,suffix,signed){return typeof v==='number'&&Number.isFinite(v)?(signed&&v>0?'+':'')+v.toFixed(dp)+(suffix||''):'—';}
function tone(v){return typeof v!=='number'?'mo-neutral':v>0?'mo-up':v<0?'mo-down':'mo-neutral';}
function render(d){
if(!Array.isArray(d.rows)||!Array.isArray(d.macros))throw new Error('快照格式不完整');
document.getElementById('mo-date').textContent='· SPY行情日 '+(d.as_of||'未知');
var brief=d.rows.map(function(r){return r.name+'：'+r.state;}).join('；');
var h='<div class="mo-brief">'+esc(brief)+'</div><div class="mo-grid"><section><h2>規則摘要（不是即時行情）</h2><table class="mo-states"><thead><tr><th scope="col">面向</th><th scope="col">狀態</th></tr></thead><tbody>';
d.rows.forEach(function(r){var cls=['up','down','neutral'].includes(r.tone)?r.tone:'neutral';h+='<tr title="'+esc(r.detail)+'"><td>'+esc(r.name)+'</td><td class="mo-'+cls+'">'+esc(r.state)+'</td></tr>';});
h+='</tbody></table><details><summary>查看判斷依據</summary>';
d.rows.forEach(function(r){h+='<p class="mo-note">'+esc(r.name)+'：'+esc(r.detail)+(r.date?'（'+esc(r.date)+'）':'')+'</p>';});
h+='</details></section><section><h2>宏觀／風險（點代號開啟 TradingView）</h2><table><thead><tr><th scope="col">標的</th><th scope="col">收市值</th><th scope="col">日漲跌</th><th scope="col">5日</th></tr></thead><tbody>';
d.macros.forEach(function(r){var isVix=r.ticker==='VIX';var href='https://www.tradingview.com/chart/?symbol='+encodeURIComponent(r.tv);h+='<tr title="行情日：'+esc(r.date||'未知')+'"><td><a target="_blank" rel="noopener noreferrer" href="'+esc(href)+'">'+esc(r.ticker)+'</a><div class="mo-name">'+esc(r.name)+'</div>'+(r.warning?'<div class="mo-warn">'+esc(r.warning)+'</div>':'')+'</td><td>'+number(r.close,2,'',false)+'</td><td class="'+(isVix?'mo-neutral':tone(r.daily))+'">'+number(r.daily,2,'%',true)+'</td><td class="'+(isVix?'mo-neutral':tone(r.change5))+'">'+number(r.change5,2,isVix?'點':'%',true)+'</td></tr>';});
h+='</tbody></table><p class="mo-note">VIX不套用股票ABC評級；5日變化以點數顯示。IEF是債價，不是10年期收益率；HYG不是信用利差本身。</p></section></div>';
var built=new Date(d.built_at);var stamp=Number.isNaN(built.getTime())?String(d.built_at||'未知'):built.toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false})+' HKT';
h+='<p class="mo-note">本區行情：'+esc(d.source)+'｜快照產生：'+esc(stamp)+'<br>'+esc(d.price_basis)+'<br>'+esc(d.rule_note)+'<br>本區獨立產生，可能與下方原有清單不同批次；行情日不代表快照產生日期。</p>';
document.getElementById('mo-content').innerHTML=h;
}
async function load(){var controller=new AbortController(),timer=setTimeout(function(){controller.abort();},15000);try{var res=await fetch('data/macro.json',{signal:controller.signal,cache:'no-cache'});if(!res.ok)throw new Error('HTTP '+res.status);render(await res.json());}catch(e){var el=document.getElementById('mo-content');el.textContent='未能取得市況快照，暫不作強弱判斷。';var b=document.createElement('button');b.type='button';b.textContent='重新載入';b.onclick=load;el.append(' ',b);}finally{clearTimeout(timer);}}
load();
})();
