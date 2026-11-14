// Faisas Deutschland-Abenteuer: läuft komplett im Browser, die Daten kommen aus app.py (window.FAISA_DATEN).
(function warte(versuch) {
  // Das Skript kann laufen, bevor Streamlit den Spiel-Rahmen eingefügt hat: kurz darauf warten.
  const wurzel = document.getElementById("faisa-abenteuer");
  if (wurzel && window.FAISA_DATEN) starteAbenteuer(wurzel, window.FAISA_DATEN);
  else if (versuch < 200) setTimeout(() => warte(versuch + 1), 50);
})(0);

function starteAbenteuer(wurzel, D) {
  "use strict";
  if (window.faisaSpiel) window.faisaSpiel.stopp();

  // ---------- Welt ----------
  const PX_LON = 330, PX_LAT = 523, LON0 = 5.3, LAT0 = 55.2;
  const W = Math.round((15.4 - LON0) * PX_LON), H = Math.round((LAT0 - 47.0) * PX_LAT);
  const wx = (lon) => (lon - LON0) * PX_LON, wy = (lat) => (LAT0 - lat) * PX_LAT;
  const NAMEN = Object.keys(D.laender);
  const TEMPO = 290, ROLLEN_NOETIG = 3;
  const GUERTEL = [[0, "Weißgurt", "#f5f5f5"], [60, "Gelbgurt", "#ffd93b"], [150, "Orangegurt", "#ff9f1c"],
    [280, "Grüngurt", "#2ec45a"], [450, "Blaugurt", "#3a86ff"], [650, "Braungurt", "#8d5524"], [900, "Schwarzgurt", "#111111"]];
  const NACHBARN = [["Dänemark", 9.2, 55.08], ["Polen", 15.05, 52.6], ["Tschechien", 13.9, 50.25], ["Österreich", 12.3, 47.2],
    ["Schweiz", 8.3, 47.3], ["Frankreich", 6.5, 48.5], ["Luxemburg", 5.95, 49.75], ["Belgien", 5.8, 50.5], ["Niederlande", 6.1, 52.4]];
  const LABEL_VERSATZ = { Brandenburg: [60, 190], Niedersachsen: [90, 60] };
  const LOB = ["Volltreffer! 🥊", "Gnarly! 🎤", "Scharf wie Buldak! 🌶️", "Sauberer Treffer! 🥋", "Stark, Faisa! 💪", "Das war ein Hit! 🎶"];

  const klemme = (v, a, b) => Math.max(a, Math.min(b, v));
  const misch = (liste) => { for (let i = liste.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [liste[i], liste[j]] = [liste[j], liste[i]]; } return liste; };
  const wahl = (liste, n) => misch(liste.slice()).slice(0, n);
  function zufallsquelle(saat) { // fester Zufall, damit alles bei jedem Besuch am selben Ort liegt
    return () => { saat |= 0; saat = (saat + 0x6d2b79f5) | 0; let t = Math.imul(saat ^ (saat >>> 15), 1 | saat);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function imRing(ring, x, y) {
    let drin = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) drin = !drin;
    }
    return drin;
  }

  const laender = {};
  NAMEN.forEach((name, i) => {
    const d = D.laender[name];
    const ringe = D.geo[name].map((r) => r.map(([lon, lat]) => [wx(lon), wy(lat)]));
    const pfad = new Path2D();
    const boxen = ringe.map((r) => {
      let a = 1e9, b = 1e9, c = -1e9, e = -1e9;
      r.forEach(([x, y], j) => { if (j) pfad.lineTo(x, y); else pfad.moveTo(x, y); a = Math.min(a, x); b = Math.min(b, y); c = Math.max(c, x); e = Math.max(e, y); });
      pfad.closePath();
      return [a, b, c, e];
    });
    const flaeche = (b) => (b[2] - b[0]) * (b[3] - b[1]);
    let haupt = 0;
    boxen.forEach((b, j) => { if (flaeche(b) > flaeche(boxen[haupt])) haupt = j; });
    const mitte = ringe[haupt].reduce((s, p) => [s[0] + p[0], s[1] + p[1]], [0, 0]).map((v) => v / ringe[haupt].length);
    const versatz = LABEL_VERSATZ[name] || [0, 0];
    laender[name] = { name, d, ringe, pfad, boxen, haupt, groesse: flaeche(boxen[haupt]), ton: (i * 137.5) % 360,
      bx: wx(d.ort[0]), by: wy(d.ort[1]), lx: mitte[0] + versatz[0], ly: mitte[1] + versatz[1] };
  });
  const nachGroesse = NAMEN.slice().sort((a, b) => laender[a].groesse - laender[b].groesse); // kleine zuerst (Berlin liegt in Brandenburg)
  function landBei(x, y) {
    for (const name of nachGroesse) {
      const L = laender[name];
      for (let j = 0; j < L.ringe.length; j++) {
        const b = L.boxen[j];
        if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3] && imRing(L.ringe[j], x, y)) return name;
      }
    }
    return null;
  }

  // Begehbare Fläche als grobe Maske (1/4 Auflösung); die dicke Linie schließt kleine Lücken an den Grenzen.
  const MASKE = 4, mb = Math.ceil(W / MASKE), mh = Math.ceil(H / MASKE);
  const maskenBild = (() => {
    const c = document.createElement("canvas"); c.width = mb; c.height = mh;
    const g = c.getContext("2d"); g.scale(1 / MASKE, 1 / MASKE); g.fillStyle = g.strokeStyle = "#fff"; g.lineWidth = 10;
    NAMEN.forEach((n) => { g.fill(laender[n].pfad); g.stroke(laender[n].pfad); });
    return g.getImageData(0, 0, mb, mh).data;
  })();
  const begehbar = (x, y) => x >= 0 && y >= 0 && x < W && y < H && maskenBild[((Math.floor(y / MASKE) * mb + Math.floor(x / MASKE)) << 2) + 3] > 120;
  const freierPlatz = (x, y, r) => begehbar(x - r, y) && begehbar(x + r, y) && begehbar(x, y - r) && begehbar(x, y + r);

  // ---------- Dinge in der Welt ----------
  const rollen = [], bosse = [], mikros = [], suppen = [];
  NAMEN.forEach((name, i) => {
    const L = laender[name], zufall = zufallsquelle(1000 + i * 77), eigene = [{ x: L.bx, y: L.by }];
    const abstand = klemme(Math.sqrt(L.groesse) / 5, 44, 150);
    const [a, b, c, e] = L.boxen[L.haupt];
    const platz = () => {
      for (let v = 0; v < 900; v++) {
        const x = a + zufall() * (c - a), y = b + zufall() * (e - b), m = v < 500 ? abstand : abstand / 2;
        if (landBei(x, y) === name && freierPlatz(x, y, 16) && eigene.every((o) => Math.hypot(o.x - x, o.y - y) >= m)) { eigene.push({ x, y }); return { x, y }; }
      }
      return { x: L.bx + 40, y: L.by + 40 };
    };
    bosse.push({ land: name, x: L.bx, y: L.by });
    const anzahl = L.groesse < 60000 ? 3 : 4;
    for (let k = 0; k < anzahl; k++) rollen.push({ id: name + "#" + k, land: name, nr: k, versuch: 0, ...platz() });
    mikros.push({ land: name, nr: i, ...platz() });
  });
  (() => {
    const zufall = zufallsquelle(4242);
    while (suppen.length < 16) {
      const x = zufall() * W, y = zufall() * H;
      if (landBei(x, y) && freierPlatz(x, y, 16) && [...rollen, ...bosse, ...mikros, ...suppen].every((o) => Math.hypot(o.x - x, o.y - y) > 60)) suppen.push({ id: suppen.length, x, y, wegBis: 0 });
    }
  })();

  // ---------- Spielstand ----------
  const SPEICHER = "faisaAbenteuer1";
  const START = { x: wx(9.45), y: wy(51.25) };
  let z = { x: START.x, y: START.y, xp: 0, herzen: 3, rollen: {}, siege: {}, mikros: {}, besucht: {}, tag: "", tage: 0, ton: true, neu: true };
  try { const alt = JSON.parse(localStorage.getItem(SPEICHER) || "null"); if (alt && typeof alt === "object") z = { ...z, ...alt }; } catch (fehler) { /* neu anfangen */ }
  for (const feld of ["rollen", "siege", "mikros", "besucht"]) if (!z[feld] || typeof z[feld] !== "object") z[feld] = {};
  if (!begehbar(z.x, z.y)) { z.x = START.x; z.y = START.y; }
  const speichern = () => { try { localStorage.setItem(SPEICHER, JSON.stringify(z)); } catch (fehler) { /* privater Modus */ } };
  const anzahlSiege = () => Object.keys(z.siege).length;
  const maxHerzen = () => 3 + (anzahlSiege() >= 5) + (anzahlSiege() >= 10);
  const guertel = () => { let g = GUERTEL[0]; for (const stufe of GUERTEL) if (z.xp >= stufe[0]) g = stufe; return g; };
  const rollenIn = (land) => rollen.filter((r) => r.land === land && z.rollen[r.id]).length;

  // ---------- Aufbau der Seite ----------
  let stil = document.getElementById("faisa-stil");
  if (!stil) { stil = document.createElement("style"); stil.id = "faisa-stil"; document.head.appendChild(stil); }
  stil.textContent = `
    .stMainBlockContainer { max-width: 1150px !important; padding-top: 2.5rem !important; }
    #faisa-abenteuer { position: relative; width: 100%; height: min(76vh, 760px); min-height: 420px; border-radius: 18px; overflow: hidden;
      background: #141021; font-family: "Source Sans Pro", system-ui, sans-serif; color: #fff6fb; user-select: none; -webkit-user-select: none; }
    #faisa-abenteuer canvas { width: 100%; height: 100%; display: block; touch-action: none; cursor: pointer; }
    .fa-hud { position: absolute; left: 0; right: 0; top: 0; display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 8px 10px;
      background: linear-gradient(#141021ee, #14102100); font-weight: 800; font-size: 15px; pointer-events: none; }
    .fa-hud > span, .fa-hud > button { background: #261d33e6; border-radius: 999px; padding: 4px 10px; white-space: nowrap; }
    .fa-hud button { pointer-events: auto; border: 0; color: inherit; font: inherit; cursor: pointer; }
    .fa-xp { display: inline-block; width: 90px; height: 8px; border-radius: 8px; background: #ffffff33; margin-left: 6px; vertical-align: middle; overflow: hidden; }
    .fa-xp i { display: block; height: 100%; background: #ff2d78; transition: width .4s; }
    .fa-ziel { position: absolute; left: 10px; bottom: 10px; max-width: calc(100% - 170px); background: #261d33e6; border-left: 5px solid #ff2d78;
      border-radius: 10px; padding: 8px 12px; font-weight: 700; font-size: 15px; pointer-events: none; }
    .fa-hinweis { position: absolute; left: 50%; top: 64px; transform: translateX(-50%); background: #ff2d78; border-radius: 999px; padding: 8px 18px;
      font-weight: 800; opacity: 0; transition: opacity .3s; pointer-events: none; text-align: center; max-width: 90%; }
    .fa-dialog { position: absolute; inset: 0; display: none; align-items: center; justify-content: center; background: #0a0714b3; padding: 12px; }
    .fa-karte { width: min(560px, 100%); background: #261d33; border: 2px solid #ff2d78; border-radius: 20px; padding: 18px; box-shadow: 0 12px 40px #000a;
      animation: fa-rein .18s ease-out; }
    @keyframes fa-rein { from { transform: scale(.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }
    .fa-kopf { font-size: 13px; letter-spacing: .05em; text-transform: uppercase; opacity: .8; font-weight: 700; }
    .fa-text { font-size: 21px; font-weight: 800; line-height: 1.3; margin: 6px 0 14px; white-space: pre-line; }
    .fa-wahl { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .fa-wahl.eins { grid-template-columns: 1fr; }
    .fa-wahl button { border: 2px solid #ffffff2e; background: #17121f; color: inherit; font: inherit; font-weight: 700; font-size: 16px; border-radius: 14px;
      padding: 13px 10px; cursor: pointer; transition: transform .08s, border-color .1s; }
    .fa-wahl button:hover:not(:disabled) { border-color: #ff2d78; transform: translateY(-1px); }
    .fa-wahl button.gut { background: #1f8f45; border-color: #2ec45a; }
    .fa-wahl button.schlecht { background: #a52828; border-color: #ff5a5a; }
    .fa-wahl button.haupt { background: #ff2d78; border-color: #ff2d78; }
    .fa-meldung { margin-top: 12px; font-weight: 700; min-height: 1.3em; }
    @media (max-width: 560px) { .fa-wahl { grid-template-columns: 1fr; } .fa-text { font-size: 18px; } .fa-hud { font-size: 13px; } }
  `;
  wurzel.innerHTML = "";
  const neu = (tag, klasse, eltern) => { const e = document.createElement(tag); if (klasse) e.className = klasse; (eltern || wurzel).appendChild(e); return e; };
  const leinwand = neu("canvas"), ctx = leinwand.getContext("2d");
  const hud = neu("div", "fa-hud"), zielFeld = neu("div", "fa-ziel"), hinweisFeld = neu("div", "fa-hinweis"), dialog = neu("div", "fa-dialog");
  const hudHerzen = neu("span", "", hud), hudGurt = neu("span", "", hud), hudLand = neu("span", "", hud), hudPokale = neu("span", "", hud), hudMikros = neu("span", "", hud);
  const hudGurtText = neu("span", "", hudGurt), hudBalken = neu("i", "", neu("span", "fa-xp", hudGurt));
  const tonKnopf = neu("button", "", hud), neuKnopf = neu("button", "", hud);
  neuKnopf.textContent = "⟲"; neuKnopf.title = "Abenteuer neu starten";

  // ---------- Ton ----------
  let audio = null;
  function klang(noten, art = "triangle", dauer = 0.12) {
    if (!z.ton) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      noten.forEach((frequenz, i) => {
        const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime + i * dauer;
        o.type = art; o.frequency.value = frequenz; g.gain.setValueAtTime(0.12, t); g.gain.exponentialRampToValueAtTime(0.001, t + dauer * 1.4);
        o.connect(g); g.connect(audio.destination); o.start(t); o.stop(t + dauer * 1.5);
      });
    } catch (fehler) { /* kein Ton verfügbar */ }
  }

  // ---------- Effekte ----------
  const funken = [], schwebend = [];
  let wackeln = 0, banner = null, landJetzt = null, combo = 0, pausiert = false, gestoppt = false, hinweisUhr = 0;
  function konfetti(x, y, menge = 26) {
    for (let i = 0; i < menge; i++) { const w = Math.random() * 6.283, v = 80 + Math.random() * 260;
      funken.push({ x, y, vx: Math.cos(w) * v, vy: Math.sin(w) * v - 120, leben: 0.7 + Math.random() * 0.6, farbe: `hsl(${Math.random() * 360} 90% 62%)` }); }
  }
  const schwebe = (text, x = z.x, y = z.y - 60, farbe = "#ffd93b") => schwebend.push({ text, x, y, leben: 1.3, farbe });
  function hinweis(text, dauer = 2200) { hinweisFeld.textContent = text; hinweisFeld.style.opacity = 1; clearTimeout(hinweisUhr); hinweisUhr = setTimeout(() => { hinweisFeld.style.opacity = 0; }, dauer); }
  function xpPlus(menge, text) {
    const vorher = guertel();
    z.xp += menge; schwebe(`+${menge} XP${text ? " " + text : ""}`);
    if (guertel() !== vorher) { konfetti(z.x, z.y - 30, 60); klang([523, 659, 784, 1047], "triangle", 0.14); hinweis(`🎉 Gürtelprüfung bestanden: ${guertel()[1]}!`, 3500); }
    zeigeHud();
  }

  // ---------- Anzeige oben ----------
  function zeigeHud() {
    const g = guertel(), i = GUERTEL.indexOf(g), naechste = GUERTEL[i + 1];
    const anteil = naechste ? ((z.xp - g[0]) / (naechste[0] - g[0])) * 100 : 100;
    hudHerzen.textContent = "❤️".repeat(z.herzen) + "🖤".repeat(Math.max(0, maxHerzen() - z.herzen));
    hudGurtText.textContent = `🥋 ${g[1]} · ${z.xp} XP`;
    hudBalken.style.width = anteil + "%";
    hudLand.textContent = landJetzt ? `📍 ${landJetzt}${z.siege[landJetzt] ? " 🏆" : ` · 📜 ${Math.min(rollenIn(landJetzt), ROLLEN_NOETIG)}/${ROLLEN_NOETIG}`}` : "📍 unterwegs";
    hudPokale.textContent = `🏆 ${anzahlSiege()}/16`;
    hudMikros.textContent = `🎤 ${Object.keys(z.mikros).length}/16`;
    tonKnopf.textContent = z.ton ? "🔊" : "🔇";
  }
  tonKnopf.onclick = () => { z.ton = !z.ton; speichern(); zeigeHud(); klang([660]); };
  neuKnopf.onclick = () => { if (window.confirm("Wirklich das ganze Abenteuer von vorn beginnen?")) { try { localStorage.removeItem(SPEICHER); } catch (fehler) { /* egal */ } window.location.reload(); } };

  // ---------- Dialoge ----------
  let dialogTaste = null;
  function zeigeText(kopf, text, knoepfe) {
    return new Promise((fertig) => {
      dialog.innerHTML = ""; dialog.style.display = "flex";
      const karte = neu("div", "fa-karte", dialog);
      neu("div", "fa-kopf", karte).textContent = kopf;
      neu("div", "fa-text", karte).textContent = text;
      const feld = neu("div", "fa-wahl" + (knoepfe.length === 1 ? " eins" : ""), karte);
      const ende = (i) => { dialogTaste = null; dialog.style.display = "none"; fertig(i); };
      knoepfe.forEach((beschriftung, i) => { const k = neu("button", i === 0 ? "haupt" : "", feld); k.textContent = beschriftung; k.onclick = () => ende(i); });
      dialogTaste = (taste) => { if (taste === "Enter" || taste === " ") ende(0); };
    });
  }
  function zeigeFrage(kopf, frage) {
    return new Promise((fertig) => {
      dialog.innerHTML = ""; dialog.style.display = "flex";
      const karte = neu("div", "fa-karte", dialog);
      neu("div", "fa-kopf", karte).textContent = kopf;
      neu("div", "fa-text", karte).textContent = frage.q;
      const feld = neu("div", "fa-wahl", karte), meldung = neu("div", "fa-meldung", karte);
      const optionen = misch([frage.a, ...frage.f]), knoepfe = [];
      let beantwortet = false;
      const ende = (richtig) => { dialogTaste = null; dialog.style.display = "none"; fertig(richtig); };
      const waehle = (i) => {
        if (beantwortet) return;
        beantwortet = true;
        const richtig = optionen[i] === frage.a;
        knoepfe.forEach((k, j) => { k.disabled = true; if (optionen[j] === frage.a) k.classList.add("gut"); else if (j === i) k.classList.add("schlecht"); });
        if (richtig) {
          klang([660, 880]); meldung.textContent = LOB[Math.floor(Math.random() * LOB.length)];
          setTimeout(() => ende(true), 750);
        } else {
          klang([196, 147], "sawtooth", 0.16); wackeln = 0.35;
          meldung.textContent = `Richtig ist: ${frage.a}`;
          const weiter = neu("div", "fa-wahl eins", karte), k = neu("button", "haupt", weiter);
          weiter.style.marginTop = "10px"; k.textContent = "Weiter ➜"; k.onclick = () => ende(false);
          dialogTaste = (taste) => { if (taste === "Enter" || taste === " ") ende(false); };
        }
      };
      optionen.forEach((text, i) => { const k = neu("button", "", feld); k.textContent = text; k.onclick = () => waehle(i); knoepfe.push(k); });
      dialogTaste = (taste) => { const i = "1234".indexOf(taste); if (i >= 0 && i < optionen.length) waehle(i); };
    });
  }

  // ---------- Ereignisse ----------
  function herzWeg() { z.herzen = Math.max(0, z.herzen - 1); combo = 0; zeigeHud(); }
  async function ohnmacht() {
    const besiegt = Object.keys(z.siege), ort = besiegt.length ? laender[besiegt[besiegt.length - 1]] : null;
    await zeigeText("💫 Autsch!", `Keine Herzen mehr! Du ruhst dich kurz aus und wachst ${ort ? "in " + ort.d.hauptstadt : "am Startpunkt"} wieder auf – mit vollen Herzen.`, ["Weiter geht's 💪"]);
    z.x = ort ? ort.bx + 50 : START.x; z.y = ort ? ort.by + 50 : START.y;
    if (!begehbar(z.x, z.y)) { z.x = ort ? ort.bx : START.x; z.y = ort ? ort.by : START.y; }
    z.herzen = maxHerzen(); ziel = null; zeigeHud();
  }
  async function oeffneRolle(rolle) {
    pausiert = true;
    const fragen = D.laender[rolle.land].fragen, tagNr = Math.floor(Date.now() / 864e5);
    const frage = fragen[(rolle.nr + rolle.versuch + (z.siege[rolle.land] ? tagNr : 0)) % fragen.length];
    if (await zeigeFrage(`📜 Wissens-Rolle · ${rolle.land}`, frage)) {
      z.rollen[rolle.id] = 1; combo++;
      const jackpot = Math.random() < 1 / 6, menge = (10 + Math.min(combo - 1, 5) * 2) * (jackpot ? 3 : 1);
      konfetti(rolle.x, rolle.y - 10, jackpot ? 60 : 22);
      xpPlus(menge, jackpot ? "🎰 JACKPOT x3!" : combo >= 3 ? `🔥 Combo x${combo}` : "");
      if (!z.siege[rolle.land] && rollenIn(rolle.land) === ROLLEN_NOETIG) { klang([523, 784]); hinweis(`🔓 ${D.laender[rolle.land].gegner[1]} wartet in ${D.laender[rolle.land].hauptstadt} auf dich!`, 3200); }
    } else { rolle.versuch++; rolle.sperre = true; herzWeg(); }
    speichern();
    if (z.herzen <= 0) await ohnmacht();
    pausiert = false;
  }
  function bossFragen(land) {
    const d = D.laender[land], staedte = [...new Set(NAMEN.map((n) => D.laender[n].hauptstadt))];
    return [
      { q: `Wie heißt die Landeshauptstadt von ${land}?`, a: d.hauptstadt, f: wahl(staedte.filter((s) => s !== d.hauptstadt), 3) },
      { q: `${d.hauptstadt} ist die Landeshauptstadt von …?`, a: land, f: wahl(NAMEN.filter((n) => n !== land), 3) },
      ...misch(d.fragen.slice()),
    ];
  }
  async function bossKampf(boss) {
    pausiert = true; boss.sperre = true;
    const d = D.laender[boss.land], [emoji, name, spruch] = d.gegner, rueckkampf = Boolean(z.siege[boss.land]);
    if (!rueckkampf && rollenIn(boss.land) < ROLLEN_NOETIG) {
      await zeigeText(`${emoji} ${name} · ${d.hauptstadt}`, `„Du willst gegen mich kämpfen? Sammle erst ${ROLLEN_NOETIG} Wissens-Rollen 📜 in ${boss.land}!“\n\nDu hast ${rollenIn(boss.land)} von ${ROLLEN_NOETIG}.`, ["Alles klar!"]);
      pausiert = false; return;
    }
    const start = await zeigeText(`${emoji} ${name} · ${d.hauptstadt}`, rueckkampf ? "„Du schon wieder? Na gut – Rückkampf!“" : `„${spruch}“`, ["Kampf starten 🥊", "Lieber noch nicht"]);
    if (start !== 0) { pausiert = false; return; }
    const fragen = bossFragen(boss.land);
    let energie = 3, i = 0;
    while (energie > 0 && z.herzen > 0) {
      if (await zeigeFrage(`${emoji} ${name} · Energie ${"💢".repeat(energie)}`, fragen[i++ % fragen.length])) { energie--; combo++; konfetti(boss.x, boss.y - 20, 14); }
      else herzWeg();
    }
    if (energie === 0) {
      klang([523, 659, 784, 1047, 1319], "triangle", 0.13); konfetti(boss.x, boss.y - 20, 90);
      if (rueckkampf) { xpPlus(25, "Rückkampf gewonnen!"); }
      else {
        z.siege[boss.land] = 1; z.herzen = maxHerzen(); xpPlus(50, "K.O.!"); zeichneMinikarte();
        const alle = anzahlSiege() === 16;
        await zeigeText(alle ? "👑 Deutsche Meisterin!" : `🏆 K.O.! ${boss.land} gehört dir!`,
          alle ? "Du hast alle 16 Gegner besiegt und kennst jetzt jedes Bundesland mit seiner Hauptstadt. Unglaublich stark, Faisa!\n\nJeden Tag gibt es neue Wissens-Rollen, und jeder Gegner nimmt einen Rückkampf an."
            : `${emoji} ${name} ist besiegt.\nMerke dir: Die Landeshauptstadt von ${boss.land} ist ${d.hauptstadt}.\n\nNoch ${16 - anzahlSiege()} Bundesländer – deine Herzen sind wieder voll.`, ["Weiter ➜"]);
        if (alle) konfetti(z.x, z.y - 30, 200);
      }
    } else await ohnmacht();
    speichern(); zeigeHud(); pausiert = false;
  }
  async function nimmMikro(mikro) {
    pausiert = true; mikro.sperre = true;
    const frage = D.deutschland[mikro.nr % D.deutschland.length];
    if (await zeigeFrage("🎤 Geheimes Mikro · Deutschland-Frage", frage)) { z.mikros[mikro.land] = 1; konfetti(mikro.x, mikro.y, 40); xpPlus(20, "🎤 Mikro gefunden!"); }
    else herzWeg();
    speichern();
    if (z.herzen <= 0) await ohnmacht();
    pausiert = false;
  }

  // ---------- Steuerung ----------
  const tasten = {}; let ziel = null, blick = 1, phase = 0, laeuft = false, gedrueckt = false;
  const RICHTUNG = { ArrowLeft: "l", a: "l", A: "l", ArrowRight: "r", d: "r", D: "r", ArrowUp: "o", w: "o", W: "o", ArrowDown: "u", s: "u", S: "u" };
  function tasteRunter(e) {
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (dialog.style.display === "flex") { if (dialogTaste && !e.repeat) { dialogTaste(e.key); } if (e.key === " " || e.key.startsWith("Arrow")) e.preventDefault(); return; }
    const r = RICHTUNG[e.key];
    if (r) { tasten[r] = true; e.preventDefault(); }
  }
  function tasteHoch(e) { const r = RICHTUNG[e.key]; if (r) tasten[r] = false; }
  function zeigerZiel(e) {
    const feld = leinwand.getBoundingClientRect();
    ziel = { x: sicht.x + ((e.clientX - feld.left) / feld.width) * sicht.b, y: sicht.y + ((e.clientY - feld.top) / feld.height) * sicht.h };
  }
  leinwand.addEventListener("pointerdown", (e) => { gedrueckt = true; zeigerZiel(e); e.preventDefault(); });
  leinwand.addEventListener("pointermove", (e) => { if (gedrueckt) zeigerZiel(e); });
  const loslassen = () => { gedrueckt = false; };
  window.addEventListener("pointerup", loslassen);
  window.addEventListener("keydown", tasteRunter);
  window.addEventListener("keyup", tasteHoch);

  // ---------- Spiellogik ----------
  function naechstesZiel() {
    if (!landJetzt) return { text: "Du bist am Rand der Karte – lauf zurück ins Land!", ort: START };
    const naehe = (liste) => liste.reduce((best, o) => (!best || Math.hypot(o.x - z.x, o.y - z.y) < Math.hypot(best.x - z.x, best.y - z.y) ? o : best), null);
    if (z.siege[landJetzt]) {
      const offen = naehe(bosse.filter((b) => !z.siege[b.land]));
      if (!offen) return { text: "👑 Alle 16 Länder erobert! Sammle neue Rollen 📜 und Mikros 🎤 oder fordere Rückkämpfe.", ort: null };
      return { text: `${landJetzt} ist erobert 🏆 Weiter nach ${offen.land} – folge dem Pfeil!`, ort: offen };
    }
    const habe = rollenIn(landJetzt), gegner = D.laender[landJetzt].gegner[1];
    if (habe < ROLLEN_NOETIG) return { text: `Finde Wissens-Rollen 📜 in ${landJetzt}: ${habe}/${ROLLEN_NOETIG}`, ort: naehe(rollen.filter((r) => r.land === landJetzt && !z.rollen[r.id])) };
    return { text: `Fordere ${gegner} in ${D.laender[landJetzt].hauptstadt} heraus! 🥊`, ort: bosse.find((b) => b.land === landJetzt) };
  }
  let auftrag = { text: "", ort: null }, auftragUhr = 0;
  function schritt(dt) {
    let dx = (tasten.r ? 1 : 0) - (tasten.l ? 1 : 0), dy = (tasten.u ? 1 : 0) - (tasten.o ? 1 : 0);
    if (dx || dy) ziel = null;
    else if (ziel) { const ex = ziel.x - z.x, ey = ziel.y - z.y, l = Math.hypot(ex, ey); if (l < 6) ziel = null; else { dx = ex / l; dy = ey / l; } }
    laeuft = Boolean(dx || dy);
    if (laeuft) {
      const l = Math.hypot(dx, dy), s = TEMPO * dt, nx = z.x + (dx / l) * s, ny = z.y + (dy / l) * s;
      if (begehbar(nx, ny)) { z.x = nx; z.y = ny; } else if (begehbar(nx, z.y)) z.x = nx; else if (begehbar(z.x, ny)) z.y = ny; else { ziel = null; laeuft = false; }
      if (Math.abs(dx) > 0.1) blick = dx < 0 ? -1 : 1;
      phase += dt * 11;
    }
    const land = landBei(z.x, z.y);
    if (land && land !== landJetzt) {
      landJetzt = land; banner = { text: land, leben: 2.4 };
      if (!z.besucht[land]) { z.besucht[land] = 1; xpPlus(5, "Neues Land entdeckt!"); klang([440, 554]); zeichneMinikarte(); speichern(); }
      zeigeHud();
    }
    const jetzt = Date.now(), nah = (o, r) => Math.hypot(o.x - z.x, o.y - z.y) < r;
    for (const ding of [...rollen, ...bosse, ...mikros]) if (ding.sperre && !nah(ding, 70)) ding.sperre = false;
    for (const r of rollen) if (!z.rollen[r.id] && !r.sperre && nah(r, 26)) { oeffneRolle(r); return; }
    for (const b of bosse) if (!b.sperre && nah(b, 38)) { bossKampf(b); return; }
    for (const m of mikros) if (!z.mikros[m.land] && !m.sperre && nah(m, 26)) { nimmMikro(m); return; }
    for (const su of suppen) if (su.wegBis < jetzt && nah(su, 26)) {
      su.wegBis = jetzt + 90000; klang([392, 523, 659]);
      if (z.herzen < maxHerzen()) { z.herzen++; schwebe("+1 ❤️ Buldak!", z.x, z.y - 60, "#ff7096"); zeigeHud(); } else xpPlus(5, "🌶️ scharf!");
      speichern();
    }
    if (jetzt > auftragUhr) { auftragUhr = jetzt + 300; auftrag = naechstesZiel(); if (zielFeld.textContent !== auftrag.text) zielFeld.textContent = auftrag.text; }
  }

  // ---------- Zeichnen ----------
  const sicht = { x: 0, y: 0, b: 900, h: 700 };
  const mini = document.createElement("canvas");
  const MINI_B = 118, MINI_H = Math.round((MINI_B * H) / W);
  mini.width = MINI_B * 2; mini.height = MINI_H * 2;
  const landFarbe = (L) => (z.siege[L.name] ? `hsl(${L.ton} 70% 56%)` : z.besucht[L.name] ? `hsl(${L.ton} 28% 34%)` : "#322b45");
  function zeichneMinikarte() {
    const g = mini.getContext("2d");
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, mini.width, mini.height);
    g.setTransform(mini.width / W, 0, 0, mini.height / H, 0, 0);
    for (const name of nachGroesse.slice().reverse()) { g.fillStyle = landFarbe(laender[name]); g.fill(laender[name].pfad); }
  }
  function zeichen(text, x, y, groesse) { ctx.font = `${groesse}px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(text, x, y); }
  function schrift(text, x, y, groesse, farbe, rand = "#141021") {
    ctx.font = `800 ${groesse}px "Source Sans Pro",system-ui,sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.lineWidth = groesse / 5; ctx.lineJoin = "round"; ctx.strokeStyle = rand; ctx.strokeText(text, x, y); ctx.fillStyle = farbe; ctx.fillText(text, x, y);
  }
  function zeichneFigur(x, y) {
    const schwung = laeuft ? Math.sin(phase) : 0, hueft = laeuft ? Math.abs(Math.sin(phase)) * 2 : 0;
    ctx.save(); ctx.translate(x, y); ctx.scale(blick, 1);
    ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.ellipse(0, 2, 14, 5, 0, 0, 6.283); ctx.fill();
    ctx.strokeStyle = "#f2f2f2"; ctx.lineWidth = 7; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(-5, -15); ctx.lineTo(-5 - schwung * 6, -2); ctx.moveTo(5, -15); ctx.lineTo(5 + schwung * 6, -2); ctx.stroke();
    ctx.translate(0, -hueft);
    ctx.fillStyle = "#fafafa"; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(-11, -36, 22, 24, 7) : ctx.rect(-11, -36, 22, 24); ctx.fill();
    ctx.fillStyle = guertel()[2]; ctx.fillRect(-11, -21, 22, 5); ctx.strokeStyle = "#0006"; ctx.lineWidth = 1; ctx.strokeRect(-11, -21, 22, 5);
    ctx.fillStyle = "#ff2d78"; ctx.beginPath(); ctx.arc(-13, -24 + schwung * 3, 5, 0, 6.283); ctx.arc(13, -24 - schwung * 3, 5, 0, 6.283); ctx.fill();
    ctx.fillStyle = "#2b1b12"; ctx.beginPath(); ctx.ellipse(-12, -42 + schwung, 5, 10, 0.5, 0, 6.283); ctx.fill();
    ctx.fillStyle = "#e3b189"; ctx.beginPath(); ctx.arc(0, -45, 11, 0, 6.283); ctx.fill();
    ctx.fillStyle = "#2b1b12"; ctx.beginPath(); ctx.arc(0, -47, 11.5, 3.3, 6.2); ctx.fill();
    ctx.fillStyle = "#1c1c1c"; ctx.beginPath(); ctx.arc(5, -44, 1.7, 0, 6.283); ctx.fill();
    ctx.restore();
  }
  function zeichne(zeit) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2), cb = leinwand.clientWidth, ch = leinwand.clientHeight;
    if (leinwand.width !== Math.round(cb * dpr) || leinwand.height !== Math.round(ch * dpr)) { leinwand.width = Math.round(cb * dpr); leinwand.height = Math.round(ch * dpr); }
    const zoom = cb < 560 ? cb / 560 : Math.max(cb / 950, 0.85);
    sicht.b = cb / zoom; sicht.h = ch / zoom;
    sicht.x = klemme(z.x - sicht.b / 2, -80, Math.max(-80, W + 80 - sicht.b)) + (wackeln > 0 ? (Math.random() - 0.5) * 14 : 0);
    sicht.y = klemme(z.y - sicht.h / 2, -80, Math.max(-80, H + 80 - sicht.h)) + (wackeln > 0 ? (Math.random() - 0.5) * 14 : 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = "#1b1629"; ctx.fillRect(0, 0, leinwand.width, leinwand.height);
    ctx.setTransform(dpr * zoom, 0, 0, dpr * zoom, -sicht.x * dpr * zoom, -sicht.y * dpr * zoom);
    const sichtbar = (x, y, rand = 80) => x > sicht.x - rand && x < sicht.x + sicht.b + rand && y > sicht.y - rand && y < sicht.y + sicht.h + rand;

    // Meere und Nachbarländer
    ctx.fillStyle = "#14365f";
    ctx.beginPath(); ctx.ellipse(wx(7.0), wy(54.9), 900, 520, 0, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.ellipse(wx(12.6), wy(55.0), 1100, 420, 0, 0, 6.283); ctx.fill();
    schrift("Nordsee 🌊", wx(7.2), wy(54.35), 30, "#9fd0ff", "#14365f"); schrift("Ostsee 🌊", wx(12.2), wy(54.62), 30, "#9fd0ff", "#14365f");
    for (const [name, lon, lat] of NACHBARN) schrift(name, wx(lon), wy(lat), 26, "#8f86a8", "#1b1629");

    // Bundesländer
    for (const name of nachGroesse.slice().reverse()) {
      const L = laender[name];
      ctx.fillStyle = landFarbe(L); ctx.fill(L.pfad);
      ctx.strokeStyle = "#141021"; ctx.lineWidth = 4; ctx.stroke(L.pfad);
    }
    for (const name of NAMEN) {
      const L = laender[name];
      if (!sichtbar(L.lx, L.ly, 300)) continue;
      ctx.globalAlpha = 0.5; schrift(z.besucht[name] ? name.toUpperCase() : "? ? ?", L.lx, L.ly, L.groesse < 60000 ? 15 : 30, "#ffffff"); ctx.globalAlpha = 1;
    }

    // Dinge
    const wippen = Math.sin(zeit / 260) * 4, jetzt = Date.now();
    for (const su of suppen) if (su.wegBis < jetzt && sichtbar(su.x, su.y)) zeichen("🍜", su.x, su.y + wippen * 0.5, 26);
    for (const m of mikros) if (!z.mikros[m.land] && sichtbar(m.x, m.y)) zeichen("🎤", m.x, m.y - wippen * 0.5, 22);
    for (const r of rollen) if (!z.rollen[r.id] && sichtbar(r.x, r.y)) {
      ctx.fillStyle = "#ffd93b55"; ctx.beginPath(); ctx.arc(r.x, r.y + 4, 20 + wippen, 0, 6.283); ctx.fill();
      zeichen("📜", r.x, r.y + wippen, 30);
    }
    for (const b of bosse) {
      if (!sichtbar(b.x, b.y, 140)) continue;
      const d = D.laender[b.land], besiegt = z.siege[b.land], bereit = besiegt || rollenIn(b.land) >= ROLLEN_NOETIG;
      ctx.fillStyle = besiegt ? "#ffd70066" : bereit ? "#ff2d7888" : "#00000055";
      ctx.beginPath(); ctx.arc(b.x, b.y + 6, 30 + (bereit && !besiegt ? wippen : 0), 0, 6.283); ctx.fill();
      zeichen(d.gegner[0], b.x, b.y - (besiegt ? 0 : Math.abs(wippen)), 42);
      zeichen(besiegt ? "🏆" : bereit ? "🥊" : "🔒", b.x + 26, b.y - 26, 20);
      schrift(d.hauptstadt, b.x, b.y + 44, 19, "#ffffff");
      schrift(d.gegner[1], b.x, b.y + 64, 13, "#ffb3cf");
    }

    // Wegweiser zum nächsten Ziel
    if (auftrag.ort && !pausiert) {
      const ex = auftrag.ort.x - z.x, ey = auftrag.ort.y - z.y, l = Math.hypot(ex, ey);
      if (l > 130) {
        const w = Math.atan2(ey, ex), r = 62 + Math.sin(zeit / 180) * 5;
        ctx.save(); ctx.translate(z.x + Math.cos(w) * r, z.y - 22 + Math.sin(w) * r); ctx.rotate(w);
        ctx.fillStyle = "#ffd93b"; ctx.strokeStyle = "#141021"; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(16, 0); ctx.lineTo(-8, -11); ctx.lineTo(-3, 0); ctx.lineTo(-8, 11); ctx.closePath(); ctx.stroke(); ctx.fill(); ctx.restore();
      }
    }
    if (ziel) { ctx.strokeStyle = "#ffffff99"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(ziel.x, ziel.y, 9 + Math.sin(zeit / 120) * 3, 0, 6.283); ctx.stroke(); }
    zeichneFigur(z.x, z.y);

    for (const f of funken) { ctx.globalAlpha = klemme(f.leben * 1.6, 0, 1); ctx.fillStyle = f.farbe; ctx.fillRect(f.x - 4, f.y - 4, 8, 8); }
    ctx.globalAlpha = 1;
    for (const t of schwebend) { ctx.globalAlpha = klemme(t.leben, 0, 1); schrift(t.text, t.x, t.y, 22, t.farbe); }
    ctx.globalAlpha = 1;

    // Feste Anzeige: Minikarte und Land-Banner
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const mx = cb - MINI_B - 10, my = ch - MINI_H - 10;
    ctx.fillStyle = "#141021d9"; ctx.strokeStyle = "#ffffff33"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(mx - 5, my - 5, MINI_B + 10, MINI_H + 10, 10) : ctx.rect(mx - 5, my - 5, MINI_B + 10, MINI_H + 10); ctx.fill(); ctx.stroke();
    ctx.drawImage(mini, mx, my, MINI_B, MINI_H);
    ctx.fillStyle = Math.floor(zeit / 350) % 2 ? "#ffffff" : "#ff2d78"; ctx.beginPath(); ctx.arc(mx + (z.x / W) * MINI_B, my + (z.y / H) * MINI_H, 4, 0, 6.283); ctx.fill();
    if (banner) { ctx.globalAlpha = klemme(banner.leben, 0, 1); schrift("📍 " + banner.text, cb / 2, ch * 0.3, cb < 560 ? 30 : 44, "#ffffff"); ctx.globalAlpha = 1; }
  }

  // ---------- Schleife ----------
  let letzte = performance.now(), speicherUhr = 0;
  function runde(zeit) {
    if (gestoppt) return;
    if (!document.body.contains(wurzel)) { stopp(); return; }
    const dt = Math.min((zeit - letzte) / 1000, 0.05); letzte = zeit;
    if (!pausiert) schritt(dt);
    for (const f of funken) { f.x += f.vx * dt; f.y += f.vy * dt; f.vy += 520 * dt; f.leben -= dt; }
    for (const t of schwebend) { t.y -= 34 * dt; t.leben -= dt; }
    for (let i = funken.length - 1; i >= 0; i--) if (funken[i].leben <= 0) funken.splice(i, 1);
    for (let i = schwebend.length - 1; i >= 0; i--) if (schwebend[i].leben <= 0) schwebend.splice(i, 1);
    if (wackeln > 0) wackeln -= dt;
    if (banner && (banner.leben -= dt) <= 0) banner = null;
    if (zeit > speicherUhr) { speicherUhr = zeit + 4000; speichern(); }
    zeichne(zeit);
    requestAnimationFrame(runde);
  }
  function stopp() {
    gestoppt = true; speichern();
    window.removeEventListener("keydown", tasteRunter); window.removeEventListener("keyup", tasteHoch); window.removeEventListener("pointerup", loslassen);
    if (stil.parentNode) stil.parentNode.removeChild(stil);
  }
  window.faisaSpiel = { stopp, zustand: () => z, dinge: { rollen, bosse, mikros, suppen }, landBei, begehbar, geheZu: (x, y) => { z.x = x; z.y = y; } };

  // ---------- Start ----------
  (async () => {
    pausiert = true;
    landJetzt = landBei(z.x, z.y); if (landJetzt) z.besucht[landJetzt] = 1;
    zeichneMinikarte(); zeigeHud(); requestAnimationFrame(runde);
    const heute = new Date().toLocaleDateString("sv"), gestern = new Date(Date.now() - 864e5).toLocaleDateString("sv");
    if (z.neu) {
      await zeigeText("🗺️ Faisas Deutschland-Abenteuer", "Erobere alle 16 Bundesländer!\n\n📜 Sammle in jedem Land 3 Wissens-Rollen.\n🥊 Dann besiege den Gegner in der Landeshauptstadt.\n🍜 Buldak-Suppe füllt deine Herzen auf.\n\nLaufen: Pfeiltasten oder WASD – oder tippe dorthin, wo du hinwillst.", ["Los geht's! 🥋"]);
      z.neu = false; z.tag = heute; z.tage = 1;
    } else if (z.tag !== heute) {
      z.tage = z.tag === gestern ? (z.tage || 0) + 1 : 1; z.tag = heute; z.herzen = maxHerzen();
      for (const r of rollen) if (z.siege[r.land]) delete z.rollen[r.id]; // neue Rollen in eroberten Ländern
      await zeigeText(`🔥 Tag ${z.tage} in Folge!`, "Schön, dass du wieder da bist!\nDeine Herzen sind voll, und in deinen eroberten Ländern liegen neue Wissens-Rollen.", ["Weiter ➜"]);
      xpPlus(20, "Tages-Bonus");
    }
    klang([523, 659]); speichern(); zeigeHud(); pausiert = false;
  })();
}
