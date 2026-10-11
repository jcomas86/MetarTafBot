import html
from datetime import datetime, timezone

LIMITE_TELEGRAM = 4000  # el máximo real es 4096; dejamos margen

EMOJI_CATEGORIA = {"VFR": "🟢", "MVFR": "🔵", "IFR": "🔴", "LIFR": "🟣"}


def _hora_utc(timestamp):
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%d/%m %H:%MZ")


def formatear_estacion(icao, metar, taf):
    nombre = (metar or {}).get("name") or (taf or {}).get("name") or ""
    cabecera = f"✈️ <b>{icao}</b>"
    if nombre:
        cabecera += f" — {html.escape(nombre)}"
    categoria = (metar or {}).get("fltCat")
    if categoria:
        cabecera += f"  {EMOJI_CATEGORIA.get(categoria, '')} {categoria}"

    lineas = [cabecera]
    if metar:
        lineas.append(f"<b>METAR</b> ({_hora_utc(metar.get('obsTime'))})")
        lineas.append(f"<pre>{html.escape(metar.get('rawOb', ''))}</pre>")
    else:
        lineas.append("<i>Sin METAR disponible</i>")
    if taf:
        lineas.append(f"<b>TAF</b> ({_hora_utc(taf.get('issueTime'))})")
        lineas.append(f"<pre>{html.escape(taf.get('rawTAF', ''))}</pre>")
    else:
        lineas.append("<i>Sin TAF disponible</i>")
    return "\n".join(lineas)


def agrupar_en_mensajes(bloques, limite=LIMITE_TELEGRAM):
    """Une los bloques de cada estación en el menor número de mensajes posible."""
    mensajes, actual = [], ""
    for bloque in bloques:
        if len(bloque) > limite:
            # Caso extremo (TAF enorme): se recorta antes de cerrar el <pre>
            bloque = bloque[: limite - 20] + "…</pre>"
        candidato = f"{actual}\n\n{bloque}" if actual else bloque
        if len(candidato) > limite:
            mensajes.append(actual)
            actual = bloque
        else:
            actual = candidato
    if actual:
        mensajes.append(actual)
    return mensajes
