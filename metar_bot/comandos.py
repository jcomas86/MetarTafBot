import re

MAX_ESTACIONES = 20
PATRON_OACI = re.compile(r"^[A-Z0-9]{4}$")
PATRON_HORA = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

AYUDA = (
    "🛩️ <b>Bot METAR/TAF</b>\n\n"
    "/buscar — buscar aeropuertos por continente y país\n"
    "/buscar torrejon — buscar por nombre o código\n"
    "/add LEMD LEBL — añadir aeropuertos (código OACI)\n"
    "/remove LEBL — quitar aeropuertos\n"
    "/list — ver aeropuertos y modo\n"
    "/modo cambios — aviso cuando salga un METAR/TAF nuevo\n"
    "/modo diario 07:30 — un resumen al día a esa hora\n"
    "/ahora — informe inmediato\n\n"
    "<i>El bot revisa cada ~30 min, así que el primer comando puede tardar un poco. "
    "Después se queda atento unos minutos y responde al momento.</i>"
)

# Menú "/" de Telegram (setMyCommands)
MENU_COMANDOS = [
    ("buscar", "Buscar aeropuertos"),
    ("list", "Ver mis aeropuertos y el modo"),
    ("ahora", "Informe METAR/TAF inmediato"),
    ("add", "Añadir por código OACI: /add LEMD"),
    ("remove", "Quitar: /remove LEMD"),
    ("modo", "/modo cambios  ó  /modo diario 07:30"),
    ("help", "Ayuda"),
]


def _codigos(args):
    return [a.strip(",").upper() for a in args if a.strip(",")]


def anadir_estaciones(estado, codigos, validar_estaciones):
    """Añade los códigos válidos a la lista y devuelve el texto de respuesta."""
    invalidos = [c for c in codigos if not PATRON_OACI.match(c)]
    nuevos = [c for c in codigos if PATRON_OACI.match(c) and c not in estado["estaciones"]]
    existentes = validar_estaciones(nuevos) if nuevos else {}
    no_encontrados = [c for c in nuevos if c not in existentes]
    anadidos = [c for c in nuevos if c in existentes]

    hueco = max(MAX_ESTACIONES - len(estado["estaciones"]), 0)
    sobrantes = anadidos[hueco:]
    anadidos = anadidos[:hueco]
    estado["estaciones"].extend(anadidos)

    lineas = []
    if anadidos:
        lineas.append("✅ Añadidos: " + ", ".join(f"{c} ({existentes[c]})" for c in anadidos))
    if no_encontrados or invalidos:
        lineas.append("❌ No encontrados: " + ", ".join(invalidos + no_encontrados))
    if sobrantes:
        lineas.append(f"⚠️ Máximo {MAX_ESTACIONES} aeropuertos. No añadidos: " + ", ".join(sobrantes))
    if not lineas:
        lineas.append("Esos aeropuertos ya estaban en tu lista.")
    return "\n".join(lineas)


def quitar_estaciones(estado, codigos):
    """Quita los códigos de la lista y devuelve el texto de respuesta."""
    quitados = [c for c in codigos if c in estado["estaciones"]]
    estado["estaciones"] = [c for c in estado["estaciones"] if c not in quitados]
    for c in quitados:
        estado["vistos"].pop(c, None)
    if not quitados:
        return "Ninguno de esos aeropuertos estaba en tu lista."
    return "🗑️ Quitados: " + ", ".join(quitados)


def procesar_comando(texto, estado, validar_estaciones):
    """
    Ejecuta un comando sobre `estado` (lo modifica).
    Devuelve (respuesta, pedir_informe). `respuesta` es un texto, o una tupla
    (texto, botones) cuando la respuesta lleva botones.
    `validar_estaciones(ids)` -> {icao: nombre} de las que existen.
    """
    partes = texto.strip().split()
    if not partes or not partes[0].startswith("/"):
        return "No entiendo ese mensaje. Escribe /help para ver los comandos.", False

    comando = partes[0].split("@")[0].lower()  # /add@MiBot -> /add
    args = partes[1:]

    if comando in ("/start", "/help"):
        return AYUDA, False

    if comando == "/add":
        codigos = _codigos(args)
        if not codigos:
            return "Uso: /add LEMD LEBL", False
        return anadir_estaciones(estado, codigos, validar_estaciones), False

    if comando == "/remove":
        codigos = _codigos(args)
        if not codigos:
            return "Uso: /remove LEBL", False
        return quitar_estaciones(estado, codigos), False

    if comando == "/list":
        if estado["modo"] == "diario":
            modo = f"diario a las {estado['hora_diaria']} (hora de Madrid)"
        else:
            modo = "cada vez que haya un METAR/TAF nuevo"
        lista = ", ".join(estado["estaciones"]) or "(ninguno)"
        return f"📋 Aeropuertos: {lista}\n⏱️ Modo: {modo}", False

    if comando == "/modo":
        if args and args[0].lower() == "cambios":
            estado["modo"] = "cambios"
            return "⏱️ Modo cambios: te aviso cuando salga un METAR o TAF nuevo.", False
        if args and args[0].lower() == "diario":
            hora = args[1] if len(args) > 1 else estado["hora_diaria"]
            m = PATRON_HORA.match(hora)
            if not m:
                return "Hora no válida. Ejemplo: /modo diario 07:30", False
            estado["modo"] = "diario"
            estado["hora_diaria"] = f"{int(m.group(1)):02d}:{m.group(2)}"
            estado["ultimo_envio_diario"] = ""
            return f"⏱️ Modo diario: resumen cada día a las {estado['hora_diaria']} (hora de Madrid).", False
        return "Uso: /modo cambios  ó  /modo diario 07:30", False

    if comando in ("/buscar", "/search"):
        from metar_bot import buscador  # import local: buscador usa funciones de este módulo
        return buscador.iniciar(args, estado), False

    if comando == "/ahora":
        if not estado["estaciones"]:
            return "No tienes aeropuertos. Añade alguno con /add LEMD", False
        return None, True  # el informe en sí es la respuesta

    return "Comando desconocido. Escribe /help para ver los comandos.", False
