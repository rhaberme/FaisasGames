"""Faisas Bundesländer-Dojo – Start: streamlit run Bundeslaender/app.py"""
import base64
import datetime
import difflib
import json
import random
import time
import zlib
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from daten import DEUTSCHLAND, DEUTSCHLAND_FAKTEN, GEGNER, LAENDER, ORTE, WISSEN

ORDNER = Path(__file__).parent
GEOJSON = ORDNER / "geo" / "bundeslaender.geo.json"
GEOJSON_KLEIN = ORDNER / "geo" / "bundeslaender_klein.geo.json"

GUERTEL = [  # (ab Punkten, Name, Farbe)
    (0, "Weißgurt", "#f5f5f5"),
    (15, "Gelbgurt", "#ffd93b"),
    (40, "Orangegurt", "#ff9f1c"),
    (75, "Grüngurt", "#2ec45a"),
    (120, "Blaugurt", "#3a86ff"),
    (180, "Braungurt", "#8d5524"),
    (250, "Schwarzgurt", "#111111"),
]
STERN_FARBEN = ["#4a3d5c", "#cd7f32", "#c9d1d9", "#ffd700"]  # 0 bis 3 Sterne
TAGESZIEL = 3
LOB = [
    "Volltreffer! 🥊", "Gnarly! 🎤", "K.O. in der ersten Runde! 💥", "Scharf wie Buldak! 🌶️",
    "Champion-Antwort! 🏆", "Sauberer Treffer! 🥋", "Das war ein Hit! 🎶", "Stark, Faisa! 💪",
]
TROST = [
    "Kurz abgeschüttelt – nächste Runde! 🥋", "Auch Champions kassieren mal einen Treffer. Weiter!",
    "Fast! Die Frage kommt nochmal – dann sitzt sie. 💪", "Einmal Suppe pusten und weiter. 🍜",
]

