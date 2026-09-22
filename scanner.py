import os
import re
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.txt"

# Ziel-URLs für UCI Luxe East Side Gallery
URLS = [
    "https://www.uci-kinowelt.de/film/die-odyssee/407923/berlin-east-side-gallery",
    "https://www.uci-kinowelt.de/kinoprogramm/berlin-east-side-gallery"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
}

def send_telegram(message: str):
    if not TOKEN or not CHAT_ID:
        print("Telegram Secrets fehlen!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(url, json=payload, timeout=15)
    print(f"Telegram Status: {res.status_code}")

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
    seen = load_seen()
    found_any = False

    for target_url in URLS:
        try:
            resp = requests.get(target_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                continue

            content = resp.text
            soup = BeautifulSoup(content, "html.parser")
            text_lower = soup.get_text().lower()

            # Prüfen, ob Odyssee überhaupt auf der Seite vorkommt
            if "odyssee" not in text_lower:
                continue

            # Wir suchen nach Abschnitten/Links mit OV / IMAX
            # RegEx sucht nach Mustern wie Datum + Uhrzeit + OV (z.B. "24. Sep ... 14:00 OV")
            has_imax = "imax" in text_lower
            has_ov = "ov" in text_lower or "originalversion" in text_lower

            if has_imax and has_ov:
                # Extrahiere Spielzeiten / Fundstellen
                matches = re.findall(r'(\d{1,2}\.\s*[A-Za-z]{3}[^\n\r<]{0,80}(?:OV|IMAX)[^\n\r<]{0,80})', content, re.IGNORECASE)
                
                details = []
                for m in matches:
                    clean = " ".join(m.split())
                    if "OV" in clean.upper():
                        details.append(clean)

                event_id = f"odyssee_imax_ov_{len(details)}"
                
                if event_id not in seen:
                    seen.add(event_id)
                    found_any = True

                    sample_times = "\n".join(f"• {d}" for d in details[:5]) if details else "Vorstellungen online gelistet!"
                    msg = (
                        "🚨 <b>IMAX OV TICKETS GEFUNDEN!</b> 🚨\n\n"
                        "<b>Film:</b> Die Odyssee\n"
                        "<b>Kino:</b> UCI Luxe Berlin - East Side Gallery\n"
                        "<b>Format:</b> IMAX (OV)\n\n"
                        f"<b>Termine:</b>\n{sample_times}\n\n"
                        f"👉 <a href='{target_url}'>Hier direkt Tickets auswählen & buchen</a>"
                    )
                    send_telegram(msg)
                    break

        except Exception as e:
            print(f"Fehler bei {target_url}: {e}")

    if found_any:
        save_seen(seen)

if __name__ == "__main__":
    check()