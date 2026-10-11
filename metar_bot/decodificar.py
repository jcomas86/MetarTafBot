"""
Traduce a español legible los campos (ya decodificados) que devuelve la API
de aviationweather.gov en formato JSON.

Notas sobre la API (comprobado con respuestas reales):
  - visib viene en millas terrestres: número, "6+", "10+" o "" (sin dato)
  - wdir es un número de grados o "VRB"
  - clouds = [{cover, base (pies), type}] ; cover puede ser NSC/CAVOK/CLR...
  - la variación de dirección del viento (p.ej. 140V260) solo está en rawOb
"""

import math
import re
from datetime import datetime, timezone

RUMBOS = [
    "norte", "norte-noreste", "noreste", "este-noreste",
    "este", "este-sureste", "sureste", "sur-sureste",
    "sur", "sur-suroeste", "suroeste", "oeste-suroeste",
    "oeste", "oeste-noroeste", "noroeste", "norte-noroeste",
]

COBERTURA = {
    "FEW": "pocas nubes",
    "SCT": "nubes dispersas",
    "BKN": "nuboso",
    "OVC": "cubierto",
    "VV": "cielo oculto, visibilidad vertical",
}
SIN_NUBES = {
    "CAVOK": "sin nubes por debajo de 1500 m y sin cumulonimbus",
    "NSC": "sin nubes significativas",
    "NCD": "sin nubes detectadas",
    "CLR": "cielo despejado",
    "SKC": "cielo despejado",
}
TIPO_NUBE = {"CB": "cumulonimbus", "TCU": "cúmulos de gran desarrollo"}

CATEGORIA = {
    "VFR": ("🟢", "condiciones visuales"),
    "MVFR": ("🔵", "visuales marginales"),
    "IFR": ("🔴", "instrumentales"),
    "LIFR": ("🟣", "instrumentales bajas"),
}

FENOMENO = {
    "DZ": "llovizna", "RA": "lluvia", "SN": "nieve", "SG": "cinarra",
    "IC": "cristales de hielo", "PL": "hielo granulado", "GR": "granizo",
    "GS": "granizo pequeño", "UP": "precipitación desconocida",
    "BR": "neblina", "FG": "niebla", "FU": "humo", "VA": "ceniza volcánica",
    "DU": "polvo", "SA": "arena", "HZ": "calima", "PY": "rocío pulverizado",
    "PO": "remolinos de polvo", "SQ": "turbonada", "FC": "tromba",
    "SS": "tempestad de arena", "DS": "tempestad de polvo",
}
DESCRIPTOR = {"MI", "BC", "PR", "DR", "BL", "SH", "TS", "FZ"}
PATRON_FENOMENO = re.compile(r"^(?P<int>[-+]|VC)?(?P<desc>MI|BC|PR|DR|BL|SH|TS|FZ)?(?P<fen>(?:[A-Z]{2})*)$")
PATRON_VARIACION = re.compile(r"\s(\d{3})V(\d{3})\s")

KT_A_KMH = 1.852
MILLA_A_KM = 1.609
PIE_A_M = 0.3048


