"""Apply narrowly scoped UI edits to the Pages deployment copy."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    names = json.loads((ROOT/'data'/'labels_zh.json').read_text(encoding='utf-8'))
    tree = ast.parse((ROOT/'scripts'/'build_data.py').read_text(encoding='utf-8'))
    groups = None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STOCK_GROUPS' for t in node.targets):
            groups = ast.literal_eval(node.value)
            break
    if groups is None:
        raise RuntimeError('無法核對股票名單，停止發布介面修改')
    missing = sorted({t for group in groups.values() for t in group} - names.keys())
    if missing:
        raise RuntimeError('缺少中文簡稱：'+','.join(missing))
    path = ROOT/'index.html'
    html = path.read_text(encoding='utf-8')
    if 'data-cn-localized="1"' in html:
        return
    def replace(old,new):
        nonlocal html
        if html.count(old)!=1:
            raise RuntimeError('首頁結構已變動，無法安全套用：'+old[:90])
        html=html.replace(old,new,1)
    replace('<html lang="zh-Hant">','<html lang="zh-Hant" data-cn-localized="1">')
    replace("['intra','日內','日內變動，沿用原始快照的計算口徑；並非即時報價。'],",'')
    replace("['daily','intra','5d','20d'].forEach", "['daily','5d','20d'].forEach")
    replace("['daily','當日','當日變動，沿用原始快照的計算口徑。']", "['daily','日漲跌','最新收市相對前一交易日收市的變動，包含開市跳空；並非即時報價。']")
    replace("['rs','1月-VARS','最近21日相對 SPY 的波動調整相對強度位置（0–100%），沿用原有計算。']", "['rs','強度位置','相對 SPY 的 ATR 調整強度經50日平滑後，在自身最近21期的百分位（0–100%）；不是跨股票排名，也不是 Deepvue RS Rating。']")
    replace("['rs','VARS','原有相對強度走勢圖；按此欄會依同一個 VARS 數值排序。']", "['rs','強度走勢','最近20期的50日平滑相對強度及其20日均線；不是0–100位置曲線。點擊按強度位置排序，公式不變。']")
    replace('function rowHtml(', 'var descriptions='+json.dumps(names,ensure_ascii=False).replace('<','\\u003c')+';\nfunction cnName(sym){return descriptions[sym]||"";}\nfunction rowHtml(')
    replace("+esc(r.ticker)+'</span></td><td>';", "+esc(r.ticker)+'</span><span class=\"ticker-desc\" title=\"'+esc(cnName(r.ticker))+'\">'+esc(cnName(r.ticker))+'</span></td><td>';")
    replace("row.hidden=!row.dataset.symbol.toUpperCase().includes(q);", "row.hidden=!(row.dataset.symbol+' '+cnName(row.dataset.symbol)).toUpperCase().includes(q);")
    replace('placeholder="搜尋代號，例如 SPY、SMH" aria-label="搜尋股票代號"', 'placeholder="搜尋代號／中文，例如 SMH、半導體" aria-label="搜尋代號或中文描述"')
    replace("$('selected-symbol').textContent=sym;", "$('selected-symbol').textContent=sym+(cnName(sym)?' · '+cnName(sym):'');")
    replace('name.textContent=sym;', "name.textContent=sym+(cnName(sym)?' · '+cnName(sym):'');")
    replace('.ticker-table th:first-child,.ticker-table td:first-child{text-align:left;width:76px}', '.ticker-table th:first-child,.ticker-table td:first-child{text-align:left;width:112px}')
    replace('.ticker-table th:nth-child(9){width:76px}.ticker-table th:nth-child(10){width:100px}', '.ticker-table th:nth-child(8){width:76px}.ticker-table th:nth-child(9){width:100px}')
    replace('</style>', '.ticker-desc{display:block;font-size:11px;color:#a8b7cd;margin-top:4px;line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n</style>')
    path.write_text(html,encoding='utf-8')
    print('Localized descriptions verified for',len({t for group in groups.values() for t in group}),'unique primary tickers; intraday display removed; strength formulas unchanged.')

if __name__=='__main__':
    main()
