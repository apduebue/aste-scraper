from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
import re

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9",
    "Referer": "https://pvp.giustizia.it/",
}

PROVINCE_TRIBUNALI = {
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

def cerca_pvp_api(provincia):
    lotti = []
    endpoints = [
        f"https://pvp.giustizia.it/pvp/it/list_full.wp?facets=lotto_tipo%3AIMMOBILE_RESIDENZIALE%7Cprovincia_sigla%3A{provincia}&start=0&rows=30&wt=json",
        f"https://pvp.giustizia.it/pvp/api/aste?provincia={provincia}&tipologia=IMMOBILE_RESIDENZIALE&rows=30",
        f"https://pvp.giustizia.it/pvp/it/ricerca.wp?query=&provincia={provincia}&tipo_bene=IMMOBILE_RESIDENZIALE&rows=30&wt=json",
    ]
    nome_provincia = PROVINCE_TRIBUNALI.get(provincia, provincia)
    for url in endpoints:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    items = (data.get("response", {}).get("docs", []) or
                            data.get("aste", []) or data.get("lotti", []) or
                            data.get("items", []) or data.get("results", []))
                    if items:
                        for item in items[:25]:
                            lotti.append({
                                "titolo": item.get("lotto_desc") or item.get("descrizione") or item.get("titolo") or "Immobile residenziale",
                                "zona": item.get("comune_desc") or item.get("comune") or nome_provincia,
                                "prezzoBase": int(float(item.get("prezzo_base") or item.get("prezzoBase") or 0)),
                                "valoreStimato": int(float(item.get("valore_stima") or item.get("valoreStimato") or 0)),
                                "mq": int(float(item.get("superficie") or item.get("mq") or 0)),
                                "dataAsta": str(item.get("data_vendita") or item.get("dataAsta") or ""),
                                "tribunale": item.get("tribunale_desc") or item.get("tribunale") or nome_provincia,
                                "url": f"https://pvp.giustizia.it/pvp/it/detail_asta.wp?asta={item.get('asta_id') or item.get('id') or ''}",
                                "fonte": "pvp.giustizia.it"
                            })
                        if lotti: break
                except: pass
        except: continue
    return lotti

def tipologia_da_titolo(titolo):
    t = titolo.lower()
    if any(x in t for x in ["villa ", "villetta"]): return "Villa"
    if any(x in t for x in ["rustico", "cascina", "casolare", "casale"]): return "Rustico"
    if any(x in t for x in ["trilocale", "3 local"]): return "Trilocale"
    if any(x in t for x in ["bilocale", "2 local", "monolocale"]): return "Bilocale"
    if any(x in t for x in ["box", "garage", "posto auto"]): return "Box/Garage"
    if any(x in t for x in ["negozio", "ufficio", "capannone", "opificio"]): return "Commerciale"
    return "Appartamento"

def arricchisci(lotto, idx):
    titolo = lotto.get("titolo", "")
    tipologia = tipologia_da_titolo(titolo)
    prezzo = lotto.get("prezzoBase", 0)
    stimato = lotto.get("valoreStimato", 0)
    if stimato == 0 and prezzo > 0: stimato = int(prezzo * 1.4)
    sconto = round((stimato - prezzo) / stimato * 100) if stimato > 0 and prezzo > 0 else 0
    return {
        "id": idx+1, "tipologia": tipologia, "titolo": titolo or "Immobile residenziale",
        "zona": lotto.get("zona",""), "prezzoBase": prezzo, "valoreStimato": stimato,
        "sconto": sconto, "mq": lotto.get("mq",0) or 0, "dataAsta": lotto.get("dataAsta",""),
        "tribunale": lotto.get("tribunale",""), "url": lotto.get("url",""),
        "fonte": lotto.get("fonte",""), "descrizione": titolo or "Immobile all'asta giudiziaria."
    }

def punteggio(lotto, modalita):
    score = 0; note = []
    txt = (lotto["titolo"]+" "+lotto["zona"]+" "+lotto["tipologia"]).lower()
    if lotto["sconto"] >= 45: score+=30; note.append("Sconto >45%")
    elif lotto["sconto"] >= 30: score+=20; note.append("Sconto 30-45%")
    elif lotto["sconto"] >= 15: score+=10; note.append("Sconto 15-30%")
    if lotto["tipologia"] in ["Appartamento","Trilocale","Bilocale"]: score+=12; note.append("Residenziale")
    if lotto["tipologia"] in ["Villa","Rustico"]:
        score += 20 if modalita!="Flipping" else 8; note.append("Potenziale B&B")
    if lotto["tipologia"] in ["Box/Garage","Commerciale"]: score-=25; note.append("Non residenziale")
    for z in ["centro storico","città alta","centro","lago","mare","lungomare","collina"]:
        if z in txt: score+=20 if modalita!="Flipping" else 10; note.append(f"Zona {z}"); break
    if 0 < lotto["prezzoBase"] < 50000: score+=20; note.append("Prezzo base basso")
    elif lotto["prezzoBase"] < 100000: score+=12; note.append("Prezzo competitivo")
    elif lotto["prezzoBase"] > 400000: score-=8; note.append("Budget elevato")
    if any(x in txt for x in ["ristruttur","rivedere","interventi"]):
        if modalita!="B&B / Affitto Breve": score+=12; note.append("Margine ristrutturazione")
    return max(0,min(100,score)), note

@app.route("/aste")
def get_aste():
    provincia = request.args.get("provincia","BG").upper()
    modalita = request.args.get("modalita","Entrambi")
    lotti_raw = cerca_pvp_api(provincia)
    lotti = []
    for i,l in enumerate(lotti_raw):
        a = arricchisci(l,i); score,note = punteggio(a,modalita)
        a["score"]=score; a["noteScore"]=note; lotti.append(a)
    lotti.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"provincia":provincia,"modalita":modalita,"totale":len(lotti),
                    "aggiornato":datetime.now().strftime("%d/%m/%Y %H:%M"),"lotti":lotti})

@app.route("/health")
def health():
    return jsonify({"status":"ok","time":datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
