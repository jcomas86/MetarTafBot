import copy
from datetime import datetime
from types import SimpleNamespace

from metar_bot import aviationweather
from metar_bot.comandos import procesar_comando
from metar_bot.estado import ESTADO_INICIAL
from metar_bot.formato import agrupar_en_mensajes, formatear_estacion
from metar_bot.main import ZONA_HORARIA, ejecutar

METAR_LEMD = {"icaoId": "LEMD", "name": "Madrid/Barajas Intl, MD, ES", "obsTime": 1760180400,
              "rawOb": "LEMD 111100Z 21008KT CAVOK 18/09 Q1021 NOSIG", "fltCat": "VFR"}
TAF_LEMD = {"icaoId": "LEMD", "issueTime": 1760158800,
            "rawTAF": "TAF LEMD 110500Z 1106/1212 21010KT CAVOK"}


def estado_nuevo(**cambios):
    estado = copy.deepcopy(ESTADO_INICIAL)
    estado.update(cambios)
    return estado


def validar(ids):
    conocidos = {"LEMD": "Madrid Barajas", "LEBL": "Barcelona El Prat"}
    return {i: conocidos[i] for i in ids if i in conocidos}


class FakeTelegram:
    def __init__(self, updates=()):
        self.updates = list(updates)
        self.enviados = []

    def obtener_updates(self, token, offset):
        return [u for u in self.updates if u["update_id"] >= offset]

    def enviar_mensaje(self, token, chat_id, texto):
        self.enviados.append(texto)
        return True


def fake_api(metars, tafs):
    return SimpleNamespace(
        obtener_metars=lambda ids: {k: v for k, v in metars.items() if k in ids},
        obtener_tafs=lambda ids: {k: v for k, v in tafs.items() if k in ids},
        validar_estaciones=validar,
    )


def update(uid, texto, chat=123):
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": texto}}


# --- API -------------------------------------------------------------------

def test_ultimo_por_estacion_se_queda_con_el_mas_reciente():
    datos = [{"icaoId": "LEMD", "obsTime": 1}, {"icaoId": "lemd", "obsTime": 5}, {"icaoId": "LEBL", "obsTime": 2}]
    r = aviationweather._ultimo_por_estacion(datos, "obsTime")
    assert r["LEMD"]["obsTime"] == 5 and set(r) == {"LEMD", "LEBL"}


def test_horas_en_texto_iso_se_convierten_a_unix():
    datos = [{"icaoId": "LEMD", "issueTime": "2025-10-11T05:00:00.000Z"},
             {"icaoId": "LEMD", "issueTime": "2025-10-11T11:00:00Z"}]
    r = aviationweather._ultimo_por_estacion(datos, "issueTime")
    assert r["LEMD"]["issueTime"] == 1760180400
    assert aviationweather.a_timestamp(None) == 0 and aviationweather.a_timestamp("basura") == 0


def test_get_json_sin_ids_no_llama_a_la_red():
    assert aviationweather._get_json("metar", []) == []


# --- Comandos --------------------------------------------------------------

def test_add_valida_y_no_duplica():
    estado = estado_nuevo(estaciones=["LEMD"])
    resp, _ = procesar_comando("/add lebl LEMD XXXX 12", estado, validar)
    assert estado["estaciones"] == ["LEMD", "LEBL"]
    assert "LEBL" in resp and "XXXX" in resp and "12" in resp


def test_add_con_nombre_de_bot_y_limite():
    estado = estado_nuevo(estaciones=[f"K{i:03d}" for i in range(19)])
    resp, _ = procesar_comando("/add@MiBot LEMD LEBL", estado, validar)
    assert len(estado["estaciones"]) == 20 and "LEBL" in resp.split("No añadidos")[1]


def test_remove_borra_tambien_vistos():
    estado = estado_nuevo(estaciones=["LEMD", "LEBL"], vistos={"LEBL": {"metar": 1, "taf": 1}})
    procesar_comando("/remove LEBL", estado, validar)
    assert estado["estaciones"] == ["LEMD"] and "LEBL" not in estado["vistos"]


