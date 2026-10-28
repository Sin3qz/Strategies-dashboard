#!/usr/bin/env python3
"""Baut index.html (GitHub Pages) aus dashboard-data/page.html + dashboard-data/shell.html.

page.html ist dieselbe Seite wie im Claude-Dashboard (Markup, Styles, Skripte gegen die dash-Schnittstelle);
shell.html liefert Design-Tokens und eine kleine Laufzeit mit dieser Schnittstelle, die die Dateien aus data/ laedt.
Aufruf nach jeder Aenderung an page.html oder shell.html:  python3 dashboard-data/build_page.py
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
page = open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
shell = open(os.path.join(HERE, "shell.html"), encoding="utf-8").read()

page = page.replace('<meta name="dash-one-writer">', "")
scripts = re.findall(r"<script>.*?</script>", page, re.S)
markup = re.sub(r"<script>.*?</script>", "", page, flags=re.S).strip()
out = shell.replace("<!--PAGE-->", markup).replace("<!--SCRIPTS-->", "\n".join(scripts))
with open(os.path.join(os.path.dirname(HERE), "index.html"), "w", encoding="utf-8") as f:
    f.write(out)
print("index.html geschrieben:", len(out), "Zeichen")
