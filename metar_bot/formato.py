import html
from datetime import datetime, timezone

from metar_bot import decodificar as d

LIMITE_TELEGRAM = 4000  # el máximo real es 4096; dejamos margen

CAMBIO_TAF = {
    "FM": "Desde",
    "BECMG": "Cambio gradual",
    "TEMPO": "Temporalmente",
    "PROB": "Posible",
}


def _cabecera(icao, metar, taf):
    datos = metar or taf or {}
    nombre = d.nombre_corto(datos.get("name"))
    texto = f"✈️ <b>{icao}</b>"
    if nombre:
        texto += f" — {html.escape(nombre)}"
    categoria = (metar or {}).get("fltCat")
    if categoria in d.CATEGORIA:
        emoji, explicacion = d.CATEGORIA[categoria]
        texto += f"\n{emoji} {categoria} ({explicacion})"
    situacion = [d.coordenadas(datos.get("lat"), datos.get("lon"))]
    if d._num(datos.get("elev")) is not None:
        situacion.append(f"{d._num(datos['elev']):.0f} m")
    situacion = [s for s in situacion if s]
    if situacion:
        texto += "\n📍 " + " · ".join(situacion)
    return texto


def _bloque_metar(metar, ahora):
    raw = metar.get("rawOb", "")
    cavok = metar.get("cover") == "CAVOK" or " CAVOK " in f" {raw} "
    lineas = [f"\n🔭 <b>OBSERVACIÓN</b> · {d.hora_utc(metar['obsTime'])} ({d.hace(metar['obsTime'], ahora)})"]

    viento = d.viento(metar.get("wdir"), metar.get("wspd"), metar.get("wgst"), raw)
    if viento:
        lineas.append(f"💨 Viento {viento}")

    clima = []
    if d._num(metar.get("temp")) is not None:
        clima.append(f"🌡️ {d._num(metar['temp']):.0f} °C")
    if d._num(metar.get("dewp")) is not None:
        clima.append(f"rocío {d._num(metar['dewp']):.0f} °C")
    humedad = d.humedad(metar.get("temp"), metar.get("dewp"))
    if humedad is not None:
        clima.append(f"💧 {humedad} %")
    if d._num(metar.get("altim")) is not None:
        clima.append(f"📊 {d._num(metar['altim']):.0f} hPa")
    if clima:
        lineas.append(" · ".join(clima))

    visibilidad = d.visibilidad(metar.get("visib"), cavok)
    if visibilidad:
        lineas.append(f"👁️ Visibilidad {visibilidad}")
    fenomenos = d.fenomenos(metar.get("wxString"))
    if fenomenos:
        lineas.append(f"🌧️ {fenomenos.capitalize()}")
    nubes = d.nubes(metar.get("clouds"), "CAVOK" if cavok else metar.get("cover"), metar.get("vertVis"))
    if nubes:
        lineas.append(f"☁️ {nubes.capitalize()}")

    lineas.append(f"<pre>{html.escape(raw)}</pre>")
    return lineas


def _periodo_taf(fcst, inicio_taf, fin_taf):
    cambio = fcst.get("fcstChange")
    desde = d._num(fcst.get("timeFrom")) or inicio_taf
    hasta = d._num(fcst.get("timeTo")) or fin_taf
    if cambio == "FM":
        titulo = f"Desde el {d.dia_hora(desde)}Z"
    elif cambio == "BECMG":
        fin_cambio = d._num(fcst.get("timeBec")) or hasta
        titulo = f"Cambio gradual {d.rango(desde, fin_cambio)}"
    elif cambio in ("TEMPO", "PROB"):
        titulo = f"{CAMBIO_TAF[cambio]} {d.rango(desde, hasta)}"
    else:
        titulo = "General"
    probabilidad = d._num(fcst.get("probability"))
    if probabilidad:
        titulo = f"Probabilidad {probabilidad:.0f} % · {titulo[0].lower()}{titulo[1:]}"

    partes = []
    viento = d.viento(fcst.get("wdir"), fcst.get("wspd"), fcst.get("wgst"))
    if viento:
        partes.append(f"viento {viento}")
    visibilidad = d.visibilidad(fcst.get("visib"))
    if visibilidad:
        partes.append(f"visibilidad {visibilidad}")
    fenomenos = d.fenomenos(fcst.get("wxString"))
    if fenomenos:
        partes.append(fenomenos)
    nubes = d.nubes(fcst.get("clouds"), vert_vis=fcst.get("vertVis"))
    if nubes:
        partes.append(nubes)
    detalle = "; ".join(partes) if partes else "sin cambios significativos"
    return f"▸ <b>{titulo}:</b> {detalle}"


def _temperaturas_taf(fcsts):
    textos = []
    for fcst in fcsts:
        for t in fcst.get("temp") or []:
            valor, cuando = d._num(t.get("surfaceTemp")), d._num(t.get("validTime"))
            if valor is None or cuando is None:
                continue
            tipo = "Máx" if t.get("maxOrMin") == "MAX" else "Mín"
            textos.append(f"{tipo} {valor:.0f} °C (día {d.dia_hora(cuando)}Z)")
    return "🌡️ " + " · ".join(textos) if textos else None


def _bloque_taf(taf, ahora):
    emitido = taf["issueTime"]
    lineas = [f"\n📅 <b>PRONÓSTICO</b> · emitido {d.hora_utc(emitido)} ({d.hace(emitido, ahora)})"]
    inicio, fin = d._num(taf.get("validTimeFrom")), d._num(taf.get("validTimeTo"))
    if inicio and fin:
        lineas.append(f"Válido del {d.dia_hora(inicio)} al {d.dia_hora(fin)} UTC")
    fcsts = taf.get("fcsts") or []
    for fcst in fcsts:
        lineas.append(_periodo_taf(fcst, inicio, fin))
    temperaturas = _temperaturas_taf(fcsts)
    if temperaturas:
        lineas.append(temperaturas)
    lineas.append(f"<pre>{html.escape(taf.get('rawTAF', ''))}</pre>")
    return lineas


def formatear_estacion(icao, metar, taf, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    lineas = [_cabecera(icao, metar, taf)]
    lineas += _bloque_metar(metar, ahora) if metar else ["\n<i>Sin METAR disponible</i>"]
    lineas += _bloque_taf(taf, ahora) if taf else ["\n<i>Sin TAF disponible</i>"]
    return "\n".join(lineas)


def agrupar_en_mensajes(bloques, limite=LIMITE_TELEGRAM):
    """Une los bloques de cada estación en el menor número de mensajes posible."""
    mensajes, actual = [], ""
    for bloque in bloques:
        if len(bloque) > limite:
            # Caso extremo (TAF enorme): se recorta antes de cerrar el <pre>
            bloque = bloque[: limite - 20] + "…</pre>"
        candidato = f"{actual}\n\n➖➖➖➖➖\n\n{bloque}" if actual else bloque
        if len(candidato) > limite:
            mensajes.append(actual)
            actual = bloque
        else:
            actual = candidato
    if actual:
        mensajes.append(actual)
    return mensajes
