# Bot de Telegram METAR / TAF

Bot: [@MetarTafTWRbot](https://t.me/MetarTafTWRbot)

Envía a Telegram el METAR y el TAF de los aeropuertos que elijas, con datos de la API pública de
[aviationweather.gov](https://aviationweather.gov/data/api/). Funciona con GitHub Actions cada ~30 min,
así que no necesita servidor.

## Comandos
| Comando | Acción |
|---|---|
| `/buscar` | buscar aeropuertos con botones: continente → país → (región) → aeropuerto |
| `/buscar torrejon` | buscar por nombre, código OACI o IATA |
| `/add LEMD LEBL` | añadir aeropuertos (código OACI) |
| `/remove LEBL` | quitar aeropuertos |
| `/list` | ver aeropuertos y modo |
| `/modo cambios` | aviso cada vez que sale un METAR/TAF nuevo |
| `/modo diario 07:30` | un resumen al día (hora de Madrid) |
| `/ahora` | informe inmediato |

El bot se ejecuta cada ~30 min, así que el **primer** comando puede tardar en contestar.
Después se queda escuchando unos 5 min (ventana interactiva) y los botones responden al momento.

## Formato de los mensajes
Cada aeropuerto muestra la observación (METAR) y el pronóstico (TAF) explicados en español:
viento, temperatura, humedad, presión, visibilidad, fenómenos y nubes, con el código original debajo.

## Puesta en marcha
1. En Telegram habla con **@BotFather** → `/newbot` y guarda el **token**.
2. Escríbele cualquier cosa a tu bot y abre `https://api.telegram.org/bot<TOKEN>/getUpdates`:
   tu chat id es el número de `"chat":{"id": ...}`.
3. En el repo: **Settings → Secrets and variables → Actions** crea
   `TELEGRAM_BOT_TOKEN` y `ALLOWED_CHAT_ID`.
4. **Actions → METAR/TAF a Telegram → Run workflow** para la primera prueba.
5. En Telegram: `/add LEMD`, espera a la siguiente ejecución (o lánzala a mano) y te llegará el informe.

## Desarrollo local
```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
TELEGRAM_BOT_TOKEN=... ALLOWED_CHAT_ID=... python -m metar_bot.main
```

## Estructura
- `metar_bot/aviationweather.py`: cliente de la API (METAR, TAF, validación de estaciones)
- `metar_bot/telegram_api.py`: envío de mensajes y lectura de comandos (`getUpdates`)
- `metar_bot/comandos.py`: lógica de los comandos
- `metar_bot/decodificar.py`: traduce los datos de la API a texto legible
- `metar_bot/formato.py`: formato de los mensajes
- `metar_bot/buscador.py`: menús del comando /buscar
- `aeropuertos.json`: base de aeropuertos con METAR (la regenera `scripts/generar_aeropuertos.py` cada mes)
- `metar_bot/main.py`: una ejecución completa
- `estado.json`: aeropuertos, modo y último METAR/TAF enviado (lo actualiza el workflow)
