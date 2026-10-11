import json
from datetime import datetime, timezone
from pathlib import Path

from metar_bot import aviationweather
from metar_bot import decodificar as d
from metar_bot.formato import formatear_estacion

DATOS = Path(__file__).parent / "datos"
AHORA = datetime(2026, 10, 11, 13, 55, tzinfo=timezone.utc)


def cargar():
    metars = aviationweather._ultimo_por_estacion(json.loads((DATOS / "metar_real.json").read_text()), "obsTime")
    tafs = aviationweather._ultimo_por_estacion(json.loads((DATOS / "taf_real.json").read_text()), "issueTime")
    return metars, tafs


def test_viento():
    assert d.viento(210, 4, raw="LETO 111330Z 21004KT 140V260 CAVOK") == \
        "4 kt (7 km/h) del sur-suroeste, variando entre sureste y oeste"
    assert d.viento("VRB", 3) == "3 kt (6 km/h) con dirección variable"
    assert d.viento(0, 0) == "en calma"
    assert "rachas de 24 kt" in d.viento(100, 15, 24)
    assert d.viento(None, None) is None


def test_visibilidad():
    assert d.visibilidad("6+") == "10 km o más"
    assert d.visibilidad("10+") == "10 km o más"
    assert d.visibilidad(4) == "6 km"
    assert d.visibilidad(2) == "3200 m"
    assert d.visibilidad("") is None
    assert d.visibilidad(None, cavok=True) == "10 km o más"


def test_nubes():
    assert d.nubes([], "CAVOK") == "sin nubes por debajo de 1500 m y sin cumulonimbus"
    assert d.nubes([{"cover": "NSC", "base": None}]) == "sin nubes significativas"
    assert d.nubes([{"cover": "BKN", "base": 4600}]) == "nuboso a 1400 m (4600 ft)"
    assert "cumulonimbus" in d.nubes([{"cover": "SCT", "base": 3000, "type": "CB"}])
    assert d.nubes([]) is None


def test_fenomenos():
    assert d.fenomenos("-RA") == "lluvia débil"
    assert d.fenomenos("-SHRA BR") == "chubascos de lluvia débil, neblina"
    assert d.fenomenos("+TSRA") == "tormenta con lluvia fuerte"
    assert d.fenomenos("VCSH") == "chubascos en las proximidades"
    assert d.fenomenos("FZFG") == "niebla engelante"
    assert d.fenomenos("XYZ123") == "XYZ123"


def test_humedad_coordenadas_y_tiempos():
    assert d.humedad(11, 9) == 87  # igual que allmetsat para LETO
    assert d.coordenadas(40.489, -3.451) == "40-29N 003-27W"
    assert d.hace(AHORA.timestamp() - 31 * 60, AHORA) == "hace 31 min"
    assert d.hace(AHORA.timestamp() - 151 * 60, AHORA) == "hace 2 h 31 min"
    assert d.nombre_corto("Madrid/Barajas Arpt, M, ES") == "Madrid/Barajas Arpt"


def test_mensaje_completo_con_datos_reales():
    metars, tafs = cargar()
    texto = formatear_estacion("LETO", metars["LETO"], tafs["LETO"], AHORA)
    for esperado in ("✈️ <b>LETO</b> — Torrejon", "40-29N 003-27W · 598 m", "13:30 UTC (hace 25 min)",
                     "variando entre sureste y oeste", "💧 38 %", "1016 hPa", "Visibilidad 10 km o más",
                     "Sin nubes por debajo de 1500 m", "<pre>METAR LETO 111330Z", "emitido 11:00 UTC",
                     "Máx 22 °C", "Mín 9 °C", "<pre>TAF LETO 111100Z"):
        assert esperado in texto, esperado


def test_taf_con_tempo_y_probabilidad():
    metars, tafs = cargar()
    texto = formatear_estacion("LEMD", metars["LEMD"], tafs["LEMD"], AHORA)
    assert "Probabilidad 30 % · temporalmente día 11 12:00–18:00Z" in texto
    texto = formatear_estacion("KJFK", metars["KJFK"], tafs["KJFK"], AHORA)
    assert "Desde el 11 a las 15:00Z" in texto and "visibilidad 3200 m" in texto
