import copy

import pytest

from metar_bot import buscador
from metar_bot.estado import ESTADO_INICIAL

DB = {
    "continentes": {"EU": "Europa", "NA": "Norteamérica", "AN": "Antártida"},
    "paises": {
        "ES": {"nombre": "España", "continente": "EU"},
        "PT": {"nombre": "Portugal", "continente": "EU"},
        "US": {"nombre": "Estados Unidos", "continente": "NA", "estados": {"TX": "Texas", "NY": "Nueva York"}},
    },
    "aeropuertos": (
        [["LETO", "Torrejón", "ES", "M", 1, "TOJ"], ["LEMD", "Madrid/Barajas Arpt", "ES", "M", 1, "MAD"],
         ["LPPT", "Lisboa", "PT", "", 1, "LIS"], ["KJFK", "New York/JF Kennedy Intl", "US", "NY", 1, "JFK"]]
        + [[f"KT{i:02d}", f"Texas {i:02d}", "US", "TX", i % 2, ""] for i in range(20)]
    ),
}


@pytest.fixture(autouse=True)
def db_de_prueba(monkeypatch):
    monkeypatch.setattr(buscador, "_db", DB)


def estado(**c):
    e = copy.deepcopy(ESTADO_INICIAL)
    e.update(c)
    return e


def datos(botones):
    return [b[1] for fila in botones for b in fila]


def test_continentes_solo_con_paises():
    texto, botones = buscador.iniciar([], estado())
    assert datos(botones) == ["c:EU:0", "c:NA:0"]


def test_paises_ordenados_y_volver():
    _, botones = buscador.pulsar("c:EU:0", estado())[:2]
    assert datos(botones) == ["p:ES:0", "p:PT:0", "c"]


def test_pais_con_estados_y_paginacion():
    _, botones, _ = buscador.pulsar("p:US:0", estado())
    assert datos(botones)[:2] == ["e:US:NY:0", "e:US:TX:0"]
    _, botones, _ = buscador.pulsar("e:US:TX:0", estado())
    assert len([d for d in datos(botones) if d.startswith("t:")]) == buscador.POR_PAGINA
    assert "e:US:TX:1" in datos(botones)
    _, botones, _ = buscador.pulsar("e:US:TX:1", estado())
    assert len([d for d in datos(botones) if d.startswith("t:")]) == 20 - buscador.POR_PAGINA


def test_pulsar_aeropuerto_anade_y_quita():
    e = estado()
    texto, botones, aviso = buscador.pulsar("t:LETO|p:ES:0", e)
    assert e["estaciones"] == ["LETO"] and aviso == "✅ LETO añadido"
    assert any(b[0].startswith("✅ LETO") for fila in botones for b in fila)
    _, _, aviso = buscador.pulsar("t:LETO|p:ES:0", e)
    assert e["estaciones"] == [] and "quitado" in aviso


def test_busqueda_por_texto_sin_acentos_e_iata():
    _, botones = buscador.iniciar(["torrejon"], estado())
    assert datos(botones)[0] == "t:LETO|s:torrejon"
    _, botones = buscador.iniciar(["MAD"], estado())
    assert datos(botones)[0].startswith("t:LEMD|")
    texto, _ = buscador.iniciar(["zzzz"], estado())
    assert "Sin resultados" in texto


def test_callback_data_cabe_en_64_bytes():
    _, botones = buscador.iniciar(["á" * 30], estado())
    _, botones = buscador.iniciar(["texas"], estado())
    assert all(len(d.encode()) <= 64 for d in datos(botones))


def test_vista_desconocida_vuelve_a_continentes():
    texto, _, _ = buscador.pulsar("p:XX:no", estado())
    assert "continente" in texto
