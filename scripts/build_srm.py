# This Source Code Form is subject to the Mozilla Public License, v. 2.0.
# https://mozilla.org/MPL/2.0/
# SRM/Stage logic derived from SRM Pro + Stage, copyright starshiptrade.
# Modifications: Python daily snapshot port for APEX dashboard; not Pine-verified.
import ast
import json
from pathlib import Path
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
SRM=['XOP','XTL','XES','XAR','XSW','XBI','XNTK','XHS','XPH','XHE','KIE','KCE','XME','XRT','XSD','XHB','XTN','KBE','KRE']
EXTRA={'XTL':'電訊產業','XAR':'航空航天國防','XSW':'軟件產業','XNTK':'科技產業','XHS':'醫療服務','XPH':'製藥業','XSD':'半導體等權'}

def finite(v):
    return float(v) if pd.notna(v) and np.isfinite(v) else None

def stage_history(s):
    ma=s.rolling(150,min_periods=150).mean()
    slopes=(ma/ma.shift(20)-1)*100
    distances=(s/ma-1)*100
    current=pending=days=0
    result=[]
    for price,m,sl,di in zip(s,ma,slopes,distances):
        if pd.notna(sl) and pd.notna(di):
            if sl>1 and price>m*1.02:
                target=2
            elif sl < -1 and price<m*.98:
                target=4
            elif current==2:
                target=3 if sl<=1 or price<m*.98 else 2
            elif current==4:
                target=1 if sl>=-1 or price>m*1.02 else 4
            else:
                target=current
            if target!=current and target!=0:
                days=days+1 if pending==target else 1
                pending=target
                if days>=3:
                    current,pending,days=target,0,0
            else:
                pending=days=0
        else:
            pending=days=0
        result.append(dict(stage=current,candidate=pending,progress=days,slope=finite(sl),distance=finite(di)))
    if len(result)<2:
        return None
    value=result[-2].copy()
    value['date']=str(s.index[-2].date())
    return value

def metrics(frame,base,asof,is_stage=False,is_base=False,is_macro=False):
    out=dict(date=None,warning=None,absBull=None,relBull=None,uptrend=None,duration=None,rawMom=None,normMom=None,rsPosition=None,newHigh=None,daily=None,week=None,month=None,dist50=None,atr=None,atrDistance=None,stage=None)
    if frame is None or len(frame)<2:
        out['warning']='行情未取得'
        return out
    close=frame['Close']
    out['date']=str(close.index[-1].date())
    for key,n in [('daily',1),('week',5),('month',21)]:
        if len(close)>n:
            out[key]=finite((close.iloc[-1]/close.iloc[-n-1]-1)*100)
    if len(close)>=50:
        sma=close.rolling(50).mean().iloc[-1]
        out['dist50']=finite((close.iloc[-1]/sma-1)*100)
        tr=pd.concat([frame['High']-frame['Low'],(frame['High']-close.shift()).abs(),(frame['Low']-close.shift()).abs()],axis=1).max(axis=1)
        atr=tr.ewm(alpha=1/14,adjust=False).mean().iloc[-1]
        out['atr']=finite(atr/close.iloc[-1]*100)
        out['atrDistance']=finite((close.iloc[-1]-sma)/atr) if atr>0 else None
    if is_stage:
        out['stage']=stage_history(close)
    if asof is None or close.index[-1]!=asof:
        out['warning']='與SPY行情日期未對齊；暫不判斷趨勢'
        return out
    if is_macro:
        out['warning']='宏觀參考，不套用股票雙重趨勢'
        return out
    if len(close)<26:
        out['warning']='趨勢資料不足'
        return out
    e=close.ewm(span=21,adjust=False).mean()
    out['absBull']=bool(close.iloc[-1]>e.iloc[-1] and e.iloc[-1]>e.iloc[-2])
    if is_base:
        return out
    if base is None:
        out['warning']='缺少SPY基準'
        return out
    aligned=pd.concat([close,base],axis=1,join='inner').dropna()
    if len(aligned)<26 or aligned.index[-1]!=asof:
        out['warning']='相對資料不足／日期未對齊'
        return out
    price=aligned.iloc[:,0]
    ratio=price/aligned.iloc[:,1]
    pe=price.ewm(span=21,adjust=False).mean()
    rema=ratio.ewm(span=21,adjust=False).mean()
    ab=(price>pe)&(pe>pe.shift())
    rb=(ratio>rema)&(rema>rema.shift())
    up=ab&rb
    out['absBull']=bool(ab.iloc[-1])
    out['relBull']=bool(rb.iloc[-1])
    out['uptrend']=bool(up.iloc[-1])
    last_change=None
    for i in range(1,len(up)):
        if bool(up.iloc[i])!=bool(up.iloc[i-1]):
            last_change=i
    out['duration']=len(up)-last_change if last_change is not None else None
    raw=(ratio/ratio.shift(5)-1)*100
    std=raw.rolling(20,min_periods=20).std(ddof=0).replace(0,1)
    out['rawMom']=finite(raw.iloc[-1])
    out['normMom']=finite((raw/std).iloc[-1])
    if len(ratio)>=180:
        lo=ratio.rolling(180,min_periods=180).min().iloc[-1]
        hi=ratio.rolling(180,min_periods=180).max().iloc[-1]
        if hi!=lo:
            out['rsPosition']=finite((ratio.iloc[-1]-lo)/(hi-lo)*100)
    out['newHigh']=bool(ratio.iloc[-1]>=ratio.iloc[-20:].max()) if len(ratio)>=20 else None
    return out

