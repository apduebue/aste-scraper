from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
import re

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9",
}

REGIONI = {
    "AG":"sicilia","AL":"piemonte","AN":"marche","AO":"valle-daosta","AR":"toscana",
    "AP":"marche","AT":"piemonte","AV":"campania","BA":"puglia","BL":"veneto",
    "BN":"campania","BG":"lombardia","BI":"piemonte","BO":"emilia-romagna","BZ":"trentino-alto-adige",
    "BS":"lombardia","BR":"puglia","CA":"sardegna","CB":"molise","CE":"campania",
    "CT":"sicilia","CZ":"calabria","CH":"abruzzo","CO":"lombardia","CS":"calabria",
    "CR":"lombardia","CN":"piemonte","FE":"emilia-romagna","FI":"toscana","FG":"puglia",
    "FC":"emilia-romagna","FR":"lazio","GE":"liguria","GO":"friuli-venezia-giulia","GR":"toscana",
    "IM":"liguria","IS":"molise","AQ":"abruzzo","SP":"liguria","LT":"lazio",
    "LE":"puglia","LC":"lombardia","LI":"toscana","LO":"lombardia","LU":"toscana",
    "MC":"marche","MN":"lombardia","MS":"toscana","MT":"basilicata","ME":"sicilia",
    "MI":"lombardia","MO":"emilia-romagna","MB":"lombardia","NA":"campania","NO":"piemonte",
    "NU":"sardegna","OR":"sardegna","PD":"veneto","PA":"sicilia","PR":"emilia-romagna",
    "PV":"lombardia","PG":"umbria","PU":"marche","PE":"abruzzo","PC":"emilia-romagna",
    "PI":"toscana","PT":"toscana","PN":"friuli-venezia-giulia","PZ":"basilicata","PO":"toscana",
    "RG":"sicilia","RC":"calabria","RE":"emilia-romagna","RI":"lazio","RN":"emilia-romagna",
    "RM":"lazio","RO":"veneto","SA":"campania","SS":"sardegna","SV":"liguria",
    "SI":"toscana","SR":"sicilia","SO":"lombardia","TA":"puglia","TE":"abruzzo",
    "TR":"umbria","TO":"piemonte","TP":"sicilia","TN":"trentino-alto-adige","TV":"veneto",
    "TS":"friuli-venezia-giulia","UD":"friuli-venezia-giulia","VA":"lombardia","VE":"veneto",
    "VB":"piemonte","VC":"piemonte","VR":"veneto","VV":"calabria","VI":"veneto","VT":"lazio"
}

NOMI_PROVINCE = {
    "AG":"Agrigento","AL":"Alessandria","AN":"Ancona","AO":"Aosta","AR":"Arezzo",
    "AP":"Ascoli Piceno","AT":"Asti","AV":"Avellino","BA":"Bari","BL":"Belluno",
    "BN":"Benevento","BG":"Bergamo","BI":"Biella","BO":"Bologna","BZ":"Bolzano",
    "BS":"Brescia","BR":"Brindisi","CA":"Cagliari","CB":"Campobasso","CE":"Caserta",
    "CT":"Catania","CZ":"Catanzaro","CH":"Chieti","CO":"Como","CS":"Cosenza",
    "CR":"Cremona","CN":"Cuneo","FE":"Ferrara","FI":"Firenze","FG":"Foggia",
    "FC":"Forlì","FR":"Frosinone","GE":"Genova","GO":"Gorizia","GR":"Grosseto",
    "IM":"Imperia","IS":"Isernia","AQ":"L'Aquila","SP":"La Spezia","LT":"Latina",
    "LE":"Lecce","LC":"Lecco","LI":"Livorno","LO":"Lodi","LU":"Lucca",
    "MC":"Macerata","MN":"Mantova","MS":"Massa","MT":"Matera","ME":"Messina",
    "MI":"Milano","MO":"Modena","MB":"Monza","NA":"Napoli","NO":"Novara",
    "NU":"Nuoro","OR":"Oristano","PD":"Padova","PA":"Palermo","PR":"Parma",
    "PV":"Pavia","PG":"Perugia","PU":"Pesaro","PE":"Pescara","PC":"Piacenza",
    "PI":"Pisa","PT":"Pistoia","PN":"Pordenone","PZ":"Potenza","PO":"Prato",
    "RG":"Ragusa","RC":"Reggio Calabria","RE":"Reggio Emilia","RI":"Rieti","RN":"Rimini",
    "RM":"Roma","RO":"Rovigo","SA":"Salerno","SS":"Sassari","SV":"Savona",
    "SI":"Siena","SR":"Siracusa","SO":"Sondrio","TA":"Taranto","TE":"Teramo",
    "TR":"Terni","TO":"Torino","TP":"Trapani","TN":"Trento","TV":"Treviso",
    "TS":"Trieste","UD":"Udine","VA":"Varese","VE":"Venezia","VB":"Verbania",
    "VC":"Vercelli","VR":"Verona","VV":"Vibo Valentia","VI":"Vicenza","VT":"Viterbo"
}

