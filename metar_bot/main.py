"""
Una ejecución del bot (la lanza GitHub Actions cada ~15 min):
  1. Lee los comandos recibidos en Telegram y los contesta.
  2. Descarga METAR y TAF de los aeropuertos guardados.
  3. Envía el informe según el modo (cambios / diario / ahora).
  4. Si hubo interacción, sigue escuchando unos minutos (ventana interactiva).

Variables de entorno:
  TELEGRAM_BOT_TOKEN -> token de @BotFather
  ALLOWED_CHAT_ID    -> tu chat id; los mensajes de otros chats se ignoran
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from metar_bot import aviationweather, buscador, telegram_api
from metar_bot.comandos import MENU_COMANDOS, procesar_comando
from metar_bot.estado import cargar_estado, guardar_estado
from metar_bot.formato import agrupar_en_mensajes, formatear_estacion

ZONA_HORARIA = ZoneInfo("Europe/Madrid")

# Ventana interactiva: tras un comando o botón el bot sigue escuchando un rato
# para que la conversación (p. ej. el buscador) responda al momento.
VENTANA_INACTIVIDAD = 5 * 60   # segundos sin interacción antes de terminar
VENTANA_MAXIMA = 10 * 60       # tope total (el job de Actions tiene 15 min)
ESPERA_LONG_POLLING = 25


def _responder(tg, token, chat_id, respuesta):
    if isinstance(respuesta, tuple):
        texto, botones = respuesta
        tg.enviar_mensaje(token, chat_id, texto, botones)
    elif respuesta:
        tg.enviar_mensaje(token, chat_id, respuesta)


def _procesar_boton(tg, token, chat_id, callback, estado):
    data = callback.get("data", "")
    print(f"Botón pulsado: {data}")
    texto, botones, aviso = buscador.pulsar(data, estado)
    tg.responder_callback(token, callback["id"], aviso)
    mensaje_id = (callback.get("message") or {}).get("message_id")
    if mensaje_id:
        tg.editar_mensaje(token, chat_id, mensaje_id, texto, botones)


def procesar_updates(token, chat_id, estado, tg=telegram_api, api=aviationweather, espera=0):
    """
    Contesta los comandos y botones pendientes.
    Devuelve (pedir_informe, numero_de_interacciones).
    """
    pedir_informe, interacciones = False, 0
    for update in tg.obtener_updates(token, estado["update_offset"], espera=espera):
        estado["update_offset"] = update["update_id"] + 1
        callback = update.get("callback_query")
        if callback:
            if str((callback.get("message") or {}).get("chat", {}).get("id")) == str(chat_id):
                _procesar_boton(tg, token, chat_id, callback, estado)
                interacciones += 1
            continue
        mensaje = update.get("message") or {}
        if str(mensaje.get("chat", {}).get("id")) != str(chat_id):
            continue
        texto = mensaje.get("text", "")
        print(f"Comando recibido: {texto}")
        respuesta, informe = procesar_comando(texto, estado, api.validar_estaciones)
        _responder(tg, token, chat_id, respuesta)
        pedir_informe = pedir_informe or informe
        interacciones += 1
    return pedir_informe, interacciones


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


def enviar_informe(token, chat_id, estado, ahora, forzar, tg=telegram_api, api=aviationweather):
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
        bloques = [formatear_estacion(i, metars.get(i), tafs.get(i), ahora) for i in a_enviar]
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


def registrar_menu(token, estado, tg=telegram_api):
    """Actualiza el menú "/" de Telegram solo cuando cambia la lista de comandos."""
    huella = hashlib.sha1(json.dumps(MENU_COMANDOS).encode()).hexdigest()[:12]
    if estado.get("menu_registrado") != huella and tg.registrar_comandos(token, MENU_COMANDOS):
        estado["menu_registrado"] = huella


def ejecutar(token, chat_id, estado, ahora, tg=telegram_api, api=aviationweather, reloj=time.monotonic):
    registrar_menu(token, estado, tg=tg)
    forzar, interacciones = procesar_updates(token, chat_id, estado, tg=tg, api=api)
    enviar_informe(token, chat_id, estado, ahora, forzar, tg=tg, api=api)

    if not interacciones:
        return
    inicio = ultima = reloj()
    print("Ventana interactiva abierta")
    while reloj() - ultima < VENTANA_INACTIVIDAD and reloj() - inicio < VENTANA_MAXIMA:
        forzar, interacciones = procesar_updates(
            token, chat_id, estado, tg=tg, api=api, espera=ESPERA_LONG_POLLING)
        if interacciones:
            ultima = reloj()
        if forzar:
            momento = ahora + timedelta(seconds=reloj() - inicio)
            enviar_informe(token, chat_id, estado, momento, True, tg=tg, api=api)
    print("Ventana interactiva cerrada")


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
