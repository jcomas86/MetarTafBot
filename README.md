# Bot de Telegram METAR / TAF

Bot: [@MetarTafTWRbot](https://t.me/MetarTafTWRbot)

Envía a Telegram el METAR y el TAF de los aeropuertos que elijas, con datos de la API pública de
[aviationweather.gov](https://aviationweather.gov/data/api/). Funciona con GitHub Actions cada ~15 min,
así que no necesita servidor.

## Comandos
| Comando | Acción |
|---|---|
| `/add LEMD LEBL` | añadir aeropuertos (código OACI) |
| `/remove LEBL` | quitar aeropuertos |
| `/list` | ver aeropuertos y modo |
| `/modo cambios` | aviso cada vez que sale un METAR/TAF nuevo |
| `/modo diario 07:30` | un resumen al día (hora de Madrid) |
| `/ahora` | informe inmediato |

Las respuestas llegan en la siguiente ejecución, así que pueden tardar hasta ~15 min.

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
- `metar_bot/formato.py`: formato de los mensajes
- `metar_bot/main.py`: una ejecución completa
- `estado.json`: aeropuertos, modo y último METAR/TAF enviado (lo actualiza el workflow)
