import pickle, sys, numpy as np
from verify_stab import comp
w = sys.argv[1]
if w == "lev":
    L = pickle.load(open("joint_lev.pkl", "rb"))
    comp(L, [(("13612+3612", 50, 175), ("1369+3612", 30, 175))], "levGTAA 1/3/6/12+3/6/12, SMA50, 125-225 vs alt")
    comp(L, [(("13612+3612", K, 175), ("1369+3612", K2, 175)) for K in (45, 50, 55) for K2 in (25, 30, 35)], "  dto. Umgebung K45-55 vs K25-35")
    comp(L, [(("13612+3612", 50, c), ("13612+3612", 30, c)) for c in (150, 175, 200, 225, 250)], "levGTAA SMA50 vs 30 nur 1/3/6/12+3/6/12")
elif w == "1x":
    X = pickle.load(open("joint_1x.pkl", "rb"))
    comp(X, [((S, L, c, "1/3/6/12"), (S2, L2, c, "1/3/6/12")) for c in (8, 10, 12) for (S, L) in [(17, 160), (19, 160), (20, 170)] for (S2, L2) in [(7, 150), (8, 150), (9, 140)]], "1xGTAA (1/3/6/12) Umgebung 19/160 vs 8/150")
    comp(X, [((19, 160, c, "1/3/6/9"), (8, 150, c, "1/3/6/12")) for c in (8, 10, 12)], "1xGTAA neu (19/160, 1369) vs alt")
else:
    T = pickle.load(open("tipsfine_rets.pkl", "rb"))
    comp(T, [((s, 210, t, c), (s, 220, t, c)) for s in (270, 280, 290, 300) for t in (160, 200, 240) for c in (5, 10, 15)], "levTips TIPS 210 vs 220 (S&P 270-300)")
    comp(T, [((s, 210, t, c), (s, 220, t, c)) for s in (270, 280, 290, 300) for t in (160, 200, 240) for c in (5, 10, 15)], "  dto. ab 2001", "2001-06-01")
    comp(T, [((280, 210, 200, 10), (280, 220, 200, 10))], "levTips 280/210 vs 280/220")