def main():
    tree=ast.parse((ROOT/'scripts'/'build_data.py').read_text(encoding='utf-8'))
    config={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ['STOCK_GROUPS','LEVERAGED_ETFS']:
                    config[target.id]=ast.literal_eval(node.value)
    old=config['STOCK_GROUPS']
    groups={}
    for name,items in old.items():
        if name=='Industries':
            groups['SRM Industries']=SRM
        groups[name]=items
    names=json.loads((ROOT/'data'/'labels_zh.json').read_text(encoding='utf-8'))
    names.update(EXTRA)
    symbols=list(dict.fromkeys(['SPY']+[s for values in groups.values() for s in values]))
    errors={}
    prices={}
    try:
        raw=yf.download(symbols,period='5y',auto_adjust=True,group_by='ticker',threads=4,progress=False,timeout=20)
    except Exception as exc:
        raw=pd.DataFrame()
        errors['download']=str(exc)[:180]
    now=datetime.now(ZoneInfo('America/New_York'))
    cutoff=now.date() if now.time()>=time(16,15) else now.date()-timedelta(days=1)
    for ticker in symbols:
        try:
            frame=raw[ticker].copy()
            frame.index=pd.to_datetime(frame.index).tz_localize(None).normalize()
            frame=frame.loc[frame.index.date<=cutoff,['High','Low','Close']].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            frame=frame[(frame['Close']>0)&(frame['High']>0)&(frame['Low']>0)]
            frame=frame.groupby(level=0).last().sort_index()
            if len(frame)<2:
                raise ValueError('有效日線不足')
            prices[ticker]=frame
        except Exception as exc:
            errors[ticker]=str(exc)[:120]
    base=prices['SPY']['Close'] if 'SPY' in prices else None
    asof=base.index[-1] if base is not None else None
    computed={t:metrics(prices.get(t),base,asof,t in SRM,t=='SPY',t=='TLT') for t in symbols}
    output={}
    for group,tickers in groups.items():
        output[group]=[]
        for i,t in enumerate(tickers):
            row=dict(computed[t],ticker=t,name=names.get(t,''),original=i)
            lev=config.get('LEVERAGED_ETFS',{}).get(t,{})
            row['long']=lev.get('long',[])
            row['short']=lev.get('short',[])
            output[group].append(row)
    data=dict(groups=output,built_at=datetime.now(timezone.utc).isoformat(),as_of=str(asof.date()) if asof is not None else None,errors=errors,source='Yahoo Finance via yfinance',note='日線快照：一般交易日美東16:15前排除當日。ETF使用調整後價格。Stage固定落後資料最後一根日線；採5年歷史重播，初始化可能與TradingView不同。尚未逐項通過Pine對照測試。',params=dict(ema=21,momentum=5,stdev=20,threshold=1,position=180,stage_ma=150,stage_slope=20,stage_buffer=2,stage_threshold=1,stage_confirm=3))
    out=ROOT/'data'/'srm.json'
    out.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    print('SRM snapshot:',len(prices),'valid symbols;',len(errors),'errors. Homepage is never modified by this data job.')

if __name__=='__main__':
    main()
