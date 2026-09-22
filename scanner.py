import os
import re
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.txt"

# Deine exakte UCI-URL für Die Odyssee im East Side Gallery Luxe
TARGET_URL = "https://www.uci-kinowelt.de/film/die-odyssee/407923/berlin-east-side-gallery"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8"
}

def send_telegram(message: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print("❌ FEHLER: Telegram Secrets (TOKEN oder CHAT_ID) fehlen!")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(url, json=payload, timeout=15)
    print(f"📡 Telegram API Antwort: HTTP {res.status_code} - {res.text}")
    return res.status_code == 200

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
    print(f"🌐 Rufe ab: {TARGET_URL}")
    seen = load_seen()
    
    try:
        resp = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
        print(f"ℹ️ HTTP Status: {resp.status_code}")
        if resp.status_code != 200:
            print("❌ Konnte Seite nicht laden.")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        # Text normalisieren (alle mehrfachen Leerzeichen/Umbruch-Zeichen zu einfachen Leerzeichen)
        clean_text = " ".join(soup.get_text(separator=" ").split())

        if "odyssee" not in clean_text.lower():
            print("⚠️ 'Odyssee' nicht auf der Seite gefunden.")
            return

        # Den Text in Tages-Blöcke aufteilen (z. B. "Do 24. Sep ...")
        day_chunks = re.split(r'(?=(?:Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{1,2}\.\s+[A-Za-z]{3,4}\.?)', clean_text)
        
        found_shows = []
        for chunk in day_chunks:
            date_match = re.match(r'^((?:Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{1,2}\.\s+[A-Za-z]{3,4}\.?)', chunk)
            if not date_match:
                continue
            date_str = date_match.group(1)

            # Suche nach Uhrzeiten gefolgt von OV oder OmU
            times = re.findall(r'\b(\d{1,2}:\d{2}\s*(?:OV|OmU))\b', chunk, re.IGNORECASE)
            for t in times:
                entry = f"{date_str}: {t.upper()}"
                if entry not in found_shows:
                    found_shows.append(entry)

        print(f"📊 Gefundene Vorstellungen ({len(found_shows)}):")
        for s in found_shows:
            print(f"   -> {s}")

        # Neue Vorstellungen ermitteln, die noch nicht in seen.txt stehen
        new_shows = [s for s in found_shows if s not in seen]

        if new_shows:
            print(f"🚀 {len(new_shows)} neue Vorstellungen gefunden! Sende Telegram Nachricht...")
            
            # Trenne nach OV und OmU für beste Übersicht
            ov_shows = [s for s in new_shows if "OV" in s]
            omu_shows = [s for s in new_shows if "OMU" in s]

            msg_parts = [
                "🚨 <b>IMAX TICKETS GEFUNDEN!</b> 🚨\n",
                "🎬 <b>Film:</b> Die Odyssee",
                "📍 <b>Kino:</b> UCI Luxe Berlin - East Side Gallery",
                "🎟 <b>Saal:</b> IMAX\n"
            ]

            if ov_shows:
                msg_parts.append("🇬🇧 <b>Originalversion (OV):</b>")
                for s in ov_shows:
                    msg_parts.append(f"• <b>{s}</b>")
                msg_parts.append("")

            if omu_shows:
                msg_parts.append("💬 <b>OmU (Original mit Untertiteln):</b>")
                for s in omu_shows:
                    msg_parts.append(f"• {s}")
                msg_parts.append("")

            msg_parts.append(f"👉 <a href='{TARGET_URL}'>Hier direkt Tickets auswählen & buchen</a>")

            success = send_telegram("\n".join(msg_parts))
            if success:
                for s in new_shows:
                    seen.add(s)
                save_seen(seen)
                print("✅ Erfolgreich gemeldet und in seen.txt vermerkt.")
        else:
            print("ℹ️ Keine neuen Vorstellungen. Alle bekannten Termine wurden bereits gemeldet.")

    except Exception as e:
        print(f"❌ Fehler bei der Ausführung: {e}")

if __name__ == "__main__":
    check()
