import json
import os

ESTADO_PATH = "estado.json"

ESTADO_INICIAL = {
    "estaciones": [],          # ["LEMD", "LEBL", ...]
    "modo": "cambios",         # "cambios" | "diario"
    "hora_diaria": "07:00",    # HH:MM en ZONA_HORARIA, solo para modo diario
    "ultimo_envio_diario": "", # fecha YYYY-MM-DD del último resumen diario
    "vistos": {},              # {icao: {"metar": obsTime, "taf": issueTime}}
    "update_offset": 0,        # offset de getUpdates de Telegram
}


def cargar_estado(path=ESTADO_PATH):
    estado = dict(ESTADO_INICIAL)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            estado.update(json.load(f))
    return estado


def guardar_estado(estado, path=ESTADO_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
        f.write("\n")
