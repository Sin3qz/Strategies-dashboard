"""Neutrale Parameterauswahl: Nachbar-geglaettete Kennzahl, Bootstrap-Vergleich zweier Varianten, PBO."""
import itertools, math, numpy as np, pandas as pd
def smooth(df, dims, col, steps=1):
    """Mittel von col ueber alle Nachbarn (+-steps Gitterstufen je Dimension, inkl. selbst)."""
    levels = {d: sorted(df[d].unique()) for d in dims}; idx = {d: {v: i for i, v in enumerate(levels[d])} for d in dims}
    lut = {tuple(r[d] for d in dims): r[col] for _, r in df.iterrows()}; out = []
    for _, r in df.iterrows():
        vals = []
        for off in itertools.product(*[range(-steps, steps + 1)] * len(dims)):
            key = []
            for d, o in zip(dims, off):
                i = idx[d][r[d]] + o
                if not 0 <= i < len(levels[d]): break
                key.append(levels[d][i])
            else:
                v = lut.get(tuple(key)); vals.append(v) if v is not None else None
        out.append(np.mean(vals))
    return np.array(out)
def boot_diff(ra, rb, B=1000, block=63, seed=3):
    """Block-Bootstrap der Tagesrenditen zweier Varianten (gleiche Bloecke): Differenz CAGR und Sharpe, 90%-Intervall."""
    j = pd.concat([ra, rb], axis=1).dropna().values; n = len(j); rng = np.random.default_rng(seed); dc, ds = [], []
    for _ in range(B):
        st = rng.integers(0, n - block, n // block + 1); x = np.concatenate([j[s:s + block] for s in st])[:n]
        c = np.exp(np.log1p(x).sum(0) * 252 / n) - 1; s = x.mean(0) / x.std(0) * math.sqrt(252)
        dc.append(c[0] - c[1]); ds.append(s[0] - s[1])
    dc, ds = np.array(dc), np.array(ds)
    return (np.percentile(dc, 5), np.percentile(dc, 95), np.mean(dc > 0)), (np.percentile(ds, 5), np.percentile(ds, 95), np.mean(ds > 0))
def pbo(M, S=16):
    X = M.values; blocks = np.array_split(np.arange(len(M)), S); lam = []
    for comb in itertools.combinations(range(S), S // 2):
        m = np.zeros(len(M), bool); m[np.concatenate([blocks[i] for i in comb])] = True
        a, b = X[m], X[~m]; si = a.mean(0) / a.std(0); so = b.mean(0) / b.std(0); k = si.argmax()
        w = ((so < so[k]).sum() + 1) / (len(so) + 1); lam.append(math.log(w / (1 - w)))
    return np.mean(np.array(lam) <= 0)
