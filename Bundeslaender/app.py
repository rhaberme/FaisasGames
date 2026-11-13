"""Faisas Bundesländer-Dojo – Start: streamlit run Bundeslaender/app.py"""
import difflib
import json
import random
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageOps

from daten import DEUTSCHLAND, DEUTSCHLAND_FAKTEN, LAENDER, WISSEN

ORDNER = Path(__file__).parent
FORTSCHRITT = ORDNER / "fortschritt.json"
KARTEN_FOTO = ORDNER / "Bilder" / "IMG20261113214224.jpg"
GEOJSON = ORDNER / "geo" / "bundeslaender.geo.json"

GUERTEL = [  # (ab Punkten, Name, Farbe)
    (0, "Weißgurt", "#f5f5f5"),
    (10, "Gelbgurt", "#ffd93b"),
    (25, "Orangegurt", "#ff9f1c"),
    (45, "Grüngurt", "#2ec45a"),
    (70, "Blaugurt", "#3a86ff"),
    (100, "Braungurt", "#8d5524"),
    (140, "Schwarzgurt", "#111111"),
]
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
def laden():
    try:
        return json.loads(FORTSCHRITT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichern():
    try:
        FORTSCHRITT.write_text(
            json.dumps({"punkte": s.punkte, "rekord": s.rekord, "statistik": s.statistik}), encoding="utf-8"
        )
    except OSError:
        pass  # z. B. schreibgeschütztes Hosting – dann gilt der Fortschritt nur für diese Sitzung


if "punkte" not in s:
    alt = laden()
    s.punkte = alt.get("punkte", 0)
    s.rekord = alt.get("rekord", 0)
    s.statistik = alt.get("statistik", {})
    s.serie = 0


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
def karte():
    bild = ImageOps.exif_transpose(Image.open(KARTEN_FOTO))
    return bild.crop((330, 740, 1335, 1960))


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


def werte_aus(k, gewaehlt):
    frage = s[f"{k}_frage"]
    if frage.get("tippen"):
        aehnlich = difflib.SequenceMatcher(None, vereinfache(gewaehlt), vereinfache(frage["antwort"])).ratio()
        richtig = aehnlich >= 0.8
    else:
        richtig = gewaehlt == frage["antwort"]
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
    offen = s[f"{k}_gewaehlt"] is None

    richtig_n, gesamt_n = s.statistik.get(k, [0, 0])
    a, b, c = st.columns(3)
    a.metric("Treffer", f"{richtig_n} / {gesamt_n}")
    b.metric("Serie", f"{s.serie} " + "🔥" * min(s.serie // 3, 5))
    c.metric("Rekord-Serie", s.rekord)

    with st.container(border=True):
        st.markdown(f'<div class="thema">Runde {nr} · {frage["thema"]}</div>'
                    f'<div class="frage">{frage["frage"]}</div>', unsafe_allow_html=True)
        if frage.get("klick"):
            if offen:
                st.caption("👆 Tippe oder klicke direkt auf das Bundesland.")
                land = geklicktes_land(deutschlandkarte(dict.fromkeys(LAENDER, "#b06cff"), False), f"{k}_karte_{nr}")
                if land:
                    werte_aus(k, land)
                    st.rerun()
            else:
                farben = dict.fromkeys(LAENDER, "#4a3d5c")
                farben[s[f"{k}_gewaehlt"]] = "#ff3b3b"
                farben[frage["antwort"]] = "#2ec45a"
                st.plotly_chart(deutschlandkarte(farben, True), key=f"{k}_loesung_{nr}", config=KARTEN_CONFIG)
        elif frage.get("tippen"):
            with st.form(f"{k}_form_{nr}", border=False):
                eingabe = st.text_input("Deine Antwort", key=f"{k}_text_{nr}", disabled=not offen)
                if st.form_submit_button("Zuschlagen 🥊", type="primary", disabled=not offen) and eingabe.strip():
                    werte_aus(k, eingabe.strip())
                    st.rerun()
        else:
            spalten = st.columns(2)
            for i, option in enumerate(frage["optionen"]):
                marke = ""
                if not offen:
                    marke = "✅ " if option == frage["antwort"] else ("❌ " if option == s[f"{k}_gewaehlt"] else "")
                if spalten[i % 2].button(marke + option, key=f"{k}_opt_{nr}_{i}", width="stretch",
                                         disabled=not offen):
                    werte_aus(k, option)
                    st.rerun()

    if not offen:
        if s[f"{k}_richtig"]:
            zusatz = ""
            if frage.get("tippen") and vereinfache(s[f"{k}_gewaehlt"]) != vereinfache(frage["antwort"]):
                zusatz = f" Achte auf die Schreibweise: **{frage['antwort']}**"
            st.success(f"**{s[f'{k}_spruch']}**{zusatz}")
        else:
            geklickt = f"Du hast **{s[f'{k}_gewaehlt']}** erwischt (rot). " if frage.get("klick") else ""
            st.error(f"{s[f'{k}_spruch']}  \n{geklickt}Richtig ist: **{frage['antwort']}**")
        if s[f"{k}_aufstieg"]:
            st.balloons()
            st.info(f"🎉 Gürtelprüfung bestanden! Du trägst jetzt den **{guertel(s.punkte)[1][1]}**!")
        elif s[f"{k}_richtig"] and s.serie and s.serie % 5 == 0:
            st.info(f"🔥 {s.serie} richtige Antworten am Stück – Schärfe-Level steigt!")
        if st.button("Nächste Runde ➜", key=f"{k}_weiter_{nr}", type="primary", width="stretch"):
            naechste_frage(k, pool)
            st.rerun()


# ---------- Seiten ----------
def seite_start():
    st.title("🥊 Faisas Bundesländer-Dojo")
    st.markdown(guertel_html(s.punkte), unsafe_allow_html=True)
    stufe, _ = guertel(s.punkte)
    if stufe + 1 < len(GUERTEL):
        ziel, name, _ = GUERTEL[stufe + 1]
        start = GUERTEL[stufe][0]
        st.progress((s.punkte - start) / (ziel - start),
                    text=f"{s.punkte} Punkte – noch {ziel - s.punkte} bis zum {name}")
    else:
        st.success(f"{s.punkte} Punkte – du bist Schwarzgurt-Champion der Bundesländer! 🏆")

    st.markdown(
        """
        Hi Faisa! 👋 Hier trainierst du die **16 Bundesländer** und ihre **Landeshauptstädte** –
        und alles, was in deinem Heft steht. Jede richtige Antwort bringt einen Punkt für deinen
        nächsten Gürtel. Wähle links dein Training:

        - 📖 **Steckbriefe** – zum Aufwärmen alles nachlesen
        - 🥊 **Hauptstadt-Fight** – welche Hauptstadt gehört zu welchem Land?
        - ⌨️ **Profi-Runde** – Hauptstädte selbst eintippen
        - 🗺️ **Karten-Kampf** – klicke auf der Deutschlandkarte auf das richtige Bundesland
        - 🍜 **Wissens-Suppe** – scharfe Fragen aus deinem Heft

        Tipp: Fragen, die du falsch hattest, kommen nach ein paar Runden wieder. So bleiben sie im Kopf! 🎤
        """
    )
    with st.expander("Fortschritt zurücksetzen"):
        if st.button("Wieder beim Weißgurt anfangen"):
            s.clear()
            FORTSCHRITT.unlink(missing_ok=True)
            st.rerun()


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
        st.image(karte(), width=420, caption="Die Karte aus deinem Heft")
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
    "🏠 Start": seite_start,
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
    st.markdown(guertel_html(s.punkte), unsafe_allow_html=True)
    st.metric("Punkte", s.punkte)
    st.metric("Serie", f"{s.serie} " + "🔥" * min(s.serie // 3, 5))

SEITEN[seite]()
