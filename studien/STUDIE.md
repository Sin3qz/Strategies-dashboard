# Studie 28.10.2026: Robustheit levGTAA, levTipsRegime, 1xGTAA

Alle Rechnungen nutzen den Code der Bot-Repos (Signale unverändert). Handel zum Schluss des Handelstags nach dem
Signal, 0,1 % Kosten je umgeschichtetem Euro, Cash ohne Zins. Synthetisch mit gehebelten Tagesrenditen der
Signalbasis (3x = 3 × Tagesrendite), daher ohne Produktgebühren und Swapkosten — für **Vergleiche zwischen Varianten**
gedacht, nicht als Prognose. Kein Anlageratschlag.

Zeitraum: Yahoo-Daten. TIP und IEF gibt es dort erst ab 2002/2003, EEMS ab 2011, Bitcoin ab 2014. Deine eigenen
Backtests ab 1987 reichen weiter; diese Studie ist eine unabhängige Gegenprobe der jüngeren Jahre.

Nachrechnen: Bot-Repos neben diesem Repo klonen (oder `BOT_REPO_DIR` setzen), dann z. B.
`python3 studien/levtips_robust.py`, `python3 studien/levgtaa_run.py`, `python3 studien/gtaa1x_run.py`.

## 1. levTipsRegime (ab 10/2004; Markt = 75 % 3x S&P 500 TR + 25 % BTC ab 2014, davor 100 % 3x S&P)

| Variante | CAGR | Max-DD | Sharpe |
|---|---|---|---|
| Neu: SMA280/220, IEF mit TLT/SMA200, Cooldown 10 | 41,1 % | −42,8 % | 1,23 |
| Alt ohne IEF | 38,0 % | −42,8 % | 1,18 |
| Ensemble (Mehrheit über S&P 240–320 / TIPS 180–260) | 41,3 % | −42,8 % | 1,23 |

- **IEF-Zweig:** in allen 400 SMA/Cooldown-Kombinationen höhere CAGR (Median +2,8 Pp), Max-DD unverändert.
  Aber: **seit 2019 in 81 % der Kombinationen schlechter** (Median −2,2 Pp; Zinswende 2022). Mit echten Produkten
  ab 12/2014 (Dashboard, EUR) etwa gleichauf (42,7 % neu vs. 43,5 % alt).
- **TLT-SMA-Länge** 125–250 fast egal (40,7–41,2 %): robust.
- **TIPS-SMA 220** sieht in Einzelwerten wie eine Spitze aus (200 und 240 je ~36 %), das Ensemble über 180–260 liefert
  aber dasselbe Ergebnis wie 220 → kein Zufallstreffer einer einzelnen Zahl.
- **Cooldown:** 10 ist das beste Verhältnis aus Rendite und Drawdown (5: mehr Wechsel, tieferer DD; 15/20: schlechter).

## 2. levGTAA (ab 06/2004)

| Parameter | Spanne getestet | CAGR-Spanne |
|---|---|---|
| Kurz-SMA K | 10–60 | 39,1–41,0 % |
| Lang-SMA-Bereich | 100–200 … 175–275 | 39,7–41,8 % |
| Vol-Target | aus, 40–85 % | 38,2–41,1 % |
| Ranglisten | 6 Sets | 39,5–42,2 % |
| Tilt Platz 1/2 | 30/70 … 60/40 | 38,4–42,7 % (60/40: Max-DD −50 %) |

Aktuell (SMA30, L 125–225, 1/3/6/9 + 3/6/12, 40/60, VT 55 %): **40,5 % CAGR, −44,5 % Max-DD, Sharpe 1,16**.
Sehr flache Hochebene → robust parametriert. **Größtes Risiko ist der Handelstag:** über alle 21 Monatstage
CAGR 34,8–42,1 % (Mittel 37,9 %), Max-DD bis −62 %. Der Monatsletzte liegt im oberen Bereich.

## 3. 1xGTAA (ab 2013; lange Historie ab 06/2008 mit EEM statt EEMS und EZU statt EMU Value vor deren Start)

Rhythmus (aktuelle Parameter): täglich mit Cooldown 10 = 13,4 % / −20,8 % / Sharpe 1,03; monatlich über alle
21 Tranchen Mittel 13,0 % (11,1–15,0 %), Sharpe 0,99 → **kein Vorteil für monatlich**, die Spanne ist Zufall des Tages.

Parameter (294 Kombinationen je Rhythmus): **Momentum 1/3/6/12 statt 1/3/6/9** ist durchgängig besser
(alle 49 SMA-Kombis Sharpe > 1; Ø CAGR 15,4 % statt 13,1 %; Ø Max-DD −15,5 % statt −20,6 %). SMA-Längen: Plateau
bei L 150–200, S 5–15.

| ab 06/2008 (täglich, Cooldown 10, SMA8/150, 40/60) | CAGR | Max-DD | Sharpe | Jahre besser |
|---|---|---|---|---|
| aktuell MoM 1/3/6/9 | 12,6 % | −20,8 % | 0,94 | – |
| **MoM 1/3/6/12** | **15,0 %** | **−17,1 %** | **1,10** | 13 von 19 |

Kostenstabil (0,05–0,40 % je Umschichtung: Vorsprung 2,3–2,8 Pp). Gewichte 50/50 oder levGTAA-Ensemble bringen
zusammen mit 1/3/6/12 nichts zusätzlich.

## Empfehlung

1. **levGTAA:** so lassen. Optional die Abhängigkeit vom Handelstag senken, indem du die Monatsumschichtung auf
   2–3 Handelstage verteilst (z. B. je ein Drittel am 1., 2. und 3. Handelstag).
2. **levTipsRegime:** SMA280/220/Cooldown 10 lassen. Der IEF-Zweig ist langfristig positiv und senkt kein Risiko;
   seit 2019 hat er geschadet. Wenn du ihn behältst: beobachten (Dashboard zeigt „alte Regel“ zum Vergleich).
3. **1xGTAA:** Momentum auf **1/3/6/12** umstellen, sonst alles lassen (täglich, Cooldown 10, SMA8/150, 40/60).
   Eine Zeile in `strategies/constants.py` (`lookbacks=(1,3,6,12)`); Warmup 252 Tage ist mit der Datenhistorie gedeckt.
