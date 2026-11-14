"""Prepare a deployment copy from saved snapshots, without network requests."""
import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape

ROOT=Path(__file__).resolve().parents[1]

def prepare(html,version,stamp,asof):
    if 'src="srm.js?v=1"' not in html:
        html,count=re.subn(r'<script>\s*\(function\(\)\{.*?</script>','<script src="srm.js?v=1"></script>',html,flags=re.S)
        if count!=1:
            raise RuntimeError('無法定位原清單程式，停止發布以免損壞首頁')
    if 'id="macro-overview-script"' not in html:
        if html.count('</body>')!=1:
            raise RuntimeError('首頁body標記不完整')
        html=html.replace('</body>','<script id="macro-overview-script" src="macro.js?v=1"></script>\n</body>',1)
    if 'id="external-tv-script"' not in html:
        if html.count('</body>')!=1:
            raise RuntimeError('首頁body標記不完整')
        html=html.replace('</body>','<script id="external-tv-script" src="external-tv.js?v=1"></script>\n</body>',1)
    html=html.replace('搜尋代號，例如 SPY、SMH','搜尋代號／中文，例如 XSD、半導體').replace('搜尋股票代號','搜尋代號或中文描述')
    if 'id="site-version"' not in html:
        if html.count('</header>')!=1:
            raise RuntimeError('首頁header標記不完整')
        badge='<span id="site-version" style="font-size:11px;color:#a8b7cd;line-height:1.6">版本 '+escape(version)+'<br>清單行情日 '+escape(asof)+'｜快照產生 '+escape(stamp)+'</span>'
        html=html.replace('</header>',badge+'</header>',1)
    return html

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default='local')
    args=parser.parse_args()
    srm_path=ROOT/'data'/'srm.json'
    macro_path=ROOT/'data'/'macro.json'
    if not srm_path.exists() or not macro_path.exists():
        raise RuntimeError('尚無保存的SRM／宏觀快照，請先執行 Refresh dashboard data')
    srm=json.loads(srm_path.read_text(encoding='utf-8'))
    macro=json.loads(macro_path.read_text(encoding='utf-8'))
    if not isinstance(srm.get('groups'),dict) or not isinstance(macro.get('rows'),list):
        raise RuntimeError('保存的快照格式不完整')
    names=json.loads((ROOT/'data'/'labels_zh.json').read_text(encoding='utf-8'))
    for rows in srm['groups'].values():
        for row in rows:
            if row.get('ticker') in names:
                row['name']=names[row['ticker']]
    srm_path.write_text(json.dumps(srm,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    built=datetime.fromisoformat(srm['built_at'].replace('Z','+00:00'))
    stamp=built.astimezone(ZoneInfo('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M HKT')
    page=ROOT/'index.html'
    page.write_text(prepare(page.read_text(encoding='utf-8'),args.version,stamp,str(srm.get('as_of') or '未知')),encoding='utf-8')
    print('Prepared deployment from saved snapshots; no market data downloaded.')

if __name__=='__main__':
    main()
