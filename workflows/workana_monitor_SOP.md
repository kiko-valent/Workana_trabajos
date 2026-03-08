# SOP: Monitor de Proyectos Workana

## Objetivo
Recibir cada día a las 10:00h un resumen por Telegram con los proyectos nuevos publicados en Workana que coincidan con las palabras clave configuradas y tengan menos propuestas que el umbral definido.

## Cuándo se ejecuta
- Automáticamente a las 10:00h vía Task Scheduler (Windows) o cron (Mac/Linux)
- Manualmente en cualquier momento: `python main.py`

---

## Requisitos previos

### 1. Firecrawl API Key
1. Crear cuenta en https://firecrawl.dev
2. Ir a **Dashboard → API Keys**
3. Copiar la clave (empieza por `fc-`)
4. Pegarla en `.env` como `FIRECRAWL_API_KEY`

**Créditos disponibles (plan gratuito):**

| Keywords configuradas | Créditos/día | Créditos/mes | Buffer restante |
|-----------------------|-------------|-------------|-----------------|
| 3                     | 3           | 90          | 410             |
| 5                     | 5           | 150         | 350             |
| 7                     | 7           | 210         | 290             |
| 10                    | 10          | 300         | 200             |

### 2. Bot de Telegram
**Crear el bot (si aún no lo tienes):**
1. Abrir Telegram y buscar `@BotFather`
2. Enviar `/newbot`
3. Elegir nombre y username para el bot
4. Copiar el token que entrega BotFather → `TELEGRAM_BOT_TOKEN` en `.env`

**Obtener tu Chat ID:**
1. Abrir el bot recién creado en Telegram y enviarle cualquier mensaje
2. Abrir en el navegador: `https://api.telegram.org/bot{TU_TOKEN}/getUpdates`
3. Buscar el campo `"id"` dentro de `"chat"` en el JSON devuelto
4. Ese número es tu `TELEGRAM_CHAT_ID` → pegarlo en `.env`

---

## Instalación

```bash
# 1. Ir al directorio del proyecto
cd C:\Users\kiko\Desktop\Proyectos_Claude\Proyectos_Workana

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac / Linux

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Configurar credenciales
copy .env.example .env
# Editar .env con tus claves reales

# 6. Test manual
python main.py
```

---

## Configuración (config.json)

```json
{
  "keywords": ["python", "n8n", "automatización", "web scraping", "bot"],
  "max_proposals": 20,
  "workana_category": "sistemas-y-tecnologia",
  "workana_language": "es",
  "seen_projects_max_age_days": 30
}
```

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `keywords` | Palabras a buscar en Workana (una petición Firecrawl por keyword) | `["python", "n8n"]` |
| `max_proposals` | Proyectos con más propuestas se descartan | `20` |
| `workana_category` | Categoría de Workana (slug de la URL) | `"sistemas-y-tecnologia"` |
| `workana_language` | Idioma de los proyectos | `"es"` |
| `seen_projects_max_age_days` | Días que se recuerda un proyecto ya notificado | `30` |

**Categorías disponibles en Workana:**
- `sistemas-y-tecnologia` — IT y programación
- `diseno-multimedia` — Diseño
- `ventas-y-marketing` — Marketing digital
- (dejar vacío `""` para buscar en todas las categorías)

**Cambiar keywords:** Solo edita `config.json`. No toques el código.

---

## Programar ejecución automática diaria

### Windows — Task Scheduler

**Opción A: Por línea de comandos (recomendada)**

Abrir CMD como Administrador y ejecutar:
```cmd
schtasks /create /tn "Workana Monitor" /tr "\"C:\Users\kiko\Desktop\Proyectos_Claude\Proyectos_Workana\run.bat\"" /sc DAILY /st 10:00 /f
```

Verificar que se creó:
```cmd
schtasks /query /tn "Workana Monitor"
```

