import os
import re
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.txt"

TARGET_URL = "https://www.uci-kinowelt.de/film/die-odyssee/407923/berlin-east-side-gallery"

MONTHS = ["jan", "feb", "mär", "mae", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "dez"]
WEEKDAYS = ["mo", "di", "mi", "do", "fr", "sa", "so"]

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
    # 1. Direkter Aufruf über TLS-Fingerprint
    print(f"🌐 Rufe Seite ab: {TARGET_URL}")
    try:
        r = cffi_requests.get(
            TARGET_URL,
            impersonate="chrome124",
            headers={"Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8"},
            timeout=25
        )
        if r.status_code == 200 and "odyssee" in r.text.lower():
            return r.text
    except Exception as e:
        print(f"Methode 1 Fehler: {e}")

    # 2. Cloudflare-Bypass Proxy
    proxy_url = f"https://r.jina.ai/{TARGET_URL}"
    print(f"🌐 Nutze Proxy-Reader: {proxy_url}")
    try:
        r = requests.get(proxy_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        if r.status_code == 200 and "odyssee" in r.text.lower():
            return r.text
    except Exception as e:
        print(f"Methode 2 Fehler: {e}")

    return ""

def parse_screenings(raw_text: str):
    # Markdown-Links und Sonderzeichen bereinigen
    clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', raw_text)
    clean = re.sub(r'[*#_]', ' ', clean)
    tokens = clean.split()

    shows = []
    current_day = "Unbekanntes Datum"
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        tok_lower = tok.lower().rstrip(".")

        # 1. Wochentag + Tag + Monat erkennen (z.B. "Mi" "23." "Sep")
        if tok_lower in WEEKDAYS and i + 2 < len(tokens):
            day_num = tokens[i+1]
            month_tok = tokens[i+2].lower().rstrip(".")
            if re.match(r'^\d{1,2}\.?$', day_num) and month_tok in MONTHS:
                current_day = f"{tok} {day_num.rstrip('.')}. {tokens[i+2].rstrip('.')}"
                i += 3
                continue

        # 2. Tag + Monat ohne Wochentag erkennen (z.B. "22." "Sep")
        if re.match(r'^\d{1,2}\.?$', tok) and i + 1 < len(tokens):
            month_tok = tokens[i+1].lower().rstrip(".")
            if month_tok in MONTHS:
                current_day = f"{tok.rstrip('.')}. {tokens[i+1].rstrip('.')}"
                i += 2
                continue

        # 3. Uhrzeit gefolgt von OV oder OmU / OmeU erkennen
        if re.match(r'^\d{1,2}:\d{2}$', tok) and i + 1 < len(tokens):
            version_cand = tokens[i+1].upper().rstrip(",.;:()")
            if version_cand in ["OV", "OMU", "OMEU"]:
                version = "OV" if version_cand == "OV" else ("OmU" if version_cand == "OMU" else "OmeU")
                entry = f"{current_day} um {tok} Uhr ({version})"
                if entry not in shows:
                    shows.append(entry)
                i += 2
                continue

        i += 1

    return shows

def check():
    raw_content = fetch_page()
    if not raw_content:
        print("❌ Konnte Seite nicht abrufen.")
        return

    seen = load_seen()
    found_shows = parse_screenings(raw_content)

    print(f"📊 Gefundene OV/OmU-Vorstellungen ({len(found_shows)}):")
    for s in found_shows:
        print(f"   -> {s}")

    new_shows = [s for s in found_shows if s not in seen]

    if new_shows:
        print(f"🚀 {len(new_shows)} neue Vorstellungen gefunden! Sende Telegram Nachricht...")

        ov_shows = [s for s in new_shows if "(OV)" in s]
        omu_shows = [s for s in new_shows if "(OmU)" in s or "(OmeU)" in s]

        msg_lines = [
            "🚨 <b>IMAX TICKETS LIVE!</b> 🚨\n",
            "🎬 <b>Film:</b> Die Odyssee",
            "📍 <b>Kino:</b> UCI Luxe East Side Gallery",
            "🎟 <b>Saal:</b> IMAX\n"
        ]

        if ov_shows:
            msg_lines.append("🇬🇧 <b>Originalversion (OV):</b>")
            for s in ov_shows:
                msg_lines.append(f"• <b>{s}</b>")
            msg_lines.append("")

        if omu_shows:
            msg_lines.append("💬 <b>OmU (Original mit Untertiteln):</b>")
            for s in omu_shows:
                msg_lines.append(f"• <b>{s}</b>")
            msg_lines.append("")

        msg_lines.append(f"👉 <a href='{TARGET_URL}'>Hier direkt buchen</a>")

        if send_telegram("\n".join(msg_lines)):
            for s in new_shows:
                seen.add(s)
            save_seen(seen)
            print("✅ Erfolgreich gemeldet und gespeichert.")
    else:
        print("ℹ️ Keine neuen Vorstellungen zum Melden vorhanden.")

if __name__ == "__main__":
    check()
