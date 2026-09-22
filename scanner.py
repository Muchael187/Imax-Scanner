import os
import re
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.txt"

# Exakte URLs inklusive Kino-ID 82 (East Side Gallery)
URLS = [
    "https://www.uci-kinowelt.de/film/die-odyssee/407923/berlin-east-side-gallery/82",
    "https://app.uci-kinowelt.de/kinoprogramm/berlin-east-side-gallery/82/list?version=imax"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8"
}

def send_telegram(message: str):
    if not TOKEN or not CHAT_ID:
        print("❌ FEHLER: Telegram Secrets (TOKEN oder CHAT_ID) fehlen!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(url, json=payload, timeout=15)
    print(f"📡 Telegram API Antwort: HTTP {res.status_code} - {res.text}")

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in sorted(seen):
            f.write(f"{item}\n")

def check():
    print("🔍 Starte Suche nach Odyssee IMAX Tickets...")
    seen = load_seen()
    found_shows = []
    direct_link = URLS[0]

    for target_url in URLS:
        try:
            print(f"🌐 Rufe ab: {target_url}")
            resp = requests.get(target_url, headers=HEADERS, timeout=20)
            print(f"ℹ️ Status Code: {resp.status_code}")

            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            page_text = soup.get_text(separator=" ")
            
            # Prüfen, ob der Film erwähnt wird
            if "odyssee" not in page_text.lower():
                print("ℹ️ 'Odyssee' auf dieser Seite nicht im Text gefunden.")
                continue

            # Suche nach Terminen mit Uhrzeit + OV oder OmU
            # Erfasst Muster wie "24. Sep. 14:00 OV" oder "Heute 14:00 OmU"
            matches = re.findall(
                r'((?:Mo|Di|Mi|Do|Fr|Sa|So|\d{1,2}\.)[^\n\r]{0,35}\b\d{1,2}:\d{2}\b[^\n\r]{0,15}\b(?:OV|OmU)\b)',
                page_text,
                re.IGNORECASE
            )

            for m in matches:
                cleaned = " ".join(m.split())
                if cleaned not in found_shows:
                    found_shows.append(cleaned)

            if found_shows:
                direct_link = target_url
                break

        except Exception as e:
            print(f"❌ Fehler bei Anfrage: {e}")

    print(f"📊 Gefundene Vorstellungen: {len(found_shows)}")
    for s in found_shows:
        print(f"   -> {s}")

    if found_shows:
        # Erstelle eine eindeutige Kennung aller Termine
        signature = "_".join(sorted(found_shows))
        
        if signature not in seen:
            print("🚀 Neue Vorstellungen entdeckt! Sende Telegram-Alert...")
            termin_liste = "\n".join(f"• <b>{show}</b>" for show in found_shows[:8])
            
            msg = (
                "🚨 <b>IMAX TICKETS GEFUNDEN!</b> 🚨\n\n"
                "<b>Film:</b> Die Odyssee\n"
                "<b>Kino:</b> UCI Luxe Berlin - East Side Gallery\n"
                "<b>Format:</b> IMAX (OV / OmU)\n\n"
                f"<b>Verfügbare Termine:</b>\n{termin_liste}\n\n"
                f"👉 <a href='{direct_link}'>Jetzt Plätze auswählen & buchen</a>"
            )
            send_telegram(msg)
            seen.add(signature)
            save_seen(seen)
        else:
            print("ℹ️ Diese Vorstellungen wurden dir bereits gemeldet.")
    else:
        print("⚠️ Keine passenden OV/OmU-Termine im HTML gefunden.")

if __name__ == "__main__":
    check()
