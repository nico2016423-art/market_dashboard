"""Build simple daily watchlist snapshots. No homepage generation or trading actions."""
import ast
import json
import re
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'NASDAQ','NYSE','AMEX','NYSEARCA','BATS','CBOE'}
SECTORS={'Technology':'資訊科技','Financial Services':'金融','Healthcare':'醫療保健','Consumer Cyclical':'非必需消費','Consumer Defensive':'必需消費','Communication Services':'通訊服務','Industrials':'工業','Energy':'能源','Basic Materials':'原材料','Real Estate':'房地產','Utilities':'公用事業'}

def number(v):
    return float(v) if pd.notna(v) and np.isfinite(v) else None

def measure(close,base):
    out={k:None for k in ['daily','rel5','rel21','ma9','ma21','ma50']}
    reasons={}
    if close is None or len(close)<2:
        return dict(out,date=None,warning='未取得有效日線',reasons={k:'未取得有效日線' for k in out})
    out['date']=str(close.index[-1].date())
    out['daily']=number((close.iloc[-1]/close.iloc[-2]-1)*100)
    for n in [9,21,50]:
        k='ma'+str(n)
        if len(close)>=n:
            avg=close.rolling(n).mean().iloc[-1] if n==50 else close.ewm(span=n,adjust=False).mean().iloc[-1]
            out[k]='equal' if close.iloc[-1]==avg else bool(close.iloc[-1]>avg)
        else:
            reasons[k]='有效日線不足'+str(n)+'筆'
    for n in [5,21]:
        k='rel'+str(n)
        if base is None or len(base)<=n:
            reasons[k]='SPY基準不足'
            continue
        dates=base.index[-n-1:]
        aligned=close.reindex(dates)
        if close.index[-1]!=base.index[-1]:
            reasons[k]='行情日未與SPY對齊'
        elif aligned.isna().any():
            reasons[k]='比較期間缺少交易日資料'
        else:
            out[k]=number(((aligned.iloc[-1]/aligned.iloc[0]-1)-(base.iloc[-1]/base.iloc[-n-1]-1))*100)
    out['reasons']=reasons
    out['warning']='行情日落後SPY' if base is not None and close.index[-1]!=base.index[-1] else ''
    return out

def main():
    tree=ast.parse((ROOT/'scripts/build_data.py').read_text(encoding='utf-8'))
    groups=None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STOCK_GROUPS' for t in node.targets):
            groups=ast.literal_eval(node.value)
    if not groups:
        raise RuntimeError('找不到原有股票清單')
    membership={}
    symbols={}
    for g,tickers in groups.items():
        for t in tickers:
            membership.setdefault(t,[]).append(g)
            symbols[t]=t
    imported=ROOT/'data/watchlist.txt'
    if imported.exists():
        for raw in re.split(r'[,\r\n]+',imported.read_text(encoding='utf-8-sig')):
            raw=raw.strip().upper()
            if not raw or raw.startswith('###'):
                continue
            bits=raw.split(':')
            if len(bits)>2 or not re.fullmatch(r'(?:[A-Z]+:)?[A-Z0-9][A-Z0-9.\-^]{0,39}',raw) or (len(bits)==2 and bits[0] not in ALLOWED):
                raise ValueError('不支援的美股代號：'+raw)
            t=bits[-1]
            membership.setdefault(t,[])
            if '自選清單' not in membership[t]:
                membership[t].append('自選清單')
            symbols[t]=raw
    membership.setdefault('SPY',['市場基準'])
    symbols.setdefault('SPY','SPY')
    if len(symbols)>2000:
        raise ValueError('代號超過2000個')
    names=json.loads((ROOT/'data/labels_zh.json').read_text(encoding='utf-8'))
    now=datetime.now(ZoneInfo('America/New_York'))
    cutoff=now.date() if (now.hour,now.minute)>=(16,15) else now.date()-timedelta(days=1)
    histories={}
    errors={}
    for start in range(0,len(symbols),40):
        batch=list(symbols)[start:start+40]
        for attempt in range(2):
            try:
                raw=yf.download(batch,period='2y',auto_adjust=True,group_by='ticker',threads=2,progress=False,timeout=20)
                for t in batch:
                    try:
                        values=raw[t]['Close'] if isinstance(raw.columns,pd.MultiIndex) else raw['Close']
                        s=pd.to_numeric(values,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
                        s.index=pd.to_datetime(s.index).tz_localize(None).normalize()
                        s=s.loc[(s.index.date<=cutoff)&(s>0)].groupby(level=0).last().sort_index()
                        if len(s)<2:
                            raise ValueError('有效日線不足')
                        histories[t]=s
                    except Exception as exc:
                        errors[t]=str(exc)[:120]
                if all(t in histories for t in batch):
                    break
            except Exception as exc:
                errors['download']=str(exc)[:160]
            if attempt==0:
                time.sleep(3)
    base=histories.get('SPY')
    if base is None:
        raise RuntimeError('SPY下載失敗；保留上一份快照')
    age=(datetime.now(timezone.utc).date()-base.index[-1].date()).days
    if not 0<=age<=7:
        raise RuntimeError('SPY行情日期異常；保留上一份快照')
    core={t for values in groups.values() for t in values}
    valid=sum(t in histories and histories[t].index[-1]==base.index[-1] for t in core)
    if valid/max(1,len(core))<0.8:
        raise RuntimeError('原清單同日有效行情少於80%；保留上一份快照')
    path=ROOT/'data/watchlist.json'
    try:
        previous={r['ticker']:r for r in json.loads(path.read_text(encoding='utf-8')).get('rows',[])}
    except (OSError,ValueError,KeyError):
        previous={}
    today=datetime.now(timezone.utc).date()
    def metadata(t):
        old=previous.get(t,{})
        try:
            if old.get('classification_as_of') and (today-datetime.fromisoformat(old['classification_as_of']).date()).days<30:
                return t,{k:old.get(k,'') for k in ['sector','industry','category','assetType','classification_as_of','source_name']}
            info=yf.Ticker(t).get_info()
            if not info or not any(info.get(k) for k in ['quoteType','shortName','longName','sector','category']):
                raise ValueError('分類來源沒有回傳資料')
            return t,dict(sector=SECTORS.get(info.get('sector'),info.get('sector') or ''),industry=info.get('industry') or '',category=info.get('category') or '',assetType=info.get('quoteType') or '',source_name=info.get('shortName') or info.get('longName') or '',classification_as_of=today.isoformat())
        except Exception:
            return t,{k:old.get(k,'') for k in ['sector','industry','category','assetType','classification_as_of','source_name']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        meta=dict(pool.map(metadata,symbols))
    rows=[]
    for t,symbol in symbols.items():
        m=meta[t]
        row=dict(ticker=t,symbol=symbol,name=names.get(t) or m.get('source_name') or '',groups=membership[t],**measure(histories.get(t),base),**m)
        if t in histories:
            errors.pop(t,None)
        rows.append(row)
    output=dict(schema=1,as_of=str(base.index[-1].date()),built_at=datetime.now(timezone.utc).isoformat(),source='Yahoo Finance via yfinance; adjusted daily close',benchmark='SPY',rows=rows,errors=errors)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(output,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    temp.replace(path)
    print('Saved watchlist:',len(rows),'symbols;',valid,'same-date core symbols')

if __name__=='__main__':
    main()
