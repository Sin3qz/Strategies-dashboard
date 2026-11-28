import itertools, numpy as np, pandas as pd
from multiprocessing import Pool
DAYS = list(range(0, 20)) + [-1]
def lev(a):
    import engine as E
    K, c = a; rets = []
    for d in DAYS:
        s, _ = E.run(rankings={"a": (1, 3, 6, 12), "b": (3, 6, 12)}, K=K, Ls=range(c - 50, c + 51), day=d); s = s[s.index >= "1987-09-01"]; rets.append(s.pct_change())
    r = pd.concat(rets, axis=1).dropna().mean(axis=1); s = (1 + r).cumprod(); m = E.metrics(s); return ("lev", K, c, m["Sharpe"], m["CAGR"], m["MaxDD"])
def mr(a):
    import mrengine as ME, met
    so, lo = a; rets = []
    for d in DAYS:
        s = ME.run((75 + so, 125 + so), (175 + lo, 250 + lo), day=d); s = s[s.index >= "1995-07-01"]; rets.append(s.pct_change())
    r = pd.concat(rets, axis=1).dropna().mean(axis=1); s = (1 + r).cumprod(); m = met.metrics(s); return ("mr", so, lo, m["Sharpe"], m["CAGR"], m["MaxDD"])
def one(a):
    import gtaa1x as X, met
    S, L = a; s = X.run(S, L); m = met.metrics(s, X.RF); return ("1x", S, L, m["Sharpe"], m["CAGR"], m["MaxDD"])
if __name__ == "__main__":
    jobs = [(lev, a) for a in itertools.product(range(25, 56, 5), (175, 188, 200, 212, 225))] + \
           [(mr, a) for a in itertools.product((-13, 0, 12), (-12, 0, 13))] + [(one, a) for a in itertools.product(range(5, 26), range(150, 201, 5))]
    with Pool(4) as p: out = p.starmap(lambda f, a: f(a), jobs) if False else p.map(_run := None, []) if False else None
