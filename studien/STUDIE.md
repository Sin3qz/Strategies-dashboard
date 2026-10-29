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

## Nachtrag 28.10.2026 (Abend): Entscheidungen und Gegenproben

**levTipsRegime ohne Bitcoin (100 % 3x S&P 500 im Markt), Regel mit IEF (TLT/SMA200), Cooldown 10:**
synthetisch ab 10/2004 36,1 % CAGR / −49,2 % Max-DD / Sharpe 1,07 (alte Regel ohne IEF 33,2 %). IEF-Zweig in allen
100 SMA-Kombinationen vorn (Median +2,8 Pp), seit 2019 in 84 % hinten (Median −1,6 Pp). TLT-SMA 150/200/250:
35,7/36,1/36,1 % → SMA200 passt. Mit echten Produkten ab 12/2014 (Dashboard): 30,6 % / −52 % (mit 25 % Bitcoin waren es
42,7 % / −44 %).

**1xGTAA – ist 1/3/6/12 überangepasst?** (ab 07/2009, täglich, Cooldown 10, 16 SMA-Kombinationen S 5–15 / L 125–200)

| Momentum | CAGR (Median) | Max-DD | 2009–14 | 2015–20 | 2021–26 |
|---|---|---|---|---|---|
| 1/3/6/9 (alt) | 13,3 % | −20,8 % | 13,5 % | 9,7 % | 17,1 % |
| **1/3/6/12** | **14,9 %** | **−17,1 %** | 12,8 % | 10,9 % | 21,1 % |
| 1/3/6/9/12 | 14,1 % | −14,5 % | 14,3 % | 12,6 % | 15,4 % |
| Nachbarn 1/3/6/10, /11, /13 | 13,8 / 13,0 / 12,0 % | | | | |

- In allen 16 SMA-Kombinationen 2015–20 und 2021–26 vorn, 2009–14 in 15 von 16 leicht hinten.
- Die 4. Länge ist verrauscht (Nachbarn 11 und 13 schwächer) → realistisch eher +0,5 bis +1 Pp statt +1,6 Pp.
- 12 Monate ist die Standardlänge der Momentum-Literatur (Faber, Antonacci, Keller „13612“), nicht aus den Daten gesucht.
- Fazit: kein Hinweis auf grobe Überanpassung, der Vorsprung ist aber kleiner als die Tabelle zeigt. Umgestellt.

**1xGTAA-Cooldown** (1/3/6/12, Median über 16 SMA-Kombinationen): 0 Tage 10,8 %, 3: 13,1 %, 5: 14,6 %, 8: 13,8 %,
**10: 14,9 %**, 12: 12,9 %, 15: 14,7 %, 20: 12,6 % → Hochebene 5–15, 10 liegt in der Mitte → bleibt.

**1xGTAA-Produkte (in EUR, wöchentlich):**
- Rohstoffe: einen UCITS-ETF auf den DBC-Index (DBIQ Optimum Yield Diversified) gibt es nicht mehr (der Xtrackers DBLCI
  OY wurde 2021 auf Bloomberg ex-Agriculture umgestellt). Ab 02/2017 gegen DBC: Invesco Bloomberg (CMOD) 7,0 % p. a.
  (Korr. 0,90), **WisdomTree Enhanced Commodity USD Acc (IE00BYMLZY74, Xetra WTIC; TER 0,23 %, 428 Mio. €)** 8,3 %
  (Korr. 0,90), DBC 9,6 %. WisdomTree rollt ähnlich optimiert wie DBC → neues Produkt.
- Cash: BIL in EUR gegen Xeon (EUR-Geldmarkt) Korrelation 0,07, Jahresabweichung bis ±13 Pp (Dollarkurs). **Xtrackers II
  USD Overnight Rate Swap 1C (LU0321465469, Xetra XFFE; TER 0,10 %, 357 Mio. €)** seit 2015 je Jahr ≤ 1 Pp neben BIL →
  neues Produkt (bildet das Signal ab; trägt wie die übrigen 1xGTAA-ETFs das Dollar-Risiko).
