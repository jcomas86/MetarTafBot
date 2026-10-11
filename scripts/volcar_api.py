"""Vuelca en el log respuestas reales de las fuentes de datos (para depurar el formato)."""

import gzip
import json
import sys

import requests

H = {"User-Agent": "MetarTafBot/1.0 (bot personal de Telegram)"}
ids = sys.argv[1] if len(sys.argv) > 1 else "LETO,LEMD,KJFK"

for tipo in ("metar", "taf"):
    r = requests.get(f"https://aviationweather.gov/api/data/{tipo}",
                     params={"ids": ids, "format": "json"}, headers=H, timeout=30)
    print(f"===== {tipo} {r.status_code}")
    print(json.dumps(r.json(), indent=1, ensure_ascii=False))

r = requests.get("https://aviationweather.gov/data/cache/stations.cache.json.gz", headers=H, timeout=60)
print(f"===== stations.cache {r.status_code} {len(r.content)} bytes")
try:
    datos = json.loads(gzip.decompress(r.content))
except OSError:
    datos = r.json()
print(type(datos).__name__, len(datos))
muestra = datos[:3] if isinstance(datos, list) else list(datos.items())[:3]
print(json.dumps(muestra, indent=1, ensure_ascii=False))
leto = [d for d in (datos if isinstance(datos, list) else datos.values()) if "LETO" in json.dumps(d)]
print("LETO:", json.dumps(leto[:1], ensure_ascii=False))

r = requests.get("https://davidmegginson.github.io/ourairports-data/countries.csv", timeout=30)
print(f"===== countries.csv {r.status_code}")
print("\n".join(r.text.splitlines()[:4]))
