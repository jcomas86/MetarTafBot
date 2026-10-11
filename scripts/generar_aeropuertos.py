"""
Genera aeropuertos.json para el buscador /buscar.

Fuentes (públicas y gratuitas):
  - Estaciones con METAR/TAF: https://aviationweather.gov/data/cache/stations.cache.json.gz
  - País -> continente:       https://davidmegginson.github.io/ourairports-data/countries.csv
  - Nombres en español:       pycountry (traducciones iso3166 incluidas en el paquete)

Lo ejecuta el workflow .github/workflows/aeropuertos.yml (manual y una vez al mes).
"""

import csv
import gettext
import gzip
import io
import json

import pycountry
import requests

ESTACIONES_URL = "https://aviationweather.gov/data/cache/stations.cache.json.gz"
PAISES_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"
HEADERS = {"User-Agent": "MetarTafBot/1.0 (bot personal de Telegram)"}
SALIDA = "aeropuertos.json"

# Países con tantas estaciones que conviene un nivel más (estado/provincia)
MINIMO_PARA_ESTADOS = 150

CONTINENTES = {
    "EU": "Europa", "NA": "Norteamérica", "SA": "Sudamérica", "AS": "Asia",
    "AF": "África", "OC": "Oceanía", "AN": "Antártida",
}


def descargar_estaciones():
    resp = requests.get(ESTACIONES_URL, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    try:
        return json.loads(gzip.decompress(resp.content))
    except OSError:  # por si el servidor ya lo entrega descomprimido
        return resp.json()


def descargar_paises():
    resp = requests.get(PAISES_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return {fila["code"]: fila for fila in csv.DictReader(io.StringIO(resp.text))}


def nombre_pais_es(codigo, nombre_en):
    es = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["es"], fallback=True)
    pais = pycountry.countries.get(alpha_2=codigo)
    if not pais:
        return nombre_en
    return es.gettext(getattr(pais, "common_name", None) or pais.name)


def nombre_estado(pais, estado):
    sub = pycountry.subdivisions.get(code=f"{pais}-{estado}")
    return sub.name if sub else estado


def limpiar(nombre):
    nombre = " ".join((nombre or "").split())
    return nombre.replace(" ,", ",")


def main():
    estaciones = descargar_estaciones()
    paises_csv = descargar_paises()

    aeropuertos = []
    for e in estaciones:
        icao = (e.get("icaoId") or "").upper()
        pais = e.get("country") or ""
        tipos = e.get("siteType") or []
        if len(icao) != 4 or "METAR" not in tipos or pais not in paises_csv:
            continue
        aeropuertos.append([
            icao,
            limpiar(e.get("site")) or icao,
            pais,
            (e.get("state") or "").strip(),
            1 if "TAF" in tipos else 0,
            (e.get("iataId") or "").upper(),
        ])
    aeropuertos.sort(key=lambda a: (a[2], a[1].lower()))

    por_pais = {}
    for a in aeropuertos:
        por_pais.setdefault(a[2], []).append(a)

    paises = {}
    for codigo, lista in por_pais.items():
        fila = paises_csv[codigo]
        info = {"nombre": nombre_pais_es(codigo, fila["name"]), "continente": fila["continent"]}
        estados = {a[3] for a in lista if a[3]}
        if len(lista) >= MINIMO_PARA_ESTADOS and len(estados) > 1:
            info["estados"] = {s: nombre_estado(codigo, s) for s in sorted(estados)}
        paises[codigo] = info

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({
            "continentes": CONTINENTES,
            "paises": paises,
            # [icao, nombre, país, estado, tiene_taf, iata]
            "aeropuertos": aeropuertos,
        }, f, ensure_ascii=False, separators=(",", ":"))

    print(f"{len(aeropuertos)} aeropuertos con METAR en {len(paises)} países")
    for codigo in ("ES", "PT", "FR", "US"):
        if codigo in paises:
            print(f"  {codigo} {paises[codigo]['nombre']}: {len(por_pais[codigo])} aeropuertos,"
                  f" estados: {len(paises[codigo].get('estados', {}))}")


if __name__ == "__main__":
    main()