def scrape_asteannunci(provincia):
    lotti = []
    nome = NOMI_PROVINCE.get(provincia, provincia).lower().replace(" ", "-").replace("'", "")
    regione = REGIONI.get(provincia, "")
    
    urls = [
        f"https://www.asteannunci.it/aste-immobiliari/{regione}/{nome}",
        f"https://www.asteannunci.it/aste-giudiziarie-{nome}",
    ]
    
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Cerca cards degli annunci
            cards = soup.select("article, .listing-item, .asta-card, .immobile-item, [class*='asta'], [class*='listing']")
            
            if not cards:
                # Prova a trovare link con pattern /aste/pvp/
                links = soup.find_all("a", href=re.compile(r"/aste/pvp/\d+"))
                for link in links[:30]:
                    href = link.get("href", "")
                    testo = link.get_text(strip=True)
                    parent = link.parent
                    testo_parent = parent.get_text(strip=True) if parent else testo
                    
                    # Estrai prezzo
                    prezzi = re.findall(r"[\d\.]{4,}", testo_parent.replace(",", ""))
                    prezzo = 0
                    for p in prezzi:
                        try:
                            v = int(p.replace(".", ""))
                            if 1000 < v < 5000000:
                                prezzo = v; break
                        except: pass
                    
                    if testo and len(testo) > 5:
                        lotti.append({
                            "titolo": testo_parent[:150].strip(),
                            "zona": provincia,
                            "prezzoBase": prezzo,
                            "valoreStimato": 0,
                            "mq": 0,
                            "dataAsta": "",
                            "tribunale": NOMI_PROVINCE.get(provincia, provincia),
                            "url": f"https://www.asteannunci.it{href}" if href.startswith("/") else href,
                            "fonte": "asteannunci.it"
                        })
            
            for card in cards[:30]:
                try:
                    titolo_el = card.select_one("h2, h3, h4, .titolo, .title, [class*='titolo'], [class*='title']")
                    prezzo_el = card.select_one(".prezzo, .price, [class*='prezzo'], [class*='price'], [class*='base']")
                    zona_el = card.select_one(".zona, .location, .comune, .indirizzo, [class*='zona'], [class*='location'], [class*='comune']")
                    link_el = card.select_one("a[href]")
                    
                    if not titolo_el: continue
                    titolo = titolo_el.get_text(strip=True)
                    prezzo_txt = prezzo_el.get_text(strip=True) if prezzo_el else card.get_text()
                    zona = zona_el.get_text(strip=True) if zona_el else NOMI_PROVINCE.get(provincia, provincia)
                    href = link_el.get("href", "") if link_el else ""
                    
                    numeri = re.findall(r"[\d\.]{4,}", prezzo_txt.replace(",", ""))
                    prezzo = 0
                    for n in numeri:
                        try:
                            v = int(n.replace(".", ""))
                            if 1000 < v < 5000000:
                                prezzo = v; break
                        except: pass
                    
                    lotti.append({
                        "titolo": titolo,
                        "zona": zona,
                        "prezzoBase": prezzo,
                        "valoreStimato": 0,
                        "mq": 0,
                        "dataAsta": "",
                        "tribunale": NOMI_PROVINCE.get(provincia, provincia),
                        "url": f"https://www.asteannunci.it{href}" if href.startswith("/") else href,
                        "fonte": "asteannunci.it"
                    })
                except: continue
            
            if lotti: break
        except Exception as e:
            print(f"Errore asteannunci {url}: {e}")
            continue
    
    return lotti

