"""Generate macro/overview data and inject its UI into the deployment copy only."""
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
SECTORS = ['XLK','XLI','XLC','XLF','XLU','XLY','XLRE','XLP','XLB','XLE','XLV']
MACROS = [('UUP','美元走勢','AMEX:UUP'),('IEF','中期美債','NASDAQ:IEF'),('HYG','高收益債','AMEX:HYG'),('^VIX','預期波動','CBOE:VIX')]

def trend(s):
    if s is None or len(s) < 26:
        return None
    e = s.ewm(span=21, adjust=False).mean()
    if s.iloc[-1] > e.iloc[-1] and e.iloc[-1] > e.iloc[-6]:
        return '偏強'
    if s.iloc[-1] < e.iloc[-1] and e.iloc[-1] < e.iloc[-6]:
        return '偏弱'
    return '分歧'

def relative(a, b):
    if a is None or b is None:
        return None
    c = pd.concat([a,b], axis=1, join='inner').dropna()
    if len(c) < 21 or c.index[-1] != a.index[-1] or c.index[-1] != b.index[-1]:
        return None
    return float(((c.iloc[-1,0]/c.iloc[-21,0]-1)-(c.iloc[-1,1]/c.iloc[-21,1]-1))*100)

def main():
    prices, errors = {}, {}
    tickers = list(dict.fromkeys(['SPY','QQQ','RSP','IWM'] + SECTORS + [x[0] for x in MACROS]))
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period='1y', auto_adjust=True, timeout=20)
            if h.empty or 'Close' not in h:
                raise ValueError('沒有歷史價格')
            s = pd.to_numeric(h['Close'], errors='coerce').dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            s = s.groupby(level=0).last().sort_index()
            s = s[(s > 0) & (s < float('inf'))]
            if len(s) < 2:
                raise ValueError('有效價格不足')
            prices[t] = s
        except Exception as exc:
            errors[t] = str(exc)[:180]
    spy = prices.get('SPY')
    asof = spy.index[-1] if spy is not None else None
    def fresh(s):
        return s is not None and asof is not None and s.index[-1] == asof
    rows = []
    def add(name, state, detail, tone='neutral', date=None):
        rows.append(dict(name=name,state=state,detail=detail,tone=tone,date=date))
    qqq = prices.get('QQQ')
    if fresh(spy) and fresh(qqq) and trend(spy) and trend(qqq):
        a, b = trend(spy), trend(qqq)
        state = a if a == b and a in ['偏強','偏弱'] else '分歧'
        add('大市趨勢',state,'SPY：'+a+'；QQQ：'+b+'。依價格相對21EMA及21EMA的5日方向判斷。','up' if state=='偏強' else 'down' if state=='偏弱' else 'neutral',str(asof.date()))
    else:
        add('大市趨勢','資料不足／日期未對齊','需要同日 SPY、QQQ 及至少26個有效交易日。')
    for ticker, name, positive, negative in [('RSP','市場參與代理','等權領先','權重領先'),('IWM','小盤相對表現','小盤領先','小盤落後')]:
        s = prices.get(ticker)
        value = relative(s,spy) if fresh(s) and fresh(spy) else None
        if value is None:
            add(name,'資料不足／日期未對齊','需要與 SPY 同日且有21個共同交易日。')
        else:
            state = positive if value > 0 else negative if value < 0 else '持平'
            add(name,state,ticker+' 相對 SPY 的20日報酬差：'+format(value,'+.2f')+' 個百分點；這是代理觀察，不是真正市場寬度。','up' if value>0 else 'down' if value<0 else 'neutral',str(asof.date()))
    valid = [prices[t] for t in SECTORS if t in prices and fresh(prices[t]) and len(prices[t]) >= 21]
    count = sum(int(s.iloc[-1] > s.ewm(span=21,adjust=False).mean().iloc[-1]) for s in valid)
    if len(valid) == 11:
        add('板塊參與',str(count)+'/11 站上21EMA','固定11個核心板塊；只比較當日位置，不表示參與度正在改善。',date=str(asof.date()))
    else:
        add('板塊參與','資料不全',str(count)+'/'+str(len(valid))+' 個同日有效板塊站上21EMA；應有11個。',date=str(asof.date()) if asof is not None else None)
    vix = prices.get('^VIX')
    if fresh(vix) and len(vix) >= 6:
        d = float(vix.iloc[-1]-vix.iloc[-6])
        state = '升溫' if d > 0 else '降溫' if d < 0 else '持平'
        add('波動環境',state,'VIX '+format(vix.iloc[-1],'.2f')+'；5日變化 '+format(d,'+.2f')+' 點。並非市場升跌預測。','down' if d>0 else 'up' if d<0 else 'neutral',str(vix.index[-1].date()))
    else:
        add('波動環境','資料不足／日期未對齊','需要與 SPY 同日的 VIX 及6個有效交易日。')
    macros = []
    for ticker,name,tv in MACROS:
        s = prices.get(ticker)
        item = dict(ticker='VIX' if ticker=='^VIX' else ticker,name=name,tv=tv,close=None,daily=None,change5=None,date=None,warning=None)
        if s is not None:
            item.update(close=float(s.iloc[-1]),daily=float((s.iloc[-1]/s.iloc[-2]-1)*100),date=str(s.index[-1].date()))
            if len(s)>=6:
                item['change5']=float(s.iloc[-1]-s.iloc[-6]) if ticker=='^VIX' else float((s.iloc[-1]/s.iloc[-6]-1)*100)
            if not fresh(s):
                item['warning']='與 SPY 行情日期未對齊，或缺少 SPY 基準'
        else:
            item['warning']='行情未取得'
        macros.append(item)
    data = dict(built_at=datetime.now(timezone.utc).isoformat(),as_of=str(asof.date()) if asof is not None else None,source='Yahoo Finance via yfinance',price_basis='ETF使用調整後日線價格；變動按供應商數據計算。VIX為指數點數。',rows=rows,macros=macros,errors=errors,rule_note='依最新一日規則判斷，未套用連續兩日確認，未經策略回測；僅為市場觀察，不是買賣或倉位建議。')
    out = ROOT/'data'/'macro.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    page = ROOT/'index.html'
    html = page.read_text(encoding='utf-8')
    if 'id="macro-overview-script"' not in html:
        if '</body>' not in html:
            raise RuntimeError('首頁缺少 body 結束標籤；停止注入')
        html = html.replace('</body>','<script id="macro-overview-script" src="macro.js?v=1"></script>\n</body>',1)
        page.write_text(html,encoding='utf-8')
    print('Macro data generated:',len(prices),'available;',len(errors),'failed. Deployment copy prepared.')

if __name__ == '__main__':
    main()
