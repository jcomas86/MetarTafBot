"""
Buscador de aeropuertos con botones de Telegram:
  /buscar           -> Continente -> País -> (Estado) -> Aeropuerto
  /buscar torrejon  -> búsqueda directa por nombre, OACI o IATA

Cada pantalla se devuelve como (texto, botones), donde botones es una lista
de filas y cada fila una lista de (etiqueta, callback_data).
callback_data (máx. 64 bytes):
  c                 lista de continentes
  c:EU:0            países de Europa, página 0
  p:ES:0            aeropuertos (o estados) de España, página 0
  e:US:TX:0         aeropuertos de Texas, página 0
  s:<texto>         resultados de búsqueda
  t:LETO|<vista>    añadir/quitar LETO y volver a pintar <vista>
"""

import json
import os
import unicodedata

from metar_bot.comandos import anadir_estaciones, quitar_estaciones

AEROPUERTOS_PATH = "aeropuertos.json"
POR_PAGINA = 15
MAX_RESULTADOS = 10

_db = None


def cargar_db(path=AEROPUERTOS_PATH):
    global _db
    if _db is None:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            _db = json.load(f)
    return _db


def _normalizar(texto):
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def _paginar(elementos, pagina, prefijo):
    """Devuelve (elementos de la página, fila de navegación)."""
    total = max((len(elementos) - 1) // POR_PAGINA + 1, 1)
    pagina = min(max(pagina, 0), total - 1)
    trozo = elementos[pagina * POR_PAGINA:(pagina + 1) * POR_PAGINA]
    nav = []
    if pagina > 0:
        nav.append(("◀️", f"{prefijo}:{pagina - 1}"))
    if total > 1:
        nav.append((f"{pagina + 1}/{total}", f"{prefijo}:{pagina}"))
    if pagina < total - 1:
        nav.append(("▶️", f"{prefijo}:{pagina + 1}"))
    return trozo, nav


def _boton_aeropuerto(a, estado, vista):
    icao, nombre, _, _, taf, _ = a
    marca = "✅ " if icao in estado["estaciones"] else ""
    etiqueta = f"{marca}{icao} · {nombre}{' 📅' if taf else ''}"
    return [(etiqueta[:60], f"t:{icao}|{vista}"[:64])]


LEYENDA = "Pulsa un aeropuerto para añadirlo o quitarlo (✅ = guardado, 📅 = tiene TAF)."


def _vista_continentes(db):
    paises_por_cont = {}
    for info in db["paises"].values():
        paises_por_cont[info["continente"]] = paises_por_cont.get(info["continente"], 0) + 1
    botones = [[(nombre, f"c:{codigo}:0")]
               for codigo, nombre in db["continentes"].items() if paises_por_cont.get(codigo)]
    return "🌍 <b>Elige continente</b>\n<i>Consejo: también puedes escribir /buscar torrejon</i>", botones


def _vista_paises(db, continente, pagina):
    paises = sorted(
        ((c, i["nombre"]) for c, i in db["paises"].items() if i["continente"] == continente),
        key=lambda p: _normalizar(p[1]),
    )
    trozo, nav = _paginar(paises, pagina, f"c:{continente}")
    botones = [[(nombre, f"p:{codigo}:0")] for codigo, nombre in trozo]
    if nav:
        botones.append(nav)
    botones.append([("⬅️ Continentes", "c")])
    titulo = db["continentes"].get(continente, continente)
    return f"🌍 <b>{titulo}</b> · elige país", botones


def _vista_lista(db, estado, aeropuertos, pagina, prefijo, titulo, volver):
    trozo, nav = _paginar(aeropuertos, pagina, prefijo)
    vista = f"{prefijo}:{pagina}"
    botones = [_boton_aeropuerto(a, estado, vista) for a in trozo]
    if nav:
        botones.append(nav)
    botones.append([volver])
    return f"{titulo}\n{LEYENDA}", botones


def _vista_pais(db, estado, pais, pagina):
    info = db["paises"].get(pais)
    if not info:
        return _vista_continentes(db)
    volver = ("⬅️ Países", f"c:{info['continente']}:0")
    if "estados" in info:
        estados = sorted(info["estados"].items(), key=lambda e: _normalizar(e[1]))
        trozo, nav = _paginar(estados, pagina, f"p:{pais}")
        botones = [[(nombre, f"e:{pais}:{codigo}:0")] for codigo, nombre in trozo]
        if nav:
            botones.append(nav)
        botones.append([volver])
        return f"🏳️ <b>{info['nombre']}</b> · elige estado o región", botones
    aeropuertos = [a for a in db["aeropuertos"] if a[2] == pais]
    return _vista_lista(db, estado, aeropuertos, pagina, f"p:{pais}",
                        f"🏳️ <b>{info['nombre']}</b>", volver)


def _vista_estado(db, estado, pais, region, pagina):
    info = db["paises"].get(pais, {})
    aeropuertos = [a for a in db["aeropuertos"] if a[2] == pais and a[3] == region]
    nombre = info.get("estados", {}).get(region, region)
    return _vista_lista(db, estado, aeropuertos, pagina, f"e:{pais}:{region}",
                        f"🏳️ <b>{info.get('nombre', pais)} · {nombre}</b>", ("⬅️ Regiones", f"p:{pais}:0"))


def buscar_texto(db, texto):
    consulta = _normalizar(texto)
    codigo = consulta.upper()
    exactos = [a for a in db["aeropuertos"] if codigo in (a[0], a[5])]
    parciales = [a for a in db["aeropuertos"]
                 if a not in exactos and consulta in _normalizar(f"{a[1]} {a[0]}")]
    return (exactos + parciales)[:MAX_RESULTADOS]


def _vista_busqueda(db, estado, texto):
    resultados = buscar_texto(db, texto)
    vista = f"s:{_normalizar(texto)}"[:40]  # ASCII y corto: cabe "t:XXXX|" en 64 bytes
    if not resultados:
        return (f"🔎 Sin resultados para «{texto}». Prueba con otra palabra o usa /buscar sin texto "
                "para navegar por continentes."), [[("🌍 Navegar por continentes", "c")]]
    botones = [_boton_aeropuerto(a, estado, vista) for a in resultados]
    botones.append([("🌍 Navegar por continentes", "c")])
    return f"🔎 Resultados para «{texto}»\n{LEYENDA}", botones


def pintar(db, estado, vista):
    """Devuelve (texto, botones) de la pantalla identificada por `vista`."""
    partes = vista.split(":")
    tipo = partes[0]
    try:
        if tipo == "c" and len(partes) == 3:
            return _vista_paises(db, partes[1], int(partes[2]))
        if tipo == "p" and len(partes) == 3:
            return _vista_pais(db, estado, partes[1], int(partes[2]))
        if tipo == "e" and len(partes) == 4:
            return _vista_estado(db, estado, partes[1], partes[2], int(partes[3]))
        if tipo == "s":
            return _vista_busqueda(db, estado, vista[2:])
    except ValueError:
        pass
    return _vista_continentes(db)


def iniciar(args, estado):
    """Respuesta al comando /buscar [texto]."""
    db = cargar_db()
    if db is None:
        return "La base de aeropuertos todavía no está disponible. Usa /add LEMD mientras tanto.", None
    texto = " ".join(args).strip()
    if texto:
        return _vista_busqueda(db, estado, texto[:30])
    return _vista_continentes(db)


def pulsar(data, estado):
    """
    Procesa un botón pulsado. Devuelve (texto, botones, aviso) donde aviso es
    el texto corto que Telegram muestra como notificación (o None).
    """
    db = cargar_db()
    if db is None:
        return "La base de aeropuertos no está disponible.", None, None
    aviso = None
    if data.startswith("t:"):
        icao, _, vista = data[2:].partition("|")
        if icao in estado["estaciones"]:
            quitar_estaciones(estado, [icao])
            aviso = f"🗑️ {icao} quitado"
        else:
            nombres = {a[0]: a[1] for a in db["aeropuertos"]}
            respuesta = anadir_estaciones(estado, [icao], lambda ids: {i: nombres[i] for i in ids if i in nombres})
            aviso = f"✅ {icao} añadido" if icao in estado["estaciones"] else respuesta
        data = vista
    texto, botones = pintar(db, estado, data)
    return texto, botones, aviso
