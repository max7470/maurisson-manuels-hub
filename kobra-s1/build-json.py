# -*- coding: utf-8 -*-
"""
Génère kobra-s1.json (machine-readable) DEPUIS index.html (le manuel public).

But : le skill maurisson-3d (et toute IA) consulte 1 JSON propre au lieu de
scraper 514 Ko de HTML. Rejouable : édite index.html puis relance ce script.

    python build-json.py

Sortie : kobra-s1.json à côté du HTML (servi sur manuels.maurisson.com/kobra-s1/).
"""
import json, os, re, sys
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "index.html")
OUT  = os.path.join(HERE, "kobra-s1.json")

soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")


def clean(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def slug(s):
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[\s_-]+", "-", s).strip("-")


def parse_table(tb):
    rows = tb.find_all("tr")
    headers = [clean(th) for th in rows[0].find_all(["th", "td"])]
    out = []
    for tr in rows[1:]:
        cells = [clean(td) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if len(headers) == len(cells):
            out.append(dict(zip(headers, cells)))
        else:
            out.append(cells)
    return {"headers": headers, "rows": out}


def kind_of(node):
    cls = node.get("class") or []
    for k in ("red", "green", "yellow", "blue"):
        if k in cls:
            return k
    return "note"


# ---------------------------------------------------------------- models
MODELS_H2 = "Trucs cool à imprimer"
models_section = None
for h2 in soup.find_all("h2"):
    if MODELS_H2 in clean(h2):
        models_section = h2
        break

themes = []
model_card_ids = set()
if models_section:
    # tous les .model jusqu'au prochain h2, groupés par h3 précédent
    cur_theme = None
    for el in models_section.find_all_next():
        if el.name == "h2":
            break
        if el.name == "h3":
            cur_theme = {"theme": clean(el), "items": []}
            themes.append(cur_theme)
        elif el.name == "div" and "model" in (el.get("class") or []):
            model_card_ids.add(id(el))
            for d in el.descendants:
                model_card_ids.add(id(d))
            h4 = el.find("h4")
            link = (h4.find("a") if h4 else None) or el.find("a")
            url = link.get("href") if link else None
            name = clean(h4) if h4 else (clean(link) if link else "")
            p = el.find("p")
            img = el.find("img", class_="thumb")
            pills = el.select(".meta .pill")
            multi = any("multi" in (pl.get("class") or []) for pl in pills)
            meta = [clean(pl) for pl in pills if "multi" not in (pl.get("class") or [])]
            item = {"name": name, "url": url, "desc": clean(p) if p else ""}
            if meta:
                item["meta"] = " · ".join(meta)
            if multi:
                item["multi"] = True
            if img and img.get("src"):
                item["thumb"] = img["src"]
            (cur_theme or themes.append({"theme": "?", "items": []}) or themes[-1])
            cur_theme["items"].append(item)

model_count = sum(len(t["items"]) for t in themes)


# ------------------------------------------------- generic section walk
def emit_blocks(start_h2):
    """Blocs structurés d'une section h2 -> intro + subsections (par h3)."""
    consumed = set()
    intro = []
    subs = []
    cur = intro  # liste de blocs courante (intro puis chaque subsection)

    def push_container_descendants(node):
        for d in node.descendants:
            consumed.add(id(d))

    for el in start_h2.find_all_next():
        if el.name == "h2":
            break
        if id(el) in model_card_ids or id(el) in consumed:
            continue
        if el.name == "h3":
            sub = {"title": clean(el), "blocks": []}
            subs.append(sub)
            cur = sub["blocks"]
            continue
        if el.name == "table":
            cur.append({"type": "table", **parse_table(el)})
            push_container_descendants(el)
        elif el.name == "div" and "callout" in (el.get("class") or []):
            cur.append({"type": "callout", "kind": kind_of(el), "text": clean(el)})
            push_container_descendants(el)
        elif el.name == "div" and "card" in (el.get("class") or []):
            h4 = el.find(["h4", "h3"])
            ps = [clean(p) for p in el.find_all("p") if clean(p)]
            bullets = [clean(li) for li in el.find_all("li")]
            blk = {"type": "card", "title": clean(h4) if h4 else ""}
            if ps:
                blk["text"] = " ".join(ps)
            if bullets:
                blk["bullets"] = bullets
            if not ps and not bullets:  # carte sans structure interne -> texte brut
                blk["text"] = clean(el)
            cur.append(blk)
            push_container_descendants(el)
        elif el.name in ("ul", "ol"):
            cur.append({"type": "list", "items": [clean(li) for li in el.find_all("li", recursive=False)] or [clean(li) for li in el.find_all("li")]})
            push_container_descendants(el)
        elif el.name == "p":
            t = clean(el)
            if t:
                cur.append({"type": "p", "text": t})
        elif el.name == "h4":
            cur.append({"type": "h4", "text": clean(el)})
    return intro, subs


sections = []
links = []
for h2 in soup.find_all("h2"):
    title = clean(h2)
    sid = slug(re.sub(r"^[^\w]+", "", title))
    if MODELS_H2 in title:
        sections.append({
            "id": "modeles", "title": title,
            "note": f"{model_count} modèles — voir la clé top-level 'models'.",
        })
        continue
    intro, subs = emit_blocks(h2)
    sec = {"id": sid, "title": title}
    if intro:
        sec["intro"] = intro
    if subs:
        sec["subsections"] = subs
    sections.append(sec)
    # collecte des liens de la section "Liens à garder"
    if "Liens" in title:
        for a in h2.find_all_next("a"):
            if a.find_parent("nav") or a.find_parent("footer"):
                continue
            href = a.get("href")
            if href and href.startswith("http"):
                links.append({"label": clean(a), "url": href})


# ------------------------------------------------------- quick indexes
hero = soup.find("header", class_="hero")
badges = [clean(b) for b in hero.find_all(class_="badge")] if hero else []

tables = soup.find_all("table")
specs = {}
for tb in tables:
    hs = [clean(th) for th in tb.find_all("th")]
    if hs[:2] == ["Caractéristique", "Valeur"]:
        for tr in tb.find_all("tr")[1:]:
            c = [clean(td) for td in tr.find_all(["td", "th"])]
            if len(c) == 2:
                specs[c[0]] = c[1]
        break

quick_facts = {
    "type": "Imprimante FDM CoreXY caisson fermé 250³ mm + module multicouleur ACE Pro (4 bobines, séchage actif)",
    "build_volume": specs.get("Volume d'impression"),
    "nozzle": specs.get("Buse"),
    "plate": specs.get("Plateau"),
    "speed": specs.get("Vitesse"),
    "materials": specs.get("Matériaux"),
    "wifi": "2,4 GHz uniquement",
    "slicer": specs.get("Slicer"),
    "camera": specs.get("Caméra"),
}
quick_facts = {k: v for k, v in quick_facts.items() if v}

# règles d'or = callouts rouges (= les avertissements critiques du manuel)
golden_rules = []
seen = set()
for co in soup.find_all("div", class_="callout"):
    if "red" in (co.get("class") or []):
        t = clean(co)
        if t and t not in seen:
            seen.add(t)
            golden_rules.append(t)

# table réglages par filament (Paramètre × matériaux)
slicer_by_filament = None
for tb in tables:
    hs = [clean(th) for th in tb.find_all("th")]
    if hs[:1] == ["Paramètre"]:
        slicer_by_filament = parse_table(tb)
        break

# table récap filaments
filaments_recap = None
for tb in tables:
    hs = [clean(th) for th in tb.find_all("th")]
    if hs[:1] == ["Matériau"] and "Prix €/kg" in hs:
        filaments_recap = parse_table(tb)
        break

canonical = (soup.find("link", rel="canonical") or {})
source_url = canonical.get("href") if canonical else "https://manuels.maurisson.com/kobra-s1/"

doc = {
    "_meta": {
        "title": "Le Dossier Anycubic Kobra S1 Combo + ACE Pro — JSON machine-readable",
        "role": "Bible imprimante requêtable par IA, générée depuis le manuel public HTML.",
        "owner": "Maxime (Maurisson)",
        "machine": "Anycubic Kobra S1 Combo + ACE Pro",
        "source_url": source_url,
        "generated_from": "index.html",
        "generator": "build-json.py",
        "lang": "fr",
        "schema_version": 1,
        "how_to_use": (
            "JSON miroir du manuel public. 'quick_facts' + 'golden_rules' + 'machine_specs' "
            "suffisent aux questions de base. 'slicer_by_filament' et 'filaments_recap' = tables "
            "clés. 'sections' = tout le manuel structuré dans l'ordre (intro + subsections : "
            "blocs typés p/list/table/callout/card). 'models' = catalogue par thème."
        ),
    },
    "quick_facts": quick_facts,
    "badges": badges,
    "machine_specs": specs,
    "golden_rules": golden_rules,
    "slicer_by_filament": slicer_by_filament,
    "filaments_recap": filaments_recap,
    "models": {"count": model_count, "themes_count": len(themes), "themes": themes},
    "sections": sections,
    "links": links,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)

size = os.path.getsize(OUT)
print(f"OK -> {OUT}")
print(f"  {size/1024:.0f} Ko | {model_count} modèles / {len(themes)} thèmes | "
      f"{len(sections)} sections | {len(golden_rules)} règles d'or | {len(links)} liens")
