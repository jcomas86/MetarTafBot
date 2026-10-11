import json

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{metodo}"


def _teclado(botones):
    """[[(texto, callback_data), ...], ...] -> reply_markup de Telegram."""
    return json.dumps({"inline_keyboard": [
        [{"text": texto, "callback_data": data} for texto, data in fila] for fila in botones
    ]})


def _llamar(token, metodo, datos, timeout=15):
    resp = requests.post(TELEGRAM_API.format(token=token, metodo=metodo), data=datos, timeout=timeout)
    if resp.status_code != 200:
        print(f"  [ERROR] Telegram {metodo} devolvió {resp.status_code}: {resp.text}")
        return False
    return True


def enviar_mensaje(token, chat_id, texto, botones=None):
    datos = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if botones:
        datos["reply_markup"] = _teclado(botones)
    return _llamar(token, "sendMessage", datos)


def editar_mensaje(token, chat_id, message_id, texto, botones=None):
    datos = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": _teclado(botones or []),
    }
    return _llamar(token, "editMessageText", datos)


def responder_callback(token, callback_id, texto=None):
    """Quita el relojito del botón pulsado y, opcionalmente, muestra un aviso corto."""
    datos = {"callback_query_id": callback_id}
    if texto:
        datos["text"] = texto
    return _llamar(token, "answerCallbackQuery", datos)


def registrar_comandos(token, comandos):
    """Menú "/" del chat: [(comando, descripción), ...]"""
    lista = [{"command": c, "description": d} for c, d in comandos]
    return _llamar(token, "setMyCommands", {"commands": json.dumps(lista, ensure_ascii=False)})


def obtener_updates(token, offset, espera=0):
    """Mensajes y botones recibidos desde el último offset. `espera` > 0 = long polling."""
    resp = requests.get(TELEGRAM_API.format(token=token, metodo="getUpdates"), params={
        "offset": offset,
        "timeout": espera,
        "allowed_updates": '["message","callback_query"]',
    }, timeout=espera + 20)
    resp.raise_for_status()
    return resp.json().get("result", [])
