"""
Cliente mínimo de la API pública de https://aviationweather.gov/data/api/

Se hace una sola petición por tipo (METAR / TAF) para todas las
estaciones, pasando los códigos OACI separados por comas.
"""

from datetime import datetime

import requests

API_BASE = "https://aviationweather.gov/api/data"
HEADERS = {"User-Agent": "MetarTafBot/1.0 (bot personal de Telegram)"}
TIMEOUT = 20


def _get_json(endpoint, ids):
    if not ids:
        return []
    resp = requests.get(
        f"{API_BASE}/{endpoint}",
        params={"ids": ",".join(ids), "format": "json"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    # 204 = sin datos para esas estaciones
    if resp.status_code == 204 or not resp.content.strip():
        return []
    resp.raise_for_status()
    return resp.json()


def a_timestamp(valor):
    """La API da unas horas como unix (int) y otras como texto ISO: lo pasamos todo a unix."""
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, str) and valor:
        try:
            return int(datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return 0
    return 0


def _ultimo_por_estacion(registros, campo_tiempo):
    """La API puede devolver varios registros por estación: nos quedamos con el más reciente."""
    resultado = {}
    for r in registros:
        r[campo_tiempo] = a_timestamp(r.get(campo_tiempo))
        icao = (r.get("icaoId") or "").upper()
        if not icao:
            continue
        actual = resultado.get(icao)
        if actual is None or (r.get(campo_tiempo) or 0) > (actual.get(campo_tiempo) or 0):
            resultado[icao] = r
    return resultado


def obtener_metars(ids):
    """Devuelve {icao: {icaoId, name, obsTime, rawOb, fltCat, ...}}"""
    return _ultimo_por_estacion(_get_json("metar", ids), "obsTime")


def obtener_tafs(ids):
    """Devuelve {icao: {icaoId, name, issueTime, rawTAF, ...}}"""
    return _ultimo_por_estacion(_get_json("taf", ids), "issueTime")


def validar_estaciones(ids):
    """Devuelve {icao: nombre} de las estaciones que existen."""
    datos = _get_json("stationinfo", ids)
    return {
        (d.get("icaoId") or "").upper(): d.get("site") or d.get("name") or ""
        for d in datos
        if d.get("icaoId")
    }