Ejecutar ahora para probar:
```cmd
schtasks /run /tn "Workana Monitor"
```

Eliminar la tarea (si hace falta):
```cmd
schtasks /delete /tn "Workana Monitor" /f
```

**Opción B: Por interfaz gráfica**
1. Buscar "Programador de tareas" en el menú inicio
2. Acción → Crear tarea básica
3. Nombre: `Workana Monitor`
4. Desencadenador: Diariamente a las 10:00
5. Acción: Iniciar un programa
   - Programa: `C:\Users\kiko\Desktop\Proyectos_Claude\Proyectos_Workana\run.bat`
   - Carpeta de inicio: `C:\Users\kiko\Desktop\Proyectos_Claude\Proyectos_Workana`

### Mac / Linux — Cron

```bash
# Editar crontab
crontab -e

# Añadir esta línea (sustituye /ruta/a/ por tu ruta real):
0 10 * * * cd /ruta/a/Proyectos_Workana && .venv/bin/python main.py >> .tmp/workana_monitor.log 2>&1
```

---

## Flujo de ejecución

```
Task Scheduler 10:00h
        │
        ▼
    run.bat
        │  activa .venv
        ▼
    main.py
        │
        ├─ [1/4] scrape_all_keywords()
        │     │  1 llamada Firecrawl por keyword
        │     │  Parsea markdown → lista de proyectos
        │     ▼
        │  raw_projects: list[dict]
        │
        ├─ [2/4] filter_projects()
        │     │  Descarta: proposals > max_proposals
        │     │  Descarta: URL ya en seen_projects.json
        │     ▼
        │  new_projects: list[dict]
        │
        ├─ [3/4] send_message()  ──► Telegram
        │     │  Formato HTML por proyecto
        │     │  Split automático si > 4000 chars
        │
        └─ [4/4] save_seen_projects()
              │  Añade URLs notificadas a seen_projects.json
              │  Poda entradas > 30 días
              ▼
          seen_projects.json (actualizado)
```

---

## Archivo de log

El log de ejecución se guarda en `.tmp/workana_monitor.log`.

Ver las últimas ejecuciones:
```bash
# Windows (PowerShell)
Get-Content .tmp\workana_monitor.log -Tail 50

# Mac / Linux
tail -50 .tmp/workana_monitor.log
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `FIRECRAWL_API_KEY no está configurada` | `.env` no existe o la variable está vacía | Copiar `.env.example` a `.env` y rellenar |
| `[firecrawl] Login-wall detectado` | Workana requiere login para esa búsqueda | Probar sin `category` (dejar `""`) o con otra keyword |
| Error 402 de Firecrawl | Sin créditos en el plan gratuito | Esperar al mes siguiente o reducir keywords |
| `0 proyectos encontrados` correctamente | Las keywords no tienen resultados hoy | Normal. Mañana puede haber proyectos |
| Telegram error 400 `Bad Request` | Carácter HTML inválido en el mensaje | Abrir un issue — el parser puede necesitar ajuste |
| Telegram error 401 | Token inválido | Recrear el bot en @BotFather |
| La tarea de Windows no se ejecuta | Usuario sin sesión iniciada | En las propiedades de la tarea, marcar "Ejecutar tanto si el usuario inició sesión como si no" |

---

## Ajuste del parser de Workana

Si Workana cambia su HTML y el script deja de encontrar proyectos:

1. Obtener el markdown crudo de Firecrawl (editar temporalmente `scrape_workana.py` para imprimir `markdown`)
2. Analizar cómo aparecen los enlaces `/job/` en ese markdown
3. Ajustar el regex `job_link_pattern` en `_parse_markdown()`
4. Actualizar este SOP con los cambios

---

## Mejoras futuras posibles
- Añadir más categorías de Workana en paralelo
- Filtro por presupuesto mínimo
- Enviar resumen semanal consolidado
- Integración con Google Sheets para historial
- Notificación por email como fallback de Telegram
