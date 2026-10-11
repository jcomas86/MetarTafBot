import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{metodo}"


def enviar_mensaje(token, chat_id, texto):
    resp = requests.post(TELEGRAM_API.format(token=token, metodo="sendMessage"), data={
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)

    if resp.status_code != 200:
        print(f"  [ERROR] Telegram devolvió {resp.status_code}: {resp.text}")
        return False
    return True


def obtener_updates(token, offset):
    """Mensajes recibidos por el bot desde el último offset procesado."""
    resp = requests.get(TELEGRAM_API.format(token=token, metodo="getUpdates"), params={
        "offset": offset,
        "timeout": 0,
        "allowed_updates": '["message"]',
    }, timeout=20)
    resp.raise_for_status()
    return resp.json().get("result", [])