def test_modo_diario_y_hora_invalida():
    estado = estado_nuevo()
    procesar_comando("/modo diario 7:05", estado, validar)
    assert estado["modo"] == "diario" and estado["hora_diaria"] == "07:05"
    resp, _ = procesar_comando("/modo diario 25:00", estado, validar)
    assert "no válida" in resp and estado["hora_diaria"] == "07:05"


def test_ahora_pide_informe():
    assert procesar_comando("/ahora", estado_nuevo(estaciones=["LEMD"]), validar) == (None, True)
    assert procesar_comando("/ahora", estado_nuevo(), validar)[1] is False


# --- Formato ---------------------------------------------------------------

def test_formato_escapa_html_y_maneja_faltantes():
    texto = formatear_estacion("LEMD", dict(METAR_LEMD, rawOb="A<B"), None)
    assert "A&lt;B" in texto and "Sin TAF" in texto and "🟢 VFR" in texto


def test_agrupar_respeta_limite():
    bloques = ["x" * 30] * 5
    mensajes = agrupar_en_mensajes(bloques, limite=70)
    assert all(len(m) <= 70 for m in mensajes) and len(mensajes) == 3


# --- Ejecución completa ----------------------------------------------------

AHORA = datetime(2025, 10, 11, 9, 0, tzinfo=ZONA_HORARIA)


def test_modo_cambios_envia_solo_lo_nuevo():
    estado = estado_nuevo(estaciones=["LEMD"])
    api = fake_api({"LEMD": METAR_LEMD}, {"LEMD": TAF_LEMD})
    tg = FakeTelegram()
    ejecutar("t", 123, estado, AHORA, tg=tg, api=api)
    assert len(tg.enviados) == 1 and "LEMD 111100Z" in tg.enviados[0]
    ejecutar("t", 123, estado, AHORA, tg=tg, api=api)
    assert len(tg.enviados) == 1  # nada nuevo -> no repite
    api = fake_api({"LEMD": dict(METAR_LEMD, obsTime=METAR_LEMD["obsTime"] + 1800)}, {"LEMD": TAF_LEMD})
    ejecutar("t", 123, estado, AHORA, tg=tg, api=api)
    assert len(tg.enviados) == 2


def test_modo_diario_una_vez_al_dia():
    estado = estado_nuevo(estaciones=["LEMD"], modo="diario", hora_diaria="08:30")
    api = fake_api({"LEMD": METAR_LEMD}, {"LEMD": TAF_LEMD})
    tg = FakeTelegram()
    ejecutar("t", 123, estado, AHORA.replace(hour=8), tg=tg, api=api)
    assert tg.enviados == []  # aún no es la hora
    ejecutar("t", 123, estado, AHORA, tg=tg, api=api)
    ejecutar("t", 123, estado, AHORA.replace(hour=12), tg=tg, api=api)
    assert len(tg.enviados) == 1 and estado["ultimo_envio_diario"] == "2025-10-11"


def test_comandos_de_otros_chats_se_ignoran_y_offset_avanza():
    estado = estado_nuevo()
    tg = FakeTelegram([update(10, "/add LEMD", chat=999), update(11, "/add LEBL")])
    ejecutar("t", 123, estado, AHORA, tg=tg, api=fake_api({}, {}))
    assert estado["estaciones"] == ["LEBL"] and estado["update_offset"] == 12


def test_ahora_envia_informe_completo():
    estado = estado_nuevo(estaciones=["LEMD"], modo="diario", hora_diaria="23:00")
    tg = FakeTelegram([update(1, "/ahora")])
    ejecutar("t", 123, estado, AHORA, tg=tg, api=fake_api({"LEMD": METAR_LEMD}, {"LEMD": TAF_LEMD}))
    assert any("TAF LEMD" in m for m in tg.enviados)