def _num(valor):
    """Convierte a float lo que parezca un número; None si no hay dato."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def rumbo(grados):
    return RUMBOS[round(grados / 22.5) % 16]


def viento(wdir, wspd, wgst=None, raw=""):
    velocidad = _num(wspd)
    if velocidad is None:
        return None
    if velocidad == 0:
        return "en calma"
    texto = f"{velocidad:.0f} kt ({velocidad * KT_A_KMH:.0f} km/h)"
    grados = _num(wdir)
    if grados is None:
        texto += " con dirección variable"
    else:
        texto += f" del {rumbo(grados)}"
    rachas = _num(wgst)
    if rachas:
        texto += f", rachas de {rachas:.0f} kt ({rachas * KT_A_KMH:.0f} km/h)"
    variacion = PATRON_VARIACION.search(f" {raw} ")
    if variacion:
        texto += f", variando entre {rumbo(int(variacion.group(1)))} y {rumbo(int(variacion.group(2)))}"
    return texto


def visibilidad(visib, cavok=False):
    if cavok:
        return "10 km o más"
    if visib is None or visib == "":
        return None
    texto = str(visib)
    millas = _num(texto.rstrip("+"))
    if millas is None:
        return texto
    km = millas * MILLA_A_KM
    if texto.endswith("+") or km >= 9.5:
        return "10 km o más"
    if km >= 5:
        return f"{km:.0f} km"
    return f"{round(km * 10) * 100:.0f} m"


def _altura(pies):
    return f"{round(pies * PIE_A_M / 10) * 10:.0f} m ({pies:.0f} ft)"


def nubes(clouds, cover=None, vert_vis=None):
    """Lista de capas en texto. Devuelve None si no hay información."""
    if cover in SIN_NUBES and not clouds:
        return SIN_NUBES[cover]
    capas = []
    for capa in clouds or []:
        tipo = (capa.get("cover") or "").upper()
        base = _num(capa.get("base"))
        if tipo in SIN_NUBES:
            capas.append(SIN_NUBES[tipo])
            continue
        texto = COBERTURA.get(tipo, tipo.lower())
        if base is not None:
            texto += f" a {_altura(base)}"
        if capa.get("type") in TIPO_NUBE:
            texto += f" ({TIPO_NUBE[capa['type']]})"
        capas.append(texto)
    if _num(vert_vis) is not None:
        capas.append(f"cielo oculto, visibilidad vertical {_altura(_num(vert_vis) * 100)}")
    return ", ".join(capas) if capas else None


def _un_fenomeno(codigo):
    m = PATRON_FENOMENO.match(codigo)
    if not m or not m.group("fen") and not m.group("desc"):
        return codigo
    fen = m.group("fen")
    nombres = [FENOMENO.get(fen[i:i + 2], fen[i:i + 2]) for i in range(0, len(fen), 2)]
    lista = " y ".join(nombres)
    desc = m.group("desc")
    if desc == "SH":
        texto = f"chubascos de {lista}" if lista else "chubascos"
    elif desc == "TS":
        texto = f"tormenta con {lista}" if lista else "tormenta"
    elif desc == "FZ":
        texto = f"{lista} engelante"
    elif desc in ("MI", "BC", "PR"):
        texto = f"{lista} {dict(MI='baja', BC='en bancos', PR='parcial')[desc]}"
    elif desc in ("DR", "BL"):
        texto = f"{lista} levantada por el viento"
    else:
        texto = lista
    intensidad = m.group("int")
    if intensidad == "-":
        texto += " débil"
    elif intensidad == "+":
        texto += " fuerte"
    elif intensidad == "VC":
        texto += " en las proximidades"
    return texto


def fenomenos(wx_string):
    if not wx_string:
        return None
    return ", ".join(_un_fenomeno(c) for c in str(wx_string).split())


def humedad(temp, dewp):
    t, td = _num(temp), _num(dewp)
    if t is None or td is None:
        return None
    def presion_vapor(x):
        return math.exp(17.625 * x / (243.04 + x))
    return round(100 * presion_vapor(td) / presion_vapor(t))


def coordenadas(lat, lon):
    lat, lon = _num(lat), _num(lon)
    if lat is None or lon is None:
        return None
    def gm(valor, ancho):
        grados = int(abs(valor))
        minutos = round((abs(valor) - grados) * 60)
        if minutos == 60:
            grados, minutos = grados + 1, 0
        return f"{grados:0{ancho}d}-{minutos:02d}"
    return f"{gm(lat, 2)}{'N' if lat >= 0 else 'S'} {gm(lon, 3)}{'E' if lon >= 0 else 'W'}"


def hora_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")


def dia_hora(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d a las %H:%M")


def hace(ts, ahora):
    minutos = int((ahora.timestamp() - ts) // 60)
    if minutos < 1:
        return "ahora mismo"
    if minutos < 60:
        return f"hace {minutos} min"
    horas, resto = divmod(minutos, 60)
    if horas < 48:
        return f"hace {horas} h {resto} min" if resto else f"hace {horas} h"
    return f"hace {horas // 24} días"


def rango(desde, hasta):
    """'11 15:00–18:00Z' si es el mismo día, '11 15:00Z → 12 06:00Z' si no."""
    a = datetime.fromtimestamp(desde, tz=timezone.utc)
    b = datetime.fromtimestamp(hasta, tz=timezone.utc)
    if a.date() == b.date():
        return f"día {a:%d} {a:%H:%M}–{b:%H:%M}Z"
    return f"día {a:%d} {a:%H:%M}Z → día {b:%d} {b:%H:%M}Z"


def nombre_corto(nombre):
    """'Madrid/Barajas Arpt, M, ES' -> 'Madrid/Barajas Arpt'"""
    return (nombre or "").split(",")[0].strip()
