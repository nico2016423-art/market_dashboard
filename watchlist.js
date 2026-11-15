"use strict";
function parseList(text){
 const items=[],invalid=[],seen=new Set();let section="Focus";
 for(const part of text.replace(/^\uFEFF/,"").split(/[,\r\n]+/)){
  const raw=part.trim();if(!raw)continue;if(raw.startsWith("###")){section=raw.slice(3).trim().slice(0,100)||"Focus";continue;}
  const s=raw.toUpperCase(),bits=s.split(":"),ticker=bits.at(-1);
  if(bits.length>2||!/^(?:[A-Z]+:)?[A-Z0-9][A-Z0-9.\-^]{0,39}$/.test(s)||(bits.length===2&&!['NASDAQ','NYSE','AMEX','NYSEARCA','BATS','CBOE'].includes(bits[0]))){invalid.push(raw);continue;}
  if(!seen.has(ticker)){seen.add(ticker);items.push({ticker,symbol:s,section});}if(items.length>2000)throw new Error("最多2000個代號。");
 }
 return {items,invalid};
}
(()=>{
 const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const numeric=v=>typeof v==='number'&&Number.isFinite(v),key='apex-focus-r4';
 const groupsZh={'Indices':'市場基準','S&P Style ETFs':'標普風格ETF','Sel Sectors':'板塊ETF','EW Sectors':'等權板塊ETF','Industries':'行業／主題ETF','Countries':'國家市場','SRM Industries':'產業ETF'};
 let mode='etf',snapshot=[],rows=[],focus=[],focusText='',active='',sort={key:'',dir:1},dataNote='正在讀取ETF快照。',busy=false;
 const css=document.createElement('style');css.textContent='.view-tabs{display:flex;gap:8px;margin:10px 0}.view-tabs [aria-selected=true]{background:#35577c;border-color:#8cbfff}.view-tabs button{min-width:120px}.tab-note{font-size:12px;color:#a8b7cd;margin:6px 0}.empty-focus{padding:28px 12px;border:1px dashed #465772;border-radius:8px;line-height:1.8}.local-tag{color:#a4c9ff;font-size:11px}#notice{font-size:12px}.ticker-table td small{line-height:1.5}';document.head.append(css);
 $('site-version').textContent='R4 · ETF／本機Focus · 自身漲跌／均線';
 document.querySelector('h1').textContent='APEX ETF與個股觀察清單';
 const tabs=document.createElement('nav');tabs.className='view-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','切換觀察清單');tabs.innerHTML='<button id="tab-etf" role="tab" type="button" aria-selected="true" aria-controls="groups-container">ETF清單</button><button id="tab-focus" role="tab" type="button" aria-selected="false" aria-controls="groups-container" tabindex="-1">Focus（本機）</button>';
 document.querySelector('.tools').before(tabs);
 const localNote=document.createElement('p');localNote.className='tab-note';localNote.id='view-note';tabs.after(localNote);
 $('groups-container').setAttribute('role','tabpanel');$('groups-container').setAttribute('aria-labelledby','tab-etf');
 const refresh=document.createElement('button');refresh.type='button';refresh.textContent='重新讀取快照';$('export').after(refresh);
 document.querySelector('details.notes').innerHTML='<summary>欄位說明／其他工具</summary><p>即日、一星期、一個月均為標的自身漲跌，不扣除SPY。一星期使用5個交易日，一個月使用21個交易日。現階段為已完成日線快照，不是盤中即時報價；以行情日為準。</p><p>9／21為EMA；50為SMA。▲表示收市價高於均線，▼低於，＝相等；不是均線斜率。缺值顯示—，移到欄位可查看原因。</p><p>Focus名單只存目前瀏覽器，不上傳GitHub，也不自動同步TradingView。清除網站資料或改用其他瀏覽器後可能需要重新匯入，請保留TXT備份。已在ETF快照內的同代號可以使用該快照；其他股票的行情需另行取得。</p><p>分類資料按來源顯示，基金類別不冒充個股行業。自訂分組不是正式行業。</p><button id="calendar-open" type="button">經濟日曆</button>';
 try{const text=localStorage.getItem(key);if(text){const p=parseList(text);focus=p.items;focusText=text;}}catch(e){dataNote='無法讀取本機Focus；ETF清單不受影響。';}
 function percent(v){return numeric(v)?'<span class="'+(v>0?'up':v<0?'down':'flat')+'">'+(v>0?'+':'')+v.toFixed(1)+'%</span>':'—';}
 function ma(v,n,reason){return '<span class="'+(v===true?'up':v===false?'down':'flat')+'" title="'+esc(reason)+'">'+n+' '+(v===true?'▲':v===false?'▼':v==='equal'?'＝':'—')+'</span>';}
 function updateRows(){
  if(mode==='focus'){const lookup=new Map(snapshot.map(r=>[r.ticker,r]));rows=focus.map(p=>({...lookup.get(p.ticker),...p,groups:[p.section],pending:!lookup.has(p.ticker)}));}else rows=snapshot.slice();
  const old=$('category').value,options=[...new Set(rows.map(r=>r.sector||r.category||'分類待取得'))].sort();$('category').innerHTML='<option value="">全部板塊／類別</option>'+options.map(v=>'<option value="'+esc(v)+'">'+esc(v)+'</option>').join('');if(options.includes(old))$('category').value=old;
  $('import').textContent='匯入Focus TXT';$('reset').textContent=mode==='focus'?'清空本機Focus':'清除篩選';$('export').textContent=mode==='focus'?'備份Focus':'匯出ETF名單';$('export').disabled=!rows.length;
  $('view-note').textContent=mode==='etf'?'原有ETF清單保留；數值為標的自身漲跌。':'私人本機清單：不提交GitHub，不會隨TradingView自動更新。';
  render();
 }
 function switchMode(next){mode=next;active='';sort={key:'',dir:1};$('search').value='';$('category').value='';for(const m of ['etf','focus']){const b=$('tab-'+m);b.setAttribute('aria-selected',String(m===mode));b.tabIndex=m===mode?0:-1;}$('groups-container').setAttribute('aria-labelledby','tab-'+mode);$('notice').textContent=dataNote;updateRows();}
 $('tab-etf').onclick=()=>switchMode('etf');$('tab-focus').onclick=()=>switchMode('focus');tabs.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();switchMode(e.key==='Home'?'etf':e.key==='End'?'focus':mode==='etf'?'focus':'etf');$('tab-'+mode).focus();};
 function render(){
  const q=$('search').value.trim().toUpperCase(),c=$('category').value;
  const visible=rows.filter(r=>(!c||(r.sector||r.category||'分類待取得')===c)&&[r.ticker,r.name,r.sector,r.industry,r.category,...(r.groups||[])].join(' ').toUpperCase().includes(q));
  if(sort.key)visible.sort((a,b)=>{const x=a[sort.key],y=b[sort.key];if(x==null)return y==null?0:1;if(y==null)return -1;return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*sort.dir;});
  const grouped=new Map();for(const r of visible){const g=(r.groups||[])[0]||'觀察清單';if(!grouped.has(g))grouped.set(g,[]);grouped.get(g).push(r);}
  const heads=[['ticker','股票／名稱'],['sector','板塊／行業或基金類別'],['daily','即日'],['week','一星期'],['month','一個月'],['','均線位置 9／21／50']];
  $('groups-container').innerHTML=[...grouped].map(([g,list])=>'<section class="group-container"><div class="group-header"><span>'+esc(groupsZh[g]||g)+'</span><small>'+list.length+'檔</small></div><div class="table-scroll"><table class="ticker-table"><thead><tr>'+heads.map(([k,t])=>'<th>'+(k?'<button type="button" data-sort="'+k+'">'+t+(sort.key===k?(sort.dir===1?' ↑':' ↓'):'')+'</button>':t)+'</th>').join('')+'</tr></thead><tbody>'+list.map(r=>{
   const why=r.pending?'該股票未有可用快照，並未自動向TradingView抓取。':r.warning||'',reasons=r.reasons||{},tip='行情日：'+(r.date||'未知')+(why?'；'+why:'');
   const reason=k=>reasons[k]||(!numeric(r[k])?'等待自身日線計算結果':'');
   return '<tr class="ticker-row '+(active===r.ticker?'active':'')+'" data-ticker="'+esc(r.symbol||r.ticker)+'" title="'+esc(tip)+'"><td>'+esc(r.ticker)+'<small>'+esc(r.name||'名稱待取得')+'</small>'+(r.pending?'<small class="local-tag">本機名單 · 行情待取得</small>':'')+'</td><td>'+esc(r.sector||r.category||'分類待取得')+'<small>'+esc(r.industry||'')+'</small></td><td title="'+esc(reason('daily'))+'">'+percent(r.daily)+'</td><td title="'+esc(reason('week'))+'">'+percent(r.week)+'</td><td title="'+esc(reason('month'))+'">'+percent(r.month)+'</td><td class="ma">'+[9,21,50].map(n=>ma(r['ma'+n],n,reasons['ma'+n]||why||'價格相對均線位置；缺值表示未取得足夠日線。')).join('　')+'</td></tr>';
  }).join('')+'</tbody></table></div></section>').join('')||(mode==='focus'&&!focus.length?'<div class="empty-focus">Focus目前未匯入。<br>按「匯入Focus TXT」，選擇從TradingView匯出的美股清單。<br><small>此步只在本機保存名單，不會將私人清單公開，也不會自動取得新股票行情。</small></div>':'<p>沒有符合的項目。</p>');
  $('result-count').textContent=(mode==='etf'?'ETF':'Focus')+'：顯示 '+visible.length+' / '+rows.length+' 個代號｜各組內排序｜漲跌單位 %';
 }
 $('search').oninput=render;$('category').onchange=render;
 $('groups-container').addEventListener('click',e=>{const b=e.target.closest('[data-sort]');if(b){sort={key:b.dataset.sort,dir:sort.key===b.dataset.sort?-sort.dir:1};render();return;}const r=e.target.closest('.ticker-row');if(r){active=r.dataset.ticker.split(':').at(-1);document.querySelectorAll('.ticker-row').forEach(el=>el.classList.toggle('active',el===r));$('notice').textContent='已選取 '+r.dataset.ticker+'；外部切換須啟用APEX TradingView Link。';}});
 $('import').onclick=()=>$('file').click();$('file').onchange=async()=>{const f=$('file').files[0];try{if(!f)return;if(f.size>1024*1024)throw new Error('TXT超過1MB。');const text=await f.text(),p=parseList(text);if(!p.items.length)throw new Error('沒有可用美股代號。');if(focus.length&&!window.confirm('以這份TXT取代目前本機Focus？ETF清單不變。'))return;focus=p.items;focusText=text;let saved=true;try{localStorage.setItem(key,text);}catch(e){saved=false;}switchMode('focus');$('notice').textContent='已匯入 '+focus.length+' 個代號，'+(saved?'僅存本機。':'儲存失敗，僅本次有效。')+'未自動同步TradingView或下載行情。'+(p.invalid.length?' 略過 '+p.invalid.length+' 個不支援項目。':'');}catch(e){$('notice').textContent=e.message;}finally{$('file').value='';}};
 $('reset').onclick=()=>{if(mode==='focus'){if(!focus.length)return;if(!window.confirm('清空本機Focus？請先備份；TradingView原清單不受影響。'))return;try{localStorage.removeItem(key);}catch(e){$('notice').textContent='無法刪除本機儲存，已取消清空。';return;}focus=[];focusText='';updateRows();$('notice').textContent='已清空本機Focus；TradingView及ETF清單沒有修改。';}else{$('search').value='';$('category').value='';sort={key:'',dir:1};render();}};
 $('export').onclick=()=>{const text=mode==='focus'?focusText:rows.map(r=>r.symbol||r.ticker).join(',');if(!text)return;const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=mode==='focus'?'APEX_Focus_backup.txt':'APEX_ETF_list.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 async function get(path){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);try{const r=await fetch(path,{cache:'no-cache',signal:controller.signal});if(!r.ok)throw new Error('HTTP '+r.status);return await r.json();}finally{clearTimeout(timer);}}
 async function load(){if(busy)return;busy=true;refresh.disabled=true;try{const d=await get('data/watchlist.json');if(!Array.isArray(d.rows)||!d.as_of)throw new Error('快照格式不完整');snapshot=d.rows;const age=(Date.now()-Date.parse(d.as_of+'T00:00:00Z'))/86400000;$('status').textContent='行情日 '+d.as_of+'｜已完成日線快照'+(age>4?'｜注意：可能已過期':'');dataNote='快照產生時間 '+d.built_at+'。不是盤中即時行情；重新讀取只重讀已發布快照。';}catch(e){try{const [old,names]=await Promise.all([get('data/snapshot.json'),get('data/labels_zh.json').catch(()=>({}))]);if(!old.groups)throw new Error('沒有備援資料');const map=new Map();for(const [g,list]of Object.entries(old.groups))for(const r of list){if(!map.has(r.ticker))map.set(r.ticker,{ticker:r.ticker,symbol:r.ticker,name:names[r.ticker]||'',groups:[],daily:r.daily,week:r['5d'],month:null,date:null,warning:'舊快照行情日期未知',reasons:{month:'舊檔20日欄位不冒充21日漲跌；等待新快照',ma9:'缺少歷史日線',ma21:'缺少歷史日線',ma50:'缺少歷史日線'}});map.get(r.ticker).groups.push(g);}snapshot=[...map.values()];$('status').textContent='舊快照備援｜行情日期未知';dataNote='新版行情尚未可用；暫顯示舊清單原有即日及5日漲跌。21日漲跌及均線留空，不以相對SPY數字代替。';}catch(err){$('status').textContent='沒有可用快照';dataNote='行情讀取失敗；仍可使用本機Focus名單。';}}finally{busy=false;refresh.disabled=false;$('notice').textContent=dataNote;updateRows();}}
 refresh.onclick=load;
 let calendarReady=false;const overlay=$('economic-calendar-modal-overlay');function closeCalendar(){overlay.style.display='none';$('calendar-open').focus();}
 $('calendar-open').onclick=()=>{overlay.style.display='flex';$('calendar-close').focus();if(!calendarReady){calendarReady=true;const s=document.createElement('script');s.async=true;s.src='https://s3.tradingview.com/external-embedding/embed-widget-events.js';s.textContent=JSON.stringify({colorTheme:'dark',isTransparent:false,locale:'zh_TW',countryFilter:'us',importanceFilter:'-1,0,1',width:'100%',height:550});$('calendar-widget').innerHTML='<div class="tradingview-widget-container__widget"></div>';$('calendar-widget').append(s);}};$('calendar-close').onclick=closeCalendar;overlay.onclick=e=>{if(e.target===overlay)closeCalendar();};document.addEventListener('keydown',e=>{if(e.key==='Escape'&&overlay.style.display==='flex')closeCalendar();});
 switchMode('etf');load();
})();