- Mit Produkten ab 08/2022 (Dashboard): 18,0 % CAGR / −10,1 % Max-DD (vorher 13,3 % / −13 %).

**levGTAA – täglich mit Cooldown statt monatlich?** (synthetisch ab 06/2004, gleicher Kern, Vol-Target 55 %; umschichten,
wenn sich die Bausteine ändern oder der Umschlag eine Schwelle übersteigt, danach Sperre)

| Variante | CAGR | Max-DD | Umschichtungen/Jahr |
|---|---|---|---|
| **monatlich (aktuell)** | **40,5 %** | **−44,5 %** | 12 |
| täglich, Cooldown 10, nur bei Baustein-Wechsel | 41,2 % | −46,9 % | 9 |
| täglich, Cooldown 10, Schwelle 10 % / 20 % / 30 % | 37,5 / 40,7 / 40,9 % | −46,9 % | 10–14 |
| täglich, Cooldown 5 (alle Schwellen) | 36,0–39,0 % | −45 bis −47 % | 13–22 |
| täglich, Cooldown 15 / 21 (alle Schwellen) | 37,6–38,9 % / 34,8–40,0 % | bis −58 % | 7–11 |

Nur eine von 16 Varianten ist knapp besser (+0,7 Pp bei tieferem Drawdown), die meisten schlechter → monatlich bleibt.
Grund: levGTAA mittelt über 202 Teilentscheidungen und skaliert per Vol-Target; die Zielquoten ändern sich fast täglich ein
wenig, ein „Wechsel“ ist nicht klar definiert und das Ergebnis hängt an willkürlichen Schwellen. 1xGTAA dagegen kennt nur
„Baustein qualifiziert ja/nein“ (Top-2, 40/60) – ein Wechsel ist eindeutig, die tägliche Prüfung reagiert früher und es
entfällt das Glück des Handelstags (monatliche Tranchen 11,1–15,0 %).

**1xGTAA – SMA-Längen (Momentum 1/3/6/12, täglich, Cooldown 10, ab 07/2009, 56 Kombinationen; lange Historie mit EEM vor
EEMS und EZU vor EMU Value)**

CAGR in % (Zeile = kurze SMA S, Spalte = lange SMA L):

| S \ L | 100 | 125 | 150 | 175 | 200 | 225 | 250 |
|---|---|---|---|---|---|---|---|
| 1 | 11,6 | 12,2 | 13,8 | 14,1 | 14,5 | 14,5 | 14,8 |
| 3 | 11,9 | 13,7 | 13,4 | 14,6 | 15,2 | 14,4 | 14,5 |
| 5 | 11,3 | 14,0 | 14,5 | 15,1 | 14,7 | 14,4 | 14,4 |
| **8** | 11,8 | 14,0 | **15,1** | 15,3 | 15,1 | 14,9 | 14,4 |
| 10 | 12,5 | 13,9 | 15,2 | 15,5 | 15,0 | 14,6 | 14,4 |
| 15 | 13,3 | 13,9 | 14,7 | 15,1 | 14,3 | 14,4 | 14,1 |
| 20 | 12,9 | 13,2 | 14,6 | 14,7 | 14,1 | 13,8 | 13,8 |
| 30 | 12,0 | 13,2 | 13,7 | 14,0 | 14,0 | 13,8 | 13,2 |

- SMA8/150: 15,1 % CAGR, −17,1 % Max-DD, Sharpe 1,12 (Platz 8 von 56 nach CAGR, Platz 6 nach Sharpe).
- Hochebene S 5–15 / L 150–200: 14,3–15,5 % CAGR, Sharpe 1,07–1,14 → 8/150 liegt mitten drin, kein Ausreißer.
- Nur L = 100 (11–13 %) und S = 30 fallen klar ab.
- Out-of-Sample: Das beste Paar auf 2009–2017 (10/175, 11,9 %) brachte 2018–2026 18,9 %; 8/150 brachte 18,4 %
  (Median aller Paare 17,8 %). Rangkorrelation In- zu Out-of-Sample 0,59 → die Hochebene ist stabil, die Wahl innerhalb
  der Hochebene ist Rauschen. **Ergebnis: SMA8/150 beibehalten.**

