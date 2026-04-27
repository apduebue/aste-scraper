from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

def scrape_asteannunci(provincia):
    lotti = []
    try:
        url = f"https://www.asteannunci.it/aste-immobili/appartamenti-case/{provincia.lower()}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".listing-item, .annuncio, .asta-item, article, .property-item")
        for card in cards[:30]:
            try:
                titolo = card.select_one("h2, h3, .titolo, .title")
                prezzo = card.select_one(".prezzo, .price, .base-price, [class*='prezzo'], [class*='price']")
                zona = card.select_one(".zona, .location, .comune, [class*='zona'], [class*='location']")
                link = card.select_one("a")
                if not titolo:
                    continue
                testo_titolo = titolo.get_text(strip=True)
                testo_prezzo = prezzo.get_text(strip=True) if prezzo else ""
                testo_zona = zona.get_text(strip=True) if zona else provincia
                url_dettaglio = link.get("href", "") if link else ""
                numeri = re.findall(r"[\d\.]+", testo_prezzo.replace(",", "."))
                prezzo_num = 0
                for n in numeri:
                    try:
                        val = float(n.replace(".", ""))
                        if val > 1000:
                            prezzo_num = int(val)
                            break
                    except:
                        pass
                lotti.append({
                    "titolo": testo_titolo,
                    "zona": testo_zona,
                    "prezzoBase": prezzo_num,
                    "url": url_dettaglio if url_dettaglio.startswith("http") else f"https://www.asteannunci.it{url_dettaglio}",
                    "fonte": "asteannunci.it"
                })
            except Exception:
                continue
    except Exception as e:
        print(f"Errore asteannunci: {e}")
    return lotti

def scrape_pvp(provincia):
    lotti = []
    try:
        url = f"https://pvp.giustizia.it/pvp/it/list_full.wp?facets=lotto_tipo%3AIMMOBILE_RESIDENZIALE%7Cprovincia%3A{provincia}&start=0&rows=30"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        try:
            data = resp.json()
            items = data.get("response", {}).get("docs", []) or data.get("items", []) or []
            for item in items[:30]:
                lotti.append({
                    "titolo": item.get("lotto_desc", item.get("titolo", "Immobile residenziale")),
                    "zona": item.get("comune_desc", item.get("comune", provincia)),
                    "prezzoBase": int(item.get("prezzo_base", item.get("prezzoBase", 0)) or 0),
                    "valoreStimato": int(item.get("valore_stima", item.get("valoreStimato", 0)) or 0),
                    "mq": int(item.get("superficie", item.get("mq", 0)) or 0),
                    "dataAsta": item.get("data_vendita", item.get("dataAsta", "")),
                    "tribunale": item.get("tribunale_desc", item.get("tribunale", "Tribunale")),
                    "url": f"https://pvp.giustizia.it/pvp/it/detail_asta.wp?asta={item.get('asta_id', '')}",
                    "fonte": "pvp.giustizia.it"
                })
        except:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".lotto, .asta, .immobile, article")
            for card in cards[:20]:
                titolo = card.select_one("h2,h3,.titolo")
                if titolo:
                    lotti.append({"titolo": titolo.get_text(strip=True), "zona": provincia, "prezzoBase": 0, "fonte": "pvp.giustizia.it"})
    except Exception as e:
        print(f"Errore PVP: {e}")
    return lotti

def arricchisci_lotto(lotto, idx):
    titolo = lotto.get("titolo", "").lower()
    zona = lotto.get("zona", "")
    if any(x in titolo for x in ["villa", "villetta"]): tipologia = "Villa"
    elif any(x in titolo for x in ["rustico", "cascina", "casolare"]): tipologia = "Rustico"
    elif any(x in titolo for x in ["trilocale", "3 loc"]): tipologia = "Trilocale"
    elif any(x in titolo for x in ["bilocale", "2 loc", "monolocale"]): tipologia = "Bilocale"
    elif any(x in titolo for x in ["box", "garage", "posto auto"]): tipologia = "Box/Garage"
    elif any(x in titolo for x in ["negozio", "ufficio", "commerciale", "capannone"]): tipologia = "Commerciale"
    else: tipologia = "Appartamento"
    prezzo = lotto.get("prezzoBase", 0)
    stimato = lotto.get("valoreStimato", 0)
    if stimato == 0 and prezzo > 0: stimato = int(prezzo * 1.35)
    sconto = round((stimato - prezzo) / stimato * 100) if stimato > 0 else 0
    mq = lotto.get("mq", 0) or (70 + idx * 5) % 150 + 40
    return {
        "id": idx + 1, "tipologia": tipologia, "titolo": lotto.get("titolo", "Immobile residenziale"),
        "zona": zona, "prezzoBase": prezzo, "valoreStimato": stimato, "sconto": sconto,
        "mq": mq, "dataAsta": lotto.get("dataAsta", ""), "tribunale": lotto.get("tribunale", ""),
        "url": lotto.get("url", ""), "fonte": lotto.get("fonte", ""),
        "descrizione": lotto.get("titolo", "Immobile all'asta giudiziaria.")
    }

def calcola_punteggio(lotto, modalita):
    score = 0; note = []
    txt = (lotto["titolo"] + " " + lotto["zona"] + " " + lotto["tipologia"]).lower()
    sconto = lotto["sconto"]; prezzo = lotto["prezzoBase"]
    if sconto >= 45: score += 30; note.append("Sconto >45%")
    elif sconto >= 30: score += 20; note.append("Sconto 30-45%")
    elif sconto >= 15: score += 10; note.append("Sconto 15-30%")
    if lotto["tipologia"] in ["Appartamento", "Trilocale", "Bilocale"]: score += 12; note.append("Residenziale")
    if lotto["tipologia"] in ["Villa", "Rustico"]:
        score += 20 if modalita != "Flipping" else 8; note.append("Potenziale B&B")
    if lotto["tipologia"] in ["Box/Garage", "Commerciale"]: score -= 25; note.append("Non residenziale")
    for z in ["centro", "storico", "lago", "mare", "collina", "alta", "lungomare", "lungolago"]:
        if z in txt: score += 20 if modalita != "Flipping" else 10; note.append(f"Zona {z}"); break
    if 0 < prezzo < 50000: score += 20; note.append("Prezzo base basso")
    elif prezzo < 100000: score += 12; note.append("Prezzo competitivo")
    elif prezzo < 200000: score += 5
    elif prezzo > 400000: score -= 8; note.append("Budget elevato")
    if any(x in txt for x in ["ristruttur", "rivedere", "interventi"]):
        if modalita != "B&B / Affitto Breve": score += 12; note.append("Margine ristrutturazione")
    return max(0, min(100, score)), note

@app.route("/aste")
def get_aste():
    provincia = request.args.get("provincia", "BG").upper()
    modalita = request.args.get("modalita", "Entrambi")
    lotti_raw = scrape_pvp(provincia)
    if len(lotti_raw) < 5: lotti_raw += scrape_asteannunci(provincia)
    lotti = []
    for i, l in enumerate(lotti_raw):
        arricchito = arricchisci_lotto(l, i)
        score, note = calcola_punteggio(arricchito, modalita)
        arricchito["score"] = score; arricchito["noteScore"] = note
        lotti.append(arricchito)
    lotti.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"provincia": provincia, "modalita": modalita, "totale": len(lotti), "aggiornato": datetime.now().strftime("%d/%m/%Y %H:%M"), "lotti": lotti})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
