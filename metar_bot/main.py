"""
Una ejecución del bot (la lanza GitHub Actions cada ~15 min):
  1. Lee los comandos recibidos en Telegram y los contesta.
  2. Descarga METAR y TAF de los aeropuertos guardados.
  3. Envía el informe según el modo (cambios / diario / ahora).

Variables de entorno:
  TELEGRAM_BOT_TOKEN -> token de @BotFather
  ALLOWED_CHAT_ID    -> tu chat id; los mensajes de otros chats se ignoran
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from metar_bot import aviationweather, telegram_api
from metar_bot.comandos import procesar_comando
from metar_bot.estado import cargar_estado, guardar_estado
from metar_bot.formato import agrupar_en_mensajes, formatear_estacion

ZONA_HORARIA = ZoneInfo("Europe/Madrid")


def procesar_updates(token, chat_id, estado, tg=telegram_api, api=aviationweather):
    """Contesta los comandos pendientes. Devuelve True si alguno pidió un informe inmediato."""
    pedir_informe = False
    for update in tg.obtener_updates(token, estado["update_offset"]):
        estado["update_offset"] = update["update_id"] + 1
        mensaje = update.get("message") or {}
        if str(mensaje.get("chat", {}).get("id")) != str(chat_id):
            continue
        texto = mensaje.get("text", "")
        print(f"Comando recibido: {texto}")
        respuesta, informe = procesar_comando(texto, estado, api.validar_estaciones)
        if respuesta:
            tg.enviar_mensaje(token, chat_id, respuesta)
        pedir_informe = pedir_informe or informe
    return pedir_informe


def toca_resumen_diario(estado, ahora):
    hoy = ahora.strftime("%Y-%m-%d")
    return ahora.strftime("%H:%M") >= estado["hora_diaria"] and estado["ultimo_envio_diario"] != hoy


def estaciones_con_cambios(estado, metars, tafs):
    cambiadas = []
    for icao in estado["estaciones"]:
        visto = estado["vistos"].get(icao, {})
        metar_nuevo = (metars.get(icao) or {}).get("obsTime", 0) > visto.get("metar", 0)
        taf_nuevo = (tafs.get(icao) or {}).get("issueTime", 0) > visto.get("taf", 0)
        if metar_nuevo or taf_nuevo:
            cambiadas.append(icao)
    return cambiadas


def ejecutar(token, chat_id, estado, ahora, tg=telegram_api, api=aviationweather):
    forzar = procesar_updates(token, chat_id, estado, tg=tg, api=api)

    estaciones = estado["estaciones"]
    if not estaciones:
        print("No hay aeropuertos guardados.")
        return

    metars = api.obtener_metars(estaciones)
    tafs = api.obtener_tafs(estaciones)

    diario = estado["modo"] == "diario" and toca_resumen_diario(estado, ahora)
    if forzar or diario:
        a_enviar = list(estaciones)
    elif estado["modo"] == "cambios":
        a_enviar = estaciones_con_cambios(estado, metars, tafs)
    else:
        a_enviar = []

    ok = True
    if a_enviar:
        bloques = [formatear_estacion(i, metars.get(i), tafs.get(i)) for i in a_enviar]
        for texto in agrupar_en_mensajes(bloques):
            ok = tg.enviar_mensaje(token, chat_id, texto) and ok
        print(f"Informe enviado de: {', '.join(a_enviar)}" if ok else "Fallo enviando el informe")

    # Si el envío falló no marcamos nada como visto, para reintentarlo en la próxima ejecución
    if ok:
        for icao in estaciones:
            estado["vistos"][icao] = {
                "metar": (metars.get(icao) or {}).get("obsTime", 0),
                "taf": (tafs.get(icao) or {}).get("issueTime", 0),
            }
        if diario:
            estado["ultimo_envio_diario"] = ahora.strftime("%Y-%m-%d")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("ALLOWED_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("Faltan las variables de entorno TELEGRAM_BOT_TOKEN y/o ALLOWED_CHAT_ID")

    estado = cargar_estado()
    try:
        ejecutar(token, chat_id, estado, datetime.now(ZONA_HORARIA))
    finally:
        # Guardamos siempre: así no se reprocesan comandos aunque falle la API
        guardar_estado(estado)


if __name__ == "__main__":
    main()