**1xGTAA – zusätzliches Rebalancing auf 40/60, solange die Position gleich bleibt?** (ab 07/2009, 1/3/6/12, Cooldown 10,
0,1 % Kosten; Median über 16 SMA-Kombinationen, dazu SMA8/150)

| Variante | CAGR 8/150 | Max-DD 8/150 | Umschichtungen/Jahr | Median CAGR (16 SMA) |
|---|---|---|---|---|
| **keins (Bot heute)** | **15,1 %** | **−17,1 %** | 16,9 | 14,9 % |
| alle 21 Handelstage nach dem Kauf | 15,0 % | −17,1 % | 20,1 | 14,8 % |
| alle 42 / 63 / 126 Tage | 15,0 / 15,1 / 15,1 % | −17,1 % | 17,5 / 17,1 / 16,9 | 14,8–14,9 % |
| am Monatsende | 15,1 % | −16,9 % | 28,9 | 14,9 % |
| bei Drift > 5 / 10 / 15 Pp | 15,1 % | −17,1 % | 16,9 | 14,9 % |
| Kontrolle: Drift > 0,5 / 1 / 2 Pp | 15,05 / 15,05 / 15,08 % | −17,0 bis −17,3 % | 54,9 / 28,4 / 19,3 | – |

- Kein Unterschied über 0,1 Pp. Grund: Positionen werden kurz gehalten (Median 11 Handelstage, nur 14 % länger als
  21 Tage, 1 % länger als 63 Tage), und 107 von 293 Umschichtungen sind bereits ein Tausch von Platz 1 und 2 (40/60 → 60/40),
  also ein Rebalancing. Die Gewichte driften deshalb kaum.
- **Ergebnis: kein zusätzliches Rebalancing.** Es kostet nur zusätzliche Orders.

## Nachtrag 29.10.2026: Gewichtung 1xGTAA, SMA 8/175, levGTAA-Parameter, Cash-Puffer

**1xGTAA 50/50 statt 40/60** (2009-07 bis 2026-10, SMA8/150, 1/3/6/12, Cooldown 10, nicht besetzter Platz verzinst mit BIL):

| Gewichtung | CAGR | MaxDD | Sharpe | Trades p. a. | Umschlag p. a. | 2009–14 | 2015–20 | 2021–26 |
|---|---|---|---|---|---|---|---|---|
| 40/60 (aktuell) | 15,1 % | −17,1 % | 1,12 | 16,9 | 13,7× | 12,9 % | 10,9 % | 21,8 % |
| 50/50 | 14,3 % | −16,3 % | 1,06 | 12,6 | 11,0× | 12,7 % | 9,8 % | 20,7 % |
| 60/40 | 15,3 % | −17,7 % | 1,08 | 16,9 | 10,7× | 13,0 % | 10,6 % | 22,8 % |

50/50 spart rund ein Viertel der Trades (Platztausch 1↔2 löst keinen Handel aus), ist aber in allen drei Teilzeiträumen,
in allen 16 SMA-Kombinationen (S 5–15, L 125–200; Sharpe 50/50 stets 0,04–0,07 niedriger) und auch bei 0,2 % Kosten
(13,1 % vs. 13,6 %) schwächer. **Entscheidung: 40/60 bleibt.**

**1xGTAA SMA8/175 statt 8/150** (feines Gitter S 5–15 × L 140–200): Plateau 14,4–15,5 % CAGR überall. 8/175: 15,3 % /
−19,2 % / Sharpe 1,13; 8/150: 15,1 % / −17,1 % / 1,12. Ab L 175 springt der MaxDD bei kurzer SMA (S ≤ 8) auf −19 bis −23 %,
unter L 150 sinkt die CAGR. Die Mitte zwischen beiden Kanten liegt bei L 150–160, nicht bei 175. Unterschiede in der CAGR
(±0,3 Pp) liegen weit unter dem Standardfehler (~3 Pp über 17 Jahre). **Entscheidung: 8/150 bleibt.**

