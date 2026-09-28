#!/usr/bin/env python3
"""Genera azoteros.ics a partir de la web de Canal Ocio y Deporte.

- Descubre partidos nuevos en la ficha del equipo (enlaces /matches/view/<id>).
- Recuerda los ya conocidos en state.json (la ficha solo enseña ~5 próximos).
- Relee cada partido para recoger cambios de fecha, hora o campo.
- Si la web falla o no se puede leer nada, sale con error y NO toca el .ics.
Solo usa la librería estándar de Python.
"""
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.ocioydeportecanal.es"
TEAM_URL = f"{BASE}/es/team/view/2127152-azoteros-fc"
TEAM_NAME = "AZOTEROS FC"
CAL_NAME = "Azoteros FC"
ADDRESS = "Avda. Filipinas esq. Pablo Iglesias, 28003 Madrid"
DURATION_MIN = 60

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
OUT = ROOT / "azoteros.ics"

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
UA = "Mozilla/5.0 (compatible; azoteros-calendario/1.0)"


class FetchError(Exception):
    pass


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # red, timeout...
            last = e
        time.sleep(3 * (i + 1))
    raise FetchError(f"{url}: {last}")


def plain_text(page):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def pretty(name):
    keep_upper = {"FC", "CF", "CD", "UD", "SAD", "AD", "4K"}
    small = {"de", "del", "la", "las", "los", "y"}
    out = []
    for i, w in enumerate(name.split()):
        if w.upper() in keep_upper:
            out.append(w.upper())
        elif i > 0 and w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def parse_match(mid, page):
    """Devuelve dict del partido o None si no es de Azoteros / no se entiende."""
    text = plain_text(page)

    teams = None
    m = re.search(r"api\.whatsapp\.com/send\?text=([^\"'&\s]+)", page)
    if m:
        share = urllib.parse.unquote(html.unescape(m.group(1)))
        share = share.split(" http")[0].strip()
        if " vs " in share:
            teams = [s.strip() for s in share.split(" vs ", 1)]
    if not teams:
        m = re.search(r"####\s*(.+?) vs (.+?)\s", text) or re.search(
            r"([A-Z0-9ÁÉÍÓÚÑ' .-]{3,}?) vs ([A-Z0-9ÁÉÍÓÚÑ' .-]{3,}?) Enviar", text)
        if m:
            teams = [m.group(1).strip(), m.group(2).strip()]
    if not teams or not any(TEAM_NAME in t.upper() for t in teams):
        return None
    home, away = teams

    m = re.search(
        r"(Canal Ocio y Deporte ?- ?[^,]+?), (\d{1,2}) ([A-Za-zé]+) (\d{4}) (\d{1,2}):(\d{2})",
        text, re.I)
    start = None
    venue = "Canal Ocio y Deporte"
    if m and m.group(3).lower() in MONTHS:
        venue = re.sub(r"\s*-\s*", " - ", m.group(1)).strip()
        start = dt.datetime(int(m.group(4)), MONTHS[m.group(3).lower()],
                            int(m.group(2)), int(m.group(5)), int(m.group(6)))

    jornada = re.search(r"Jornada (\d+)", text)
    grupo = re.search(r"Grupo ([A-Z])\b", text)
    comp = re.search(r"Competición (.{3,80}?) (?:Grupo|Jornada|Sede|Ronda|Fase de)", text)
    if comp and re.search(r"[{};=]", comp.group(1)):
        comp = None

    return {
        "id": mid,
        "home": pretty(home),
        "away": pretty(away),
        "start": start.strftime("%Y%m%dT%H%M%S") if start else None,
        "venue": venue.replace("PRINCIPAL", "Principal"),
        "jornada": jornada.group(1) if jornada else None,
        "grupo": grupo.group(1) if grupo else None,
        "competicion": comp.group(1).strip() if comp else None,
    }


def esc(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;")
             .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not parts else 74):
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def build_ics(matches, stamps):
    L = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//diegoversa//azoteros-calendario//ES",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CAL_NAME}", "X-WR-TIMEZONE:Europe/Madrid",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
        "BEGIN:VTIMEZONE", "TZID:Europe/Madrid",
        "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST",
        "DTSTART:19700329T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET",
        "DTSTART:19701025T030000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD", "END:VTIMEZONE",
    ]
    for mt in sorted(matches, key=lambda x: x["start"]):
        s = dt.datetime.strptime(mt["start"], "%Y%m%dT%H%M%S")
        e = s + dt.timedelta(minutes=DURATION_MIN)
        local = TEAM_NAME in mt["home"].upper()
        detail = ", ".join(x for x in [
            mt["competicion"],
            f"Jornada {mt['jornada']}" if mt["jornada"] else None,
            f"Grupo {mt['grupo']}" if mt["grupo"] else None,
            "local" if local else "visitante",
        ] if x)
        url = f"{BASE}/es/matches/view/{mt['id']}"
        L += [
            "BEGIN:VEVENT",
            f"UID:{mt['id']}@azoteros-calendario",
            f"DTSTAMP:{stamps[mt['id']]}",
            f"DTSTART;TZID=Europe/Madrid:{s:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Europe/Madrid:{e:%Y%m%dT%H%M%S}",
            f"SUMMARY:{esc('⚽ ' + mt['home'] + ' vs ' + mt['away'])}",
            f"LOCATION:{esc(mt['venue'] + ', ' + ADDRESS)}",
            f"DESCRIPTION:{esc(detail + chr(10) + url)}",
            f"URL:{url}",
            "BEGIN:VALARM", "ACTION:DISPLAY",
            "DESCRIPTION:Partido Azoteros FC", "TRIGGER:-PT2H", "END:VALARM",
            "END:VEVENT",
        ]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {"matches": {}}
    known = state.setdefault("matches", {})

    team_page = fetch(TEAM_URL)
    if not team_page or TEAM_NAME not in team_page.upper():
        raise SystemExit("No se pudo leer la ficha del equipo; no toco el calendario.")
    for mid in re.findall(r"/matches/view/(\d+)", team_page):
        known.setdefault(mid, {})

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    matches, stamps, dropped = [], {}, []
    for mid in sorted(known, key=int):
        page = fetch(f"{BASE}/es/matches/view/{mid}")
        if page is None:  # partido borrado en la web
            dropped.append(mid)
            continue
        mt = parse_match(mid, page)
        if mt is None:
            dropped.append(mid)
            continue
        if not mt["start"]:
            print(f"  {mid}: sin fecha todavía, lo mantengo en seguimiento")
            continue
        h = hashlib.sha1(json.dumps(mt, sort_keys=True).encode()).hexdigest()
        prev = known[mid]
        if prev.get("hash") != h:
            prev.update(hash=h, stamp=now)
            print(f"  {mid}: {'nuevo' if 'first' not in prev else 'cambiado'} -> "
                  f"{mt['home']} vs {mt['away']} {mt['start']}")
        prev.setdefault("first", now)
        stamps[mid] = prev["stamp"]
        matches.append(mt)
    for mid in dropped:
        print(f"  {mid}: ya no existe o no es de Azoteros, lo quito")
        known.pop(mid, None)

    if not matches:
        raise SystemExit("No he podido leer ningún partido; no toco el calendario.")

    OUT.write_bytes(build_ics(matches, stamps).encode("utf-8"))
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    print(f"OK: {len(matches)} partidos en {OUT.name}")


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        sys.exit(f"Error de red, no toco el calendario: {e}")
