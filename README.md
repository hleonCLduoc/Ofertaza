# Monitor de precios (Falabella — Fase 0/1)

Detecta posibles **errores de precio** (no ofertas normales) en Falabella,
comparando cada precio nuevo contra el historial del mismo producto.

## Cómo funciona

- `src/scraper.py` busca en Falabella (`?Ntt=<término>&page=N`) los términos
  definidos en `src/config.py` (`SEARCH_TERMS`), leyendo el JSON `__NEXT_DATA__`
  que el sitio ya trae embebido en el HTML (no requiere navegador headless).
- Cada precio se guarda en SQLite (`price_observations`).
- `src/detect.py` compara el precio nuevo contra la mediana de sus últimas
  observaciones. Alerta si:
  - cae más de `DROP_THRESHOLD` (55% por defecto) respecto a la mediana, o
  - es ~1/10 o ~1/100 de la mediana (típico error de "falta un dígito").
- Un producto necesita al menos `MIN_HISTORY_FOR_ALERT` (3) observaciones
  previas antes de poder generar una alerta (evita falsos positivos en frío).
- `src/notify.py` manda la alerta a Telegram si `TELEGRAM_BOT_TOKEN` y
  `TELEGRAM_CHAT_ID` están configurados; si no, solo queda en el log.

El contenedor corre en loop infinito: un ciclo completo (todos los términos)
cada `CYCLE_INTERVAL_SECONDS` (1800s = 30 min por defecto).

## Desplegar en el VPS

### 1. Subir el código a un repo remoto (desde tu máquina local)

```bash
cd "C:/Users/hug.leon/Documents/SCRAP"
git remote add origin <URL_DE_TU_REPO>   # ej: git@github.com:usuario/precio-monitor.git
git push -u origin master
```

### 2. En el VPS (por SSH)

```bash
git clone <URL_DE_TU_REPO> precio-monitor
cd precio-monitor
cp .env.example .env
nano .env   # completa TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (opcional por ahora)
docker compose up -d --build
```

### 3. Verificar que está corriendo

```bash
docker compose logs -f precio-monitor-falabella
```

Deberías ver líneas tipo:

```
INFO 'notebook': 1395 productos en 30 páginas
INFO Ciclo completo: 5000 productos revisados, 0 alertas generadas
INFO Durmiendo 1500 segundos hasta el próximo ciclo
```

Los datos persisten en `./data/precios.db` (montado como volumen), así que
`docker compose restart` o un `git pull` + rebuild no pierden el historial.

### Actualizar tras un cambio de código

```bash
git pull
docker compose up -d --build
```

## Configurar el bot de Telegram (opcional, para alertas push)

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram, `/newbot`,
   sigue las instrucciones y copia el token que te da.
2. Escríbele un mensaje cualquiera a tu bot recién creado (para que pueda
   escribirte de vuelta).
3. Obtén tu `chat_id`: abre en el navegador
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` después del paso 2,
   y busca el campo `"chat":{"id": ...}`.
4. Pon `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env` y reinicia el
   contenedor (`docker compose up -d`).

## Próximos pasos (fuera del alcance de esta fase)

- Sumar Paris, Ripley, PC Factory, Sodimac, La Polar (cada uno con su propio
  parser, ya que la estructura HTML/JSON cambia por sitio).
- Excluir explícitamente tiendas que resulten muy confiables/sin errores.
- Comparación cross-tienda del mismo producto (más compleja: requiere
  matchear productos entre sitios).
- Ajustar `DROP_THRESHOLD` / `DIGIT_ERROR_TOLERANCE` según cuántos falsos
  positivos veamos en la práctica.
