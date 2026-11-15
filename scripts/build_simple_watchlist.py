"""Add own 5/21-session returns without modifying the legacy SRM code."""
import build_watchlist as core

original_measure=core.measure

def measure(close,base):
    out=original_measure(close,base)
    for key,n in [('week',5),('month',21)]:
        out[key]=core.number((close.iloc[-1]/close.iloc[-n-1]-1)*100) if close is not None and len(close)>n else None
        if out[key] is None:
            out.setdefault('reasons',{})[key]='有效日線不足'+str(n+1)+'筆'
    return out

if __name__=='__main__':
    core.measure=measure
    core.main()