**levGTAA Momentum-Ranglisten × SMA-Längen × kurze SMA** (72 Varianten, 2004–2026, Bot-Kern momentum_core, Vol-Target 55 %):
alle Varianten 39,7–43,8 % CAGR, MaxDD −39 bis −48 %, Sharpe 1,15–1,22. Aktuell (1/3/6/9 + 3/6/12, L 125–225, SMA30):
40,5 % / −44,5 % / 1,16. Nur 1/3/6/12 läge im Mittel bei 42,8 %, war aber 2004–2014 nicht besser (Sharpe 0,98 vs. 1,00);
die bessere Variante in-sample (1/3/6/9, L 100–200, SMA40: 33,1 % in-sample) lag out-of-sample (2015–2026) unter dem
Median (48,3 % vs. 53,3 %). Rangkorrelation in-sample/out-of-sample: **−0,55** – wer nach der Vergangenheit das Beste
auswählt, liegt danach eher schlechter. **Entscheidung: levGTAA bleibt unverändert** (breites Ensemble, kein Datamining).

**Cash-Puffer für wikifolio-Gebühren** (tägliche Produkt-Equity 12/2014–10/2026, Gebühren wie bei wikifolio aus dem Cash:
0,95 % p. a. täglich, 5 % auf jedes neue Hoch über der HWM). wikifolio-Regeln (Hilfecenter): negatives Cash muss bei
investierbaren wikifolios binnen 7 Tagen ausgeglichen werden, **während der Emission darf es nicht negativ werden**.
Anteil der Zeiträume, in denen das Cash vor dem nächsten Auffüllen unter 0 fällt / mittlerer Puffer:

| | Auffüllen | fest 0,5 % | fest 1 % | bisher (Monatsende q90) | neu q90 Monatshoch | neu q95 Monatshoch |
|---|---|---|---|---|---|---|
| levGTAA | monatliche Umschichtung | 17,6 % / 0,50 % | 6,3 % / 1,00 % | 9,2 % / 0,43 % | 8,5 % / 0,51 % | 7,0 % / 0,63 % |
| levTipsRegime | nur bei Signalwechsel | 16,9 % | 7,0 % | 21,1 % | 16,9 % | 15,5 % (bis −3,8 %) |
| levTipsRegime | Wechsel + monatlicher Cash-Check | 5,7 % | 0,5 % | 3,8 % | 2,4 % / 0,43 % | 1,4 % / 0,54 % |

Regel im Rechner: Puffer = 0,08 % Monatsgebühr + 5 % × (höchster Stand in 21 Handelstagen − nötiger Anstieg bis zur HWM)
+ 0,05 %, aufgerundet auf 0,05 %, höchstens 1 %. Höchster Stand = 95-%-Wert während der Emission, sonst 90-%-Wert
(levGTAA 26,7 % / 20,6 %, levTipsRegime 17,7 % / 14,3 %). Bei levTipsRegime (täglich mit Cooldown, Wechsel selten) ist der
monatliche Cash-Check nötig: ohne ihn läuft das Cash in 15–21 % der Zeiträume leer. Der Puffer kostet im Mittel
0,1–0,3 Pp Rendite im Jahr.

## Nachtrag 29.10.2026 (2): 1xGTAA täglich vs. monatlich (Kosten) und Overfitting-Test SMA8/150

**Kosten und Umschlag** (2009-07 bis 2026-10, SMA8/150, 1/3/6/12, 40/60; Umschlag = umgeschichteter Anteil pro Jahr):

