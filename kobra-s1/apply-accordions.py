# -*- coding: utf-8 -*-
"""
Range le manuel public index.html (one-shot, idempotent) :
  1. les 23 thèmes de modèles -> <details> (accordéons, 1er ouvert) + comptes
  2. les sous-parties du cours slicer -> <details> (index cliquable)
  3. réordonne les <section> dans un flux logique (basiques -> slicer groupé -> faire)
  4. nav réordonnée pour suivre + CSS accordéons + bouton tout déplier/replier
Rejouable : détecte si déjà appliqué (présence de details.theme) et ne double pas.
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from bs4 import BeautifulSoup

soup = BeautifulSoup(open("index.html", encoding="utf-8").read(), "html.parser")
main = soup.find("main")

if soup.find("details", class_="theme"):
    print("Déjà appliqué (details.theme présent) — rien à faire.")
    sys.exit(0)

# ---- 1. accordéons sur les thèmes de modèles (section#imprimer) ----------
sec_imp = soup.find("section", id="imprimer")
themes = sec_imp.find_all("h3")
for i, h3 in enumerate(themes):
    grid = h3.find_next_sibling()
    while grid is not None and not (grid.name == "div" and "grid" in (grid.get("class") or [])):
        grid = grid.find_next_sibling()
    if grid is None:
        continue
    n = len(grid.select(".model"))
    det = soup.new_tag("details", attrs={"class": "theme"})
    if i == 0:
        det["open"] = ""
    summ = soup.new_tag("summary")
    h3.insert_before(det)
    summ.append(h3.extract())
    cnt = soup.new_tag("span", attrs={"class": "th-count"})
    cnt.string = str(n)
    summ.append(cnt)
    det.append(summ)
    det.append(grid.extract())

# bouton tout déplier / replier juste après le lead de la section
lead = sec_imp.find("p", class_="lead")
ctrl = soup.new_tag("div", attrs={"class": "acc-controls"})
for label, val in [("Tout déplier", "open"), ("Tout replier", "close")]:
    b = soup.new_tag("button", attrs={"data-acc": val})
    b.string = label
    ctrl.append(b)
(lead or sec_imp).insert_after(ctrl) if lead else sec_imp.insert(0, ctrl)

# ---- 2. accordéons sur le cours slicer (section#slicer-cours) ------------
sec_cours = soup.find("section", id="slicer-cours")
if sec_cours:
    for h3 in sec_cours.find_all("h3"):
        det = soup.new_tag("details", attrs={"class": "course"})
        summ = soup.new_tag("summary")
        # collecter les frères jusqu'au prochain h3
        sibs = []
        sib = h3.find_next_sibling()
        while sib is not None and sib.name != "h3":
            nxt = sib.find_next_sibling()
            sibs.append(sib)
            sib = nxt
        h3.insert_before(det)
        summ.append(h3.extract())
        det.append(summ)
        for s in sibs:
            det.append(s.extract())

# ---- 3. réordonner les <section> -----------------------------------------
ORDER = ["machine", "acepro", "conseils", "filaments",
         "reglages-or", "slicer-map", "slicer", "slicer-cours",
         "maintenance", "pannes", "mods", "imprimer", "claude", "liens"]
secs = {s.get("id"): s for s in main.find_all("section", recursive=False)}
assert set(ORDER) == set(secs), f"ids divergents: {set(ORDER) ^ set(secs)}"
for sid in ORDER:
    main.append(secs[sid].extract())  # ré-append dans l'ordre voulu

# ---- 4. nav réordonnée pour suivre ---------------------------------------
nav = soup.find("nav")
links = {a.get("href"): a for a in nav.find_all("a")}
for sid in ORDER:
    a = links.get("#" + sid)
    if a:
        nav.append(a.extract())

# ---- CSS accordéons + bouton ---------------------------------------------
CSS = """
/* --- accordéons (rangement 2026-06-20) --- */
details.theme{border:1px solid var(--line);border-radius:14px;margin:12px 0;background:var(--card);overflow:hidden}
details.theme>summary{cursor:pointer;list-style:none;padding:14px 18px;display:flex;align-items:center;gap:12px}
details.theme>summary::-webkit-details-marker{display:none}
details.theme>summary::before{content:"\\25B8";color:var(--accent);transition:transform .15s ease;font-size:1.1em}
details.theme[open]>summary::before{transform:rotate(90deg)}
details.theme>summary h3{border:0;padding:0;margin:0;font-size:1.2rem}
details.theme .th-count{margin-left:auto;background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:3px 11px;font-size:.8rem;color:var(--muted);flex:0 0 auto}
details.theme>.grid{padding:4px 18px 18px}
details.course{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;margin:8px 0;background:var(--card)}
details.course>summary{cursor:pointer;list-style:none;padding:12px 16px}
details.course>summary::-webkit-details-marker{display:none}
details.course>summary::before{content:"\\25B8";color:var(--accent);margin-right:10px;display:inline-block;transition:transform .15s ease}
details.course[open]>summary::before{transform:rotate(90deg)}
details.course>summary h3{display:inline;border:0;margin:0;padding:0;font-size:1.08rem;color:var(--accent2)}
details.course>*:not(summary){margin-left:16px;margin-right:16px}
details.course>*:last-child{margin-bottom:14px}
.acc-controls{display:flex;gap:8px;margin:16px 0 4px}
.acc-controls button{background:var(--card2);border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:7px 14px;cursor:pointer;font-size:.85rem}
.acc-controls button:hover{border-color:var(--accent);color:var(--accent2)}
"""
style = soup.find("style")
style.append(CSS)

# ---- petit JS tout déplier / replier -------------------------------------
JS = ("document.querySelectorAll('.acc-controls [data-acc]').forEach(function(b){"
      "b.addEventListener('click',function(){var o=b.dataset.acc==='open';"
      "document.querySelectorAll('#imprimer details.theme').forEach(function(d){d.open=o;});});});")
script = soup.new_tag("script")
script.string = JS
soup.body.append(script)

open("index.html", "w", encoding="utf-8").write(str(soup))
nb_theme = len(soup.find_all("details", class_="theme"))
nb_course = len(soup.find_all("details", class_="course"))
print(f"OK : {nb_theme} accordéons thèmes + {nb_course} accordéons cours, sections réordonnées.")
print("ordre nav:", [a.get("href") for a in soup.find("nav").find_all("a")])
