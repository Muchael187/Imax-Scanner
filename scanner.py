import os
import re
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.txt"

TARGET_URL = "https://www.uci-kinowelt.de/film/die-odyssee/407923/berlin-east-side-gallery"

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
    print(f"📡 Telegram API Status: HTTP {res.status_code}")
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

def fetch_page() -> str:
    # 1. Versuch: Chrome-Browser Impersonation (umgeht TLS-Fingerprint-Blocks)
    print(f"🌐 Rufe UCI über Chrome-Impersonation ab: {TARGET_URL}")
    try:
        r = cffi_requests.get(
            TARGET_URL,
            impersonate="chrome124",
            headers={"Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8"},
            timeout=25
        )
        print(f"ℹ️ Status Methode 1: HTTP {r.status_code}")
        if r.status_code == 200 and "odyssee" in r.text.lower():
            return r.text
    except Exception as e:
        print(f"Methode 1 Fehler: {e}")

    # 2. Versuch: Backup-Proxy (umgeht Cloudflare-IP-Sperren)
    proxy_url = f"https://r.jina.ai/{TARGET_URL}"
    print(f"🌐 Methode 2 (Bypass Reader): {proxy_url}")
    try:
        r = requests.get(proxy_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        print(f"ℹ️ Status Methode 2: HTTP {r.status_code}")
        if r.status_code == 200 and "odyssee" in r.text.lower():
            return r.text
    except Exception as e:
        print(f"Methode 2 Fehler: {e}")

    return ""

def check():
    raw_content = fetch_page()
    if not raw_content:
        print("❌ Konnte Seite über keine der Methoden laden.")
        return

    seen = load_seen()
    
    # Text bereinigen
    soup = BeautifulSoup(raw_content, "html.parser")
    clean_text = " ".join(soup.get_text(separator=" ").split())

    # Nach Tagen und Vorstellungen suchen
    day_chunks = re.split(r'(?=(?:Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{1,2}\.\s+[A-Za-z]{3,4}\.?)', clean_text)
    
    found_shows = []
    for chunk in day_chunks:
        date_match = re.match(r'^((?:Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{1,2}\.\s+[A-Za-z]{3,4}\.?)', chunk)
        if not date_match:
            continue
        date_str = date_match.group(1)

        times = re.findall(r'(\d{1,2}:\d{2}\s*(?:OV|OmU))', chunk, re.IGNORECASE)
        for t in times:
            entry = f"{date_str}: {t.upper()}"
            if entry not in found_shows:
                found_shows.append(entry)

    print(f"📊 Gefundene Vorstellungen ({len(found_shows)}):")
    for s in found_shows:
        print(f"   -> {s}")

    # Prüfen, welche Vorstellungen neu sind
    new_shows = [s for s in found_shows if s not in seen]

    if new_shows:
        print(f"🚀 {len(new_shows)} Vorstellungen gefunden! Sende Telegram-Benachrichtigung...")
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

        if send_telegram("\n".join(msg_parts)):
            for s in new_shows:
                seen.add(s)
            save_seen(seen)
            print("✅ Benachrichtigung gesendet und gespeichert.")
    else:
        print("ℹ️ Keine neuen Vorstellungen gefunden.")

if __name__ == "__main__":
    check()