| Variante | Trades p. a. | Umschlag p. a. | Kosten p. a. bei 0,1 % | CAGR brutto | 0,1 % | 0,2 % | 0,3 % | 0,5 % | MaxDD | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| täglich, Cooldown 10 (aktuell) | 16,9 | 13,7× | 1,37 % | 16,6 % | 15,1 % | 13,6 % | 12,2 % | 9,3 % | −17,1 % | 1,12 |
| täglich, Cooldown 5 | 24,2 | 19,4× | 1,94 % | 16,6 % | 14,5 % | 12,5 % | 10,5 % | 6,6 % | −15,3 % | 1,08 |
| täglich, Cooldown 15 | 13,0 | 10,8× | 1,08 % | 17,0 % | 15,8 % | 14,7 % | 13,5 % | 11,2 % | −13,0 % | 1,16 |
| monatlich (Monatsletzter) | 12,7 | 7,4× | 0,74 % | 14,2 % | 13,4 % | 12,7 % | 11,9 % | 10,3 % | −20,5 % | 0,99 |
| monatlich (1. Handelstag) | 12,5 | 7,2× | 0,72 % | 13,5 % | 12,7 % | 12,0 % | 11,2 % | 9,7 % | −25,7 % | 0,93 |

Täglich mit Cooldown kostet knapp doppelt so viel, bringt brutto aber 2,4 Pp mehr. Der Vorsprung hält bis etwa
0,35 % Kosten je umgeschichtetem Euro (ETF-Spreads im wikifolio typischerweise 0,05–0,2 %). Cooldown 15 läge vorn,
war aber 2021–2026 schwächer (17,4 % vs. 21,8 %); 10 bleibt als Mitte des Plateaus 5–15.

**Overfitting SMA8/150:**
- CSCV (Bailey/López de Prado): 56 SMA-Paare (S 1–30 × L 100–250), 16 Zeitblöcke, alle 12.870 Aufteilungen in
  8 in-sample / 8 out-of-sample. **PBO 28 %** (Anteil, in dem das in-sample beste Paar out-of-sample unter dem Median liegt;
  50 % hieße: Auswahl wertlos). Sharpe des in-sample Besten fällt von 1,16 auf 1,09 (normaler Auswahl-Abschlag).
- **SMA8/150 liegt out-of-sample in 96 % der Aufteilungen über dem Median** (Median-Perzentil 88 %); über alles Rang 6
  von 56 (Sharpe 1,12; bestes Paar 10/175 mit 1,14; Median 1,06).
- Walk-forward: jedes Jahr das in den 5 Vorjahren beste Paar nehmen (ohne Blick in die Zukunft) ergibt 2015–2026 CAGR
  15,8 % / Sharpe 1,21; fest 8/150 16,2 % / 1,24.
- Fazit: 8/150 ist kein Zufallstreffer auf einer Spitze, sondern liegt in einem breiten, stabilen Bereich; eine
  „optimierte“ Auswahl bringt nichts. **Bleibt.**

## Nachtrag 29.10.2026 (3): Aus welcher Position Cash holen?

Frage: Beim Auffüllen des Cash (Gebühren) die Position verkaufen, die gegenüber der **gehaltenen** Allokation oder gegenüber
dem **heute simulierten** Signal übergewichtet ist? Ziel: kein Verkauf, der beim nächsten Monatssignal zurückgekauft wird.

levGTAA, Bot-Kern, 267 Monatsentscheidungen 2004–2026; Abstand = Umschlag zwischen Allokation und tatsächlicher Entscheidung:

| Tage vor Monatssignal | Ø Abstand simuliert → Entscheidung | Ø Abstand gehalten → Entscheidung | stärkste Reduktion richtig vorhergesagt |
|---|---|---|---|
| 1 | 3,9 % | 16,3 % | 93 % |
| 3 | 6,6 % | 16,3 % | 90 % |
| 5 | 7,5 % | 16,3 % | 86 % |
| 10 | 11,3 % | 16,3 % | 78 % |
| 15 | 14,3 % | 16,3 % | 69 % |
| 20 | 16,1 % | 16,3 % | 61 % |

**Entscheidung (im Rechner, Ziel „Nur Cash auf Soll bringen“):** levGTAA in den letzten 10 Handelstagen vor dem
Monatssignal Referenz = heute simuliertes Signal, sonst gehaltene Allokation. levTipsRegime (täglich, Cooldown): gehaltene
Position, außer das Tagessignal weicht ab (Wechsel steht an). 1xGTAA (täglich, Cooldown 10, kein wikifolio): gleiche Regel
wie levTipsRegime. Verkauft wird die Position, die gegenüber der Referenz am stärksten übergewichtet ist.
