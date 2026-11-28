import numpy as np, pandas as pd
def regret(df, dims, rad, per, extra=()):
    vals = df[list(dims)].values; out = []
    for i in range(len(df)):
        m = np.all([np.abs(vals[:, j] - vals[i, j]) <= rad[j] if rad[j] is not None else vals[:, j] == vals[i, j] for j in range(len(dims))], axis=0)
        out.append({**{f"g_{p}": df[p].values[m].mean() for p in per + list(extra)}})
    g = pd.DataFrame(out, index=df.index); df = pd.concat([df, g], axis=1)
    for p in per: df[f"reg_{p}"] = df[f"g_{p}"].max() - df[f"g_{p}"]
    df["maxregret"] = df[[f"reg_{p}" for p in per]].max(axis=1); return df