def tipologia_da_titolo(titolo):
    t = titolo.lower()
    if any(x in t for x in ["villa ", "villetta"]): return "Villa"
    if any(x in t for x in ["rustico", "cascina", "casolare", "casale"]): return "Rustico"
    if any(x in t for x in ["trilocale", "3 local", "tre vani"]): return "Trilocale"
    if any(x in t for x in ["bilocale", "2 local", "monolocale"]): return "Bilocale"
    if any(x in t for x in ["box", "garage", "posto auto", "autorimessa", "stalla", "rimessa"]): return "Box/Garage"
    if any(x in t for x in ["negozio", "ufficio", "capannone", "opificio", "commerciale", "bottega"]): return "Commerciale"
    if any(x in t for x in ["terreno", "area", "suolo"]): return "Terreno"
    return "Appartamento"

def arricchisci(lotto, idx):
    titolo = lotto.get("titolo", "")
    tipologia = tipologia_da_titolo(titolo)
    prezzo = lotto.get("prezzoBase", 0)
    stimato = lotto.get("valoreStimato", 0)
    if stimato == 0 and prezzo > 0:
        stimato = int(prezzo * 1.4)
    sconto = round((stimato - prezzo) / stimato * 100) if stimato > 0 and prezzo > 0 else 0
    return {
        "id": idx+1, "tipologia": tipologia,
        "titolo": titolo or "Immobile residenziale",
        "zona": lotto.get("zona", ""),
        "prezzoBase": prezzo, "valoreStimato": stimato, "sconto": sconto,
        "mq": lotto.get("mq", 0) or 0,
        "dataAsta": lotto.get("dataAsta", ""),
        "tribunale": lotto.get("tribunale", ""),
        "url": lotto.get("url", ""),
        "fonte": lotto.get("fonte", ""),
        "descrizione": titolo or "Immobile all'asta giudiziaria."
    }

def punteggio(lotto, modalita):
    score = 0; note = []
    txt = (lotto["titolo"] + " " + lotto["zona"] + " " + lotto["tipologia"]).lower()
    
    if lotto["sconto"] >= 45: score += 30; note.append("Sconto >45%")
    elif lotto["sconto"] >= 30: score += 20; note.append("Sconto 30-45%")
    elif lotto["sconto"] >= 15: score += 10; note.append("Sconto 15-30%")

    if lotto["tipologia"] in ["Appartamento","Trilocale","Bilocale"]: score += 12; note.append("Residenziale")
    if lotto["tipologia"] in ["Villa","Rustico"]:
        score += 20 if modalita != "Flipping" else 8; note.append("Potenziale B&B")
    if lotto["tipologia"] in ["Box/Garage","Commerciale","Terreno"]: score -= 20; note.append("Non residenziale")

    for z in ["centro storico","città alta","centro","lago","mare","lungomare","collina","montagna"]:
        if z in txt: score += 20 if modalita != "Flipping" else 10; note.append(f"Zona {z}"); break

    if 0 < lotto["prezzoBase"] < 50000: score += 20; note.append("Prezzo base basso")
    elif lotto["prezzoBase"] < 100000: score += 12; note.append("Prezzo competitivo")
    elif lotto["prezzoBase"] < 200000: score += 5
    elif lotto["prezzoBase"] > 400000: score -= 8; note.append("Budget elevato")

    if any(x in txt for x in ["ristruttur","rivedere","interventi","ripristino"]):
        if modalita != "B&B / Affitto Breve": score += 12; note.append("Margine ristrutturazione")

    return max(0, min(100, score)), note

@app.route("/aste")
def get_aste():
    provincia = request.args.get("provincia", "BG").upper()
    modalita = request.args.get("modalita", "Entrambi")
    
    lotti_raw = scrape_asteannunci(provincia)
    
    lotti = []
    for i, l in enumerate(lotti_raw):
        a = arricchisci(l, i)
        score, note = punteggio(a, modalita)
        a["score"] = score; a["noteScore"] = note
        lotti.append(a)
    
    lotti.sort(key=lambda x: x["score"], reverse=True)
    
    return jsonify({
        "provincia": provincia, "modalita": modalita,
        "totale": len(lotti),
        "aggiornato": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "lotti": lotti, "fonte": "asteannunci.it"
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