st.set_page_config(page_title="Faisas Bundesländer-Dojo", page_icon="🥊", layout="centered")
st.markdown(
    """
    <style>
    .stButton > button { border-radius: 16px; padding: 0.8rem 1rem; font-size: 1.1rem; font-weight: 700; }
    .frage { font-size: 1.6rem; font-weight: 800; line-height: 1.3; margin: 0.4rem 0 1rem 0; }
    .gurt { display: inline-block; padding: 0.35rem 1rem; border-radius: 999px; font-weight: 800;
            border: 2px solid #ffffff55; }
    /* Bundesland unter der Maus hervorheben */
    .js-plotly-plot .choroplethlayer path { transition: filter 0.12s; }
    .js-plotly-plot .choroplethlayer path.hervor { filter: brightness(1.4) saturate(1.2);
            stroke: #ffffff !important; stroke-width: 3px !important; stroke-opacity: 1 !important; }
    .js-plotly-plot.ueber-land .geo .bg rect { cursor: pointer; }
    .gegner { display: flex; gap: 0.9rem; align-items: center; font-size: 1.3rem; line-height: 1.2; }
    .gegner .kopf { font-size: 3.4rem; animation: wackeln 1.6s ease-in-out infinite; }
    @keyframes wackeln { 0%, 100% { transform: rotate(-6deg); } 50% { transform: rotate(6deg); } }
    .herzen { font-size: 2rem; text-align: right; letter-spacing: 0.1em; }
    .sterne { font-size: 3rem; text-align: center; letter-spacing: 0.2em; }
    .thema { opacity: 0.75; font-size: 0.95rem; letter-spacing: 0.04em; text-transform: uppercase; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Plotly kennt kein Hover-Styling für Flächen: Das Skript markiert das Bundesland unter der Maus per CSS-Klasse.
st.html(
    """
    <script>
    if (!window.faisaHover) {
        window.faisaHover = true;
        const markiere = (ereignis) => requestAnimationFrame(() => {
            const karte = ereignis.target.closest ? ereignis.target.closest(".js-plotly-plot") : null;
            const treffer = karte && karte._hoverdata && karte._hoverdata[0];
            const pfade = karte ? karte.querySelectorAll(".choroplethlayer path") : [];
            const ziel = treffer ? pfade[treffer.pointNumber] : null;
            document.querySelectorAll(".choroplethlayer path.hervor").forEach((p) => p !== ziel && p.classList.remove("hervor"));
            document.querySelectorAll(".js-plotly-plot.ueber-land").forEach((k) => k !== karte && k.classList.remove("ueber-land"));
            if (karte) karte.classList.toggle("ueber-land", Boolean(ziel));
            if (ziel) ziel.classList.add("hervor");
        });
        document.addEventListener("mousemove", markiere);
        document.addEventListener("mouseleave", markiere);
    }
    </script>
    """,
    unsafe_allow_javascript=True,
)

s = st.session_state


# ---------- Fortschritt ----------
# Der Spielstand steckt als Code in der Adresse (?s=…) und zusätzlich im Browser-Speicher.
# So hat jedes Gerät seinen eigenen Stand, auch auf Streamlit Cloud.
def kodiere(daten):
    return base64.urlsafe_b64encode(zlib.compress(json.dumps(daten, separators=(",", ":")).encode())).decode()


def dekodiere(code):
    try:
        daten = json.loads(zlib.decompress(base64.urlsafe_b64decode(code)))
        return daten if isinstance(daten, dict) else {}
    except Exception:  # kaputter oder fremder Code: einfach von vorn anfangen
        return {}


def stand():
    return {"punkte": s.punkte, "rekord": s.rekord, "statistik": s.statistik, "siege": s.siege,
            "tag": s.tag, "heute": s.heute, "tage": s.tage}


def speichern():
    st.query_params["s"] = kodiere(stand())


frisch = "punkte" not in s
if frisch:
    alt = dekodiere(st.query_params.get("s", ""))
    zahl = lambda name: alt[name] if isinstance(alt.get(name), int) else 0  # noqa: E731
    s.punkte, s.rekord, s.heute, s.tage = zahl("punkte"), zahl("rekord"), zahl("heute"), zahl("tage")
    s.statistik = {k: v for k, v in alt.get("statistik", {}).items()
                   if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v)} \
        if isinstance(alt.get("statistik"), dict) else {}
    s.siege = {land: n for land, n in alt.get("siege", {}).items() if land in LAENDER and n in (1, 2, 3)} \
        if isinstance(alt.get("siege"), dict) else {}
    s.tag = alt.get("tag") if isinstance(alt.get("tag"), str) else ""
    s.serie = 0
    s.kampf = None
    s.arena_nr = 0
    s.reihenfolge = random.sample(list(LAENDER), len(LAENDER))  # feste Gegner-Reihenfolge je Sitzung

if frisch and "s" not in st.query_params:
    # Neuer Besuch ohne Code in der Adresse: gemerkten Spielstand aus dem Browser holen (höchstens ein Versuch).
    st.html(
        """
        <script>
        try {
            const gemerkt = localStorage.getItem("faisaStand");
            if (gemerkt && !sessionStorage.getItem("faisaGeholt")) {
                sessionStorage.setItem("faisaGeholt", "1");
                const adresse = new URL(window.location.href);
                adresse.searchParams.set("s", gemerkt);
                window.location.replace(adresse);
            }
        } catch (fehler) {}
        </script>
        """,
        unsafe_allow_javascript=True,
    )
else:
    st.html(f'<script>try {{ localStorage.setItem("faisaStand", "{kodiere(stand())}"); }} catch (fehler) {{}}</script>',
            unsafe_allow_javascript=True)


def heute_iso():
    return datetime.date.today().isoformat()


def siege_heute():
    return s.heute if s.tag == heute_iso() else 0


def tage_in_folge():
    gestern = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    return s.tage if s.tag in (heute_iso(), gestern) else 0


def guertel(punkte):
    stufe = max(i for i, g in enumerate(GUERTEL) if punkte >= g[0])
    return stufe, GUERTEL[stufe]


def guertel_html(punkte):
    _, (_, name, farbe) = guertel(punkte)
    text = "#111" if farbe in ("#f5f5f5", "#ffd93b", "#ff9f1c", "#2ec45a") else "#fff"
    return f'<span class="gurt" style="background:{farbe};color:{text}">🥋 {name}</span>'


# ---------- Fragen ----------
def mische(richtig, falsch):
    optionen = [richtig, *falsch]
    random.shuffle(optionen)
    return optionen


def andere(werte, richtig, n=3):
    return random.sample([w for w in dict.fromkeys(werte) if w != richtig], n)


def fragen_hauptstadt():
    namen = list(LAENDER)
    staedte = [d["hauptstadt"] for d in LAENDER.values()]
    fragen = []
    for land, d in LAENDER.items():
        fragen.append({"thema": land, "frage": f"Wie heißt die Landeshauptstadt von {land}?",
                       "antwort": d["hauptstadt"], "falsch": andere(staedte, d["hauptstadt"])})
        fragen.append({"thema": d["hauptstadt"], "frage": f"{d['hauptstadt']} ist die Landeshauptstadt von …?",
                       "antwort": land, "falsch": andere(namen, land)})
    return fragen


def fragen_tippen():
    return [{"thema": land, "frage": f"Tippe die Landeshauptstadt von {land} ein:",
             "antwort": d["hauptstadt"], "tippen": True} for land, d in LAENDER.items()]


def fragen_karte():
    fragen = []
    for land, d in LAENDER.items():
        fragen.append({"thema": "Karte", "frage": f"Klicke auf der Karte auf {land}!", "antwort": land, "klick": True})
        if d["hauptstadt"] != land:
            fragen.append({"thema": "Karte", "antwort": land, "klick": True,
                           "frage": f"Klicke auf das Bundesland mit der Landeshauptstadt {d['hauptstadt']}!"})
    return fragen


def fragen_wissen():
    return [{"thema": t, "frage": f, "antwort": a, "falsch": list(x)} for t, f, a, x in WISSEN]


def vereinfache(text):
    text = text.lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return "".join(z for z in text if z.isalnum())


@st.cache_data
def geojson():
    return json.loads(GEOJSON.read_text(encoding="utf-8"))


BUNT = ["#ff2d78", "#ff9f1c", "#ffd93b", "#2ec45a", "#3a86ff", "#b06cff", "#19c8c8", "#ff7096"]
KARTEN_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}


def deutschlandkarte(farben, namen_zeigen):
    """farben: Bundesland -> Farbe. Ohne Namen beim Drüberfahren, wenn geraten werden soll."""
    laender = list(LAENDER)
    palette = list(dict.fromkeys(farben[land] for land in laender))
    n = len(palette)
    skala = [[i / max(n - 1, 1), f] for i, f in enumerate(palette)] if n > 1 else [[0, palette[0]], [1, palette[0]]]
    fig = go.Figure(go.Choropleth(
        geojson=geojson(), featureidkey="properties.name", locations=laender,
        z=[palette.index(farben[land]) for land in laender], zmin=0, zmax=max(n - 1, 1),
        colorscale=skala, showscale=False,
        marker_line_color="#17121f", marker_line_width=1.5,
        customdata=[LAENDER[land]["hauptstadt"] for land in laender],
        hovertemplate="<b>%{location}</b><br>Hauptstadt: %{customdata}<extra></extra>" if namen_zeigen else None,
        hoverinfo=None if namen_zeigen else "none",
        selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}},
    ))
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0), dragmode=False, clickmode="event+select",
                      paper_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(font_size=16))
    return fig


def geklicktes_land(fig, key):
    ereignis = st.plotly_chart(fig, key=key, on_select="rerun", selection_mode="points", config=KARTEN_CONFIG)
    punkte = ereignis.selection.points if ereignis else []
    return punkte[0].get("location") if punkte else None


# ---------- Quiz-Motor ----------
def naechste_frage(k, pool):
    """Falsch beantwortete Fragen kommen bald wieder, sonst wird ein gemischter Stapel abgearbeitet."""
    falsche = s.setdefault(f"{k}_falsch", [])
    stapel = s.setdefault(f"{k}_stapel", [])
    if falsche and s.get(f"{k}_seit_fehler", 0) >= 3:
        frage = falsche.pop(0)
        s[f"{k}_seit_fehler"] = 0
    else:
        if not stapel:
            stapel.extend(pool())
            random.shuffle(stapel)
        frage = stapel.pop()
        s[f"{k}_seit_fehler"] = s.get(f"{k}_seit_fehler", 0) + 1
    if "falsch" in frage:
        frage["optionen"] = mische(frage["antwort"], frage["falsch"])
    s[f"{k}_frage"] = frage
    s[f"{k}_gewaehlt"] = None
    s[f"{k}_nr"] = s.get(f"{k}_nr", 0) + 1


def ist_richtig(frage, gewaehlt):
    if frage.get("tippen"):
        return difflib.SequenceMatcher(None, vereinfache(gewaehlt), vereinfache(frage["antwort"])).ratio() >= 0.8
    return gewaehlt == frage["antwort"]


def frage_widget(key, frage, kopf, gewaehlt):
    """Zeigt eine Frage. Gibt die neue Antwort zurück, solange noch keine gewählt war (gewaehlt is None)."""
    offen = gewaehlt is None
    neu = None
    with st.container(border=True):
        st.markdown(f'<div class="thema">{kopf}</div><div class="frage">{frage["frage"]}</div>',
                    unsafe_allow_html=True)
        if frage.get("klick"):
            if offen:
                st.caption("👆 Tippe oder klicke direkt auf das Bundesland.")
                neu = geklicktes_land(deutschlandkarte(dict.fromkeys(LAENDER, "#b06cff"), False), f"{key}_karte")
            else:
                farben = dict.fromkeys(LAENDER, "#4a3d5c")
                if gewaehlt in farben:
                    farben[gewaehlt] = "#ff3b3b"
                farben[frage["antwort"]] = "#2ec45a"
                st.plotly_chart(deutschlandkarte(farben, True), key=f"{key}_loesung", config=KARTEN_CONFIG)
        elif frage.get("tippen"):
            with st.form(f"{key}_form", border=False):
                eingabe = st.text_input("Deine Antwort", key=f"{key}_text", disabled=not offen)
                if st.form_submit_button("Zuschlagen 🥊", type="primary", disabled=not offen) and eingabe.strip():
                    neu = eingabe.strip()
        else:
            spalten = st.columns(2)
            for i, option in enumerate(frage["optionen"]):
                marke = ""
                if not offen:
                    marke = "✅ " if option == frage["antwort"] else ("❌ " if option == gewaehlt else "")
                if spalten[i % 2].button(marke + option, key=f"{key}_opt_{i}", width="stretch", disabled=not offen):
                    neu = option
    return neu if offen else None


def fehler_text(frage, gewaehlt, spruch):
    geklickt = f"Du hast **{gewaehlt}** erwischt (rot). " if frage.get("klick") else ""
    return f"{spruch}  \n{geklickt}Richtig ist: **{frage['antwort']}**"


def werte_aus(k, gewaehlt):
    frage = s[f"{k}_frage"]
    richtig = ist_richtig(frage, gewaehlt)
    stufe_vorher, _ = guertel(s.punkte)
    stat = s.statistik.setdefault(k, [0, 0])
    stat[1] += 1
    if richtig:
        stat[0] += 1
        s.punkte += 1
        s.serie += 1
        s.rekord = max(s.rekord, s.serie)
    else:
        s.serie = 0
        s[f"{k}_falsch"].append(frage)
        s[f"{k}_seit_fehler"] = 0
    s[f"{k}_gewaehlt"] = gewaehlt
    s[f"{k}_richtig"] = richtig
    s[f"{k}_spruch"] = random.choice(LOB if richtig else TROST)
    s[f"{k}_aufstieg"] = guertel(s.punkte)[0] > stufe_vorher
    speichern()


def quiz(k, pool):
    if f"{k}_frage" not in s:
        naechste_frage(k, pool)
    frage = s[f"{k}_frage"]
    nr = s[f"{k}_nr"]
    gewaehlt = s[f"{k}_gewaehlt"]

    richtig_n, gesamt_n = s.statistik.get(k, [0, 0])
    a, b, c = st.columns(3)
    a.metric("Treffer", f"{richtig_n} / {gesamt_n}")
    b.metric("Serie", f"{s.serie} " + "🔥" * min(s.serie // 3, 5))
    c.metric("Rekord-Serie", s.rekord)

    neu = frage_widget(f"{k}_{nr}", frage, f"Runde {nr} · {frage['thema']}", gewaehlt)
    if neu:
        werte_aus(k, neu)
        st.rerun()

    if gewaehlt is not None:
        if s[f"{k}_richtig"]:
            zusatz = ""
            if frage.get("tippen") and vereinfache(gewaehlt) != vereinfache(frage["antwort"]):
                zusatz = f" Achte auf die Schreibweise: **{frage['antwort']}**"
            st.success(f"**{s[f'{k}_spruch']}**{zusatz}")
        else:
            st.error(fehler_text(frage, gewaehlt, s[f"{k}_spruch"]))
        if s[f"{k}_aufstieg"]:
            st.balloons()
            st.info(f"🎉 Gürtelprüfung bestanden! Du trägst jetzt den **{guertel(s.punkte)[1][1]}**!")
        elif s[f"{k}_richtig"] and s.serie and s.serie % 5 == 0:
            st.info(f"🔥 {s.serie} richtige Antworten am Stück – Schärfe-Level steigt!")
        if st.button("Nächste Runde ➜", key=f"{k}_weiter_{nr}", type="primary", width="stretch"):
            naechste_frage(k, pool)
            st.rerun()


# ---------- Arena: Kämpfe gegen die 16 Bundesländer ----------
def starte_kampf(land):
    eigene = [f for f in fragen_wissen() if f["thema"] == land]
    random.shuffle(eigene)
    haupt = [f for f in fragen_hauptstadt() if land in (f["thema"], f["antwort"])]
    rest = eigene[:4] + [
        haupt[1],
        {"thema": "Karte", "frage": f"Klicke auf der Karte auf {land}!", "antwort": land, "klick": True},
        next(f for f in fragen_tippen() if f["thema"] == land),
    ]
    random.shuffle(rest)
    fragen = [haupt[0], *rest]  # leichter Einstieg; 8 Fragen reichen immer für Sieg oder Niederlage
    for frage in fragen:
        if "falsch" in frage:
            frage["optionen"] = mische(frage["antwort"], frage["falsch"])
    s.arena_nr += 1
    s.kampf = {"land": land, "fragen": fragen, "i": 0, "hp": 100, "herzen": 3, "combo": 0, "gewaehlt": None,
               "status": "läuft", "gewinn": 0, "zeit": time.time(), "stufe": guertel(s.punkte)[0]}


def kampf_weiter():
    k = s.kampf
    k["i"] += 1
    k["gewaehlt"] = None
    k["zeit"] = time.time()
    if k["hp"] <= 0:
        sterne = k["herzen"]
        k["status"] = "gewonnen"
        k["erster_sieg"] = k["land"] not in s.siege
        k["bonus"] = 2 * sterne
        s.punkte += k["bonus"]
        s.siege[k["land"]] = max(s.siege.get(k["land"], 0), sterne)
        gestern = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        if s.tag == heute_iso():
            s.heute += 1
        else:
            s.tage = s.tage + 1 if s.tag == gestern else 1
            s.heute = 1
            s.tag = heute_iso()
    elif k["herzen"] <= 0 or k["i"] >= len(k["fragen"]):
        k["status"] = "verloren"
    speichern()


def kampf_antwort(gewaehlt):
    k = s.kampf
    frage = k["fragen"][k["i"]]
    stat = s.statistik.setdefault("kampf", [0, 0])
    stat[1] += 1
    if ist_richtig(frage, gewaehlt):
        stat[0] += 1
        k["combo"] += 1
        combo_schlag = k["combo"] >= 3
        blitz = not frage.get("tippen") and time.time() - k["zeit"] < 7
        plus = 1 + blitz
        k["hp"] = max(0, k["hp"] - (30 if combo_schlag else 20))
        k["gewinn"] += plus
        s.punkte += plus
        s.serie += 1
        s.rekord = max(s.rekord, s.serie)
        s.meldung = (f"{random.choice(LOB)}  +{plus} Punkt{'e' if plus > 1 else ''}"
                     + (" ⚡ Blitz-Bonus!" if blitz else "") + (" 🔥 Combo-Schlag!" if combo_schlag else ""))
        kampf_weiter()
    else:
        k["combo"] = 0
        k["herzen"] -= 1
        k["spruch"] = random.choice(TROST)
        k["gewaehlt"] = gewaehlt
        s.serie = 0
        speichern()


def naechster_gegner():
    """Erst alle Unbesiegten, danach die mit den wenigsten Sternen."""
    offen = [land for land in s.reihenfolge if land not in s.siege]
    if offen:
        return offen[0]
    schwach = [land for land in s.reihenfolge if s.siege[land] < 3]
    return min(schwach, key=lambda land: s.siege[land]) if schwach else None


def kampf_ansicht():
    k = s.kampf
    land = k["land"]
    emoji, name, spruch = GEGNER[land]
    if meldung := s.pop("meldung", None):
        st.toast(meldung)

    links, rechts = st.columns([3, 2])
    links.markdown(f'<div class="gegner"><span class="kopf">{emoji}</span><div><b>{name}</b><br>'
                   f'<span class="thema">{land}</span></div></div>', unsafe_allow_html=True)
    links.progress(k["hp"] / 100, text=f"Gegner-Energie: {k['hp']} %")
    rechts.markdown(f'<div class="herzen">{"❤️" * k["herzen"]}{"🖤" * (3 - k["herzen"])}</div>',
                    unsafe_allow_html=True)
    rechts.caption(f"🔥 Combo x{k['combo']} – Treffer zählen jetzt extra!" if k["combo"] >= 2
                   else "3 Treffer in Folge = Combo-Schlag")

    if k["status"] == "gewonnen":
        sterne = s.siege[land] if k["herzen"] < 1 else k["herzen"]
        if not k.get("gefeiert"):
            k["gefeiert"] = True
            st.balloons()
        st.markdown(f'<div class="sterne">{"⭐" * sterne}{"☆" * (3 - sterne)}</div>', unsafe_allow_html=True)
        st.success(f"**K.O.! Du hast {name} besiegt!** 🏆  \n+{k['gewinn'] + k['bonus']} Punkte "
                   f"({k['gewinn']} für Treffer, {k['bonus']} Sieg-Bonus)")
        if k.get("erster_sieg"):
            st.info(f"{emoji} **{name}** ist jetzt in deiner Trophäen-Sammlung – {len(s.siege)} von 16!")
        if guertel(s.punkte)[0] > k["stufe"]:
            st.info(f"🎉 Gürtelprüfung bestanden! Du trägst jetzt den **{guertel(s.punkte)[1][1]}**!")
        if siege_heute() == TAGESZIEL:
            st.info("🍜 Tagesziel geschafft! Drei Siege heute – Zeit für eine Buldak-Pause.")
        weiter = naechster_gegner()
        a, b = st.columns(2)
        if weiter and a.button(f"Nächster Gegner: {GEGNER[weiter][1]} ➜", key="sieg_weiter", type="primary", width="stretch"):
            starte_kampf(weiter)
            st.rerun()
        if sterne < 3 and b.button("Nochmal für 3 Sterne ⭐", width="stretch"):
            starte_kampf(land)
            st.rerun()
    elif k["status"] == "verloren":
        st.error(f"**{name} hat diese Runde gewonnen.** Aber du hast {k['gewinn']} Punkte mitgenommen – "
                 "und jetzt kennst du die Tricks!")
        if st.button("Revanche! 🥊", type="primary", width="stretch"):
            starte_kampf(land)
            st.rerun()
        with st.expander(f"🤫 Spickzettel: Steckbrief {land}"):
            steckbrief(land)
    else:
        frage = k["fragen"][k["i"]]
        if k["i"] == 0 and k["gewaehlt"] is None:
            st.caption(f"{name}: „{spruch}“")
        neu = frage_widget(f"kampf_{s.arena_nr}_{k['i']}", frage, f"Schlag {k['i'] + 1} · {frage['thema']}",
                           k["gewaehlt"])
        if neu:
            kampf_antwort(neu)
            st.rerun()
        if k["gewaehlt"] is not None:
            st.error(fehler_text(frage, k["gewaehlt"], k["spruch"]))
            if st.button("Weiterkämpfen ➜", type="primary", width="stretch"):
                kampf_weiter()
                st.rerun()

    if st.button("↩ Zurück zur Arena" if k["status"] != "läuft" else "Aufgeben und zurück zur Arena"):
        s.kampf = None
        st.rerun()


def seite_arena():
    if s.kampf:
        kampf_ansicht()
        return
    st.title("🥊 Faisas Bundesländer-Dojo")
    st.markdown(guertel_html(s.punkte), unsafe_allow_html=True)
    stufe, _ = guertel(s.punkte)
    if stufe + 1 < len(GUERTEL):
        ziel, name, _ = GUERTEL[stufe + 1]
        start = GUERTEL[stufe][0]
        st.progress((s.punkte - start) / (ziel - start),
                    text=f"{s.punkte} Punkte – noch {ziel - s.punkte} bis zum {name}")
    else:
        st.success(f"{s.punkte} Punkte – Schwarzgurt! 🏆")

    sterne = sum(s.siege.values())
    a, b, c = st.columns(3)
    a.metric("Besiegte Gegner", f"{len(s.siege)} / 16")
    b.metric("Sterne", f"{sterne} / 48 ⭐")
    c.metric("Tage in Folge", f"{tage_in_folge()} 🔥")
    heute = siege_heute()
    st.progress(min(heute, TAGESZIEL) / TAGESZIEL,
                text=f"Tagesziel: {min(heute, TAGESZIEL)} von {TAGESZIEL} Siegen heute"
                     + (" – geschafft! 🍜" if heute >= TAGESZIEL else ""))

    if sterne == 48:
        st.success("👑 **Legende!** Alle 16 Gegner mit drei Sternen besiegt. Mehr geht nicht!")
    elif len(s.siege) == 16:
        st.success("🏆 **Deutsche Meisterin!** Alle 16 Gegner besiegt. Schaffst du überall drei Sterne?")
    else:
        st.markdown("Besiege die Gegner aus allen **16 Bundesländern**! Jeder Treffer nimmt dem Gegner Energie, "
                    "bei einem Fehler verlierst du ein ❤️. Wer schnell antwortet, bekommt den ⚡ Blitz-Bonus.")

    weiter = naechster_gegner()
    if weiter and st.button(f"▶️ Nächster Kampf: {GEGNER[weiter][1]} ({weiter})", key="arena_weiter", type="primary", width="stretch"):
        starte_kampf(weiter)
        st.rerun()

    st.caption("Oder such dir deinen Gegner selbst aus – auf der Karte oder in der Trophäen-Sammlung. "
               "Grau = noch unbesiegt, Bronze/Silber/Gold = 1/2/3 Sterne.")
    farben = {land: STERN_FARBEN[s.siege.get(land, 0)] for land in LAENDER}
    land = geklicktes_land(deutschlandkarte(farben, True), f"arena_karte_{s.arena_nr}")
    if land:
        starte_kampf(land)
        st.rerun()

    st.subheader("🏆 Trophäen-Sammlung")
    spalten = st.columns(4)
    for i, land in enumerate(sorted(LAENDER)):
        n = s.siege.get(land, 0)
        text = f"{GEGNER[land][0]} {land} {'⭐' * n}" if n else f"❓ {land}"
        if spalten[i % 4].button(text, key=f"trophaee_{land}", width="stretch"):
            starte_kampf(land)
            st.rerun()

    st.caption("Zum Üben ohne Gegner: links findest du die Steckbriefe und die Trainings-Runden.")
    with st.expander("Fortschritt zurücksetzen"):
        if st.button("Wieder beim Weißgurt anfangen"):
            s.clear()
            st.query_params["s"] = kodiere({})
            st.rerun()


# ---------- Seiten ----------
@st.cache_data
def abenteuer_daten():
    """Alles, was das Spiel im Browser braucht: Umrisse, Hauptstädte, Gegner und Fragen."""
    umrisse = {}
    for merkmal in json.loads(GEOJSON_KLEIN.read_text(encoding="utf-8"))["features"]:
        geo = merkmal["geometry"]
        polygone = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        umrisse[merkmal["properties"]["name"]] = [[[round(x, 3), round(y, 3)] for x, y in p[0]] for p in polygone]
    frage = lambda f, a, x: {"q": f, "a": a, "f": list(x)}  # noqa: E731
    daten = {
        "laender": {land: {"hauptstadt": d["hauptstadt"], "ort": ORTE[land], "gegner": GEGNER[land],
                           "fragen": [frage(f, a, x) for t, f, a, x in WISSEN if t == land]}
                    for land, d in LAENDER.items()},
        "deutschland": [frage(f, a, x) for t, f, a, x in WISSEN if t == "Deutschland"],
        "geo": umrisse,
    }
    return json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")


def seite_abenteuer():
    skript = (ORDNER / "abenteuer.js").read_text(encoding="utf-8")
    st.html(f'<div id="faisa-abenteuer"></div><script>window.FAISA_DATEN = {abenteuer_daten()};</script>'
            f"<script>{skript}</script>", unsafe_allow_javascript=True)
    st.caption("Laufen: Pfeiltasten oder WASD – oder dorthin tippen, wo du hinwillst. "
               "Antworten: anklicken oder die Tasten 1–4. Der Spielstand wird in diesem Browser gespeichert.")


def steckbrief(land):
    d = LAENDER[land]
    st.subheader(f"{land} (Nr. {d['nr']} im Heft)")
    a, b, c = st.columns(3)
    a.metric("Landeshauptstadt", d["hauptstadt"])
    b.metric("Größe", d["groesse"])
    c.metric("Einwohner", d["einwohner"])
    st.markdown("\n".join(f"- {f}" for f in d["fakten"]))


def seite_steckbriefe():
    st.title("📖 Steckbriefe")
    tab_karte, tab_land, tab_alle, tab_de = st.tabs(
        ["🗺️ Karte erkunden", "Ein Bundesland", "Alle Hauptstädte", "Deutschland"])
    with tab_karte:
        st.caption("👆 Klicke auf ein Bundesland, dann erscheint sein Steckbrief.")
        farben = {land: BUNT[i % len(BUNT)] for i, land in enumerate(LAENDER)}
        land = geklicktes_land(deutschlandkarte(farben, True), "erkunden_karte")
        if land:
            steckbrief(land)
    with tab_land:
        steckbrief(st.selectbox("Bundesland auswählen", list(LAENDER)))
    with tab_alle:
        verdeckt = st.toggle("Hauptstädte verdecken (zum Selbsttest)")
        st.table([{"Nr.": d["nr"], "Bundesland": land, "Landeshauptstadt": "❓" if verdeckt else d["hauptstadt"]}
                  for land, d in sorted(LAENDER.items(), key=lambda x: x[1]["nr"])])
        farben = {land: BUNT[i % len(BUNT)] for i, land in enumerate(LAENDER)}
        st.plotly_chart(deutschlandkarte(farben, not verdeckt), key="tabelle_karte", config=KARTEN_CONFIG)
    with tab_de:
        st.subheader("Steckbrief Deutschland")
        st.table([{"Was": k, "Antwort": v} for k, v in DEUTSCHLAND.items()])
        st.markdown("\n".join(f"- {f}" for f in DEUTSCHLAND_FAKTEN))


def seite_wissen():
    st.title("🍜 Wissens-Suppe")
    themen = ["Alle Themen", *dict.fromkeys(t for t, *_ in WISSEN)]
    thema = st.selectbox("Thema", themen)
    if s.get("wissen_thema") != thema:  # Themenwechsel: neuer Stapel
        for name in ("wissen_frage", "wissen_stapel", "wissen_falsch"):
            s.pop(name, None)
        s.wissen_thema = thema
    quiz("wissen", lambda: [f for f in fragen_wissen() if thema in ("Alle Themen", f["thema"])])


SEITEN = {
    "🗺️ Abenteuer": seite_abenteuer,
    "🏟️ Arena": seite_arena,
    "📖 Steckbriefe": seite_steckbriefe,
    "🥊 Hauptstadt-Fight": lambda: (st.title("🥊 Hauptstadt-Fight"), quiz("hauptstadt", fragen_hauptstadt)),
    "⌨️ Profi-Runde": lambda: (st.title("⌨️ Profi-Runde"), quiz("tippen", fragen_tippen)),
    "🗺️ Karten-Kampf": lambda: (st.title("🗺️ Karten-Kampf"), quiz("karte", fragen_karte)),
    "🍜 Wissens-Suppe": seite_wissen,
}

with st.sidebar:
    st.markdown("## 🥋 Faisas Dojo")
    seite = st.radio("Training", list(SEITEN), label_visibility="collapsed")
    st.divider()
    if seite == "🗺️ Abenteuer":  # das Abenteuer zeigt seinen eigenen Stand im Spiel an
        st.caption("Im Abenteuer sammelst du XP direkt im Spiel. Arena und Training haben ihren eigenen Punktestand.")
    else:
        st.markdown(guertel_html(s.punkte), unsafe_allow_html=True)
        st.metric("Punkte", s.punkte)
        st.metric("Sterne", f"{sum(s.siege.values())} / 48 ⭐")
        st.metric("Serie", f"{s.serie} " + "🔥" * min(s.serie // 3, 5))

SEITEN[seite]()
