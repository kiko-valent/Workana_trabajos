"""
main.py — Orquestador del Monitor de Proyectos Workana
WAT Framework: coordina los tools en el orden correcto.

Flujo:
  [1/4] Scrape de Workana (1 llamada Firecrawl, todos los proyectos visibles)
  [2/4] Filtrar por keywords + propuestas máximas + deduplicar vs seen_projects.json
  [3/4] Enviar notificación por Telegram
  [4/4] Actualizar seen_projects.json con los proyectos notificados

Uso:
  python main.py
  O automáticamente via Task Scheduler / cron (ver workflows/workana_monitor_SOP.md)
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Forzar UTF-8 en stdout para evitar errores de encoding en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

from tools.scrape_workana import scrape_workana
from tools.filter_projects import load_seen_projects, filter_by_keywords, filter_projects, save_seen_projects
from tools.send_telegram import format_projects_message, send_message

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
SEEN_PATH = PROJECT_ROOT / "seen_projects.json"


def load_config() -> dict:
    """
    Carga y valida config.json.

    Returns:
        Dict con la configuración del usuario.

    Raises:
        SystemExit: Si el archivo no existe o tiene formato inválido.
    """
    if not CONFIG_PATH.exists():
        print(
            "[ERROR] config.json no encontrado.\n"
            "Copia el ejemplo y edita tus keywords:\n"
            "  cp config.json.example config.json  (o créalo manualmente)\n"
            "Consulta workflows/workana_monitor_SOP.md para más detalles."
        )
        sys.exit(1)

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] config.json tiene formato JSON inválido: {e}")
        sys.exit(1)

    # Validaciones básicas
    if not isinstance(config.get("keywords"), list) or not config["keywords"]:
        print("[ERROR] config.json: 'keywords' debe ser una lista no vacía.")
        sys.exit(1)
    if not isinstance(config.get("max_proposals"), int) or config["max_proposals"] < 0:
        print("[ERROR] config.json: 'max_proposals' debe ser un entero >= 0.")
        sys.exit(1)

    return config


def run_monitor():
    print("=" * 55)
    print("  Monitor de Proyectos Workana")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 55)

    # ── Cargar configuración ──────────────────────────────────────────────────
    config = load_config()
    keywords = config["keywords"]
    max_proposals = config["max_proposals"]
    language = config.get("workana_language", "es")
    max_age_days = config.get("seen_projects_max_age_days", 30)

    print(f"\n  Keywords: {keywords}")
    print(f"  Max propuestas: {max_proposals}")
    print(f"  Idioma: {language}")

    # ── [1/4] Scraping (1 crédito Firecrawl) ─────────────────────────────────
    print(f"\n[1/4] Scrapeando Workana (1 llamada Firecrawl)...")
    try:
        raw_projects = scrape_workana(language)
    except Exception as e:
        print(f"\n[ERROR] Fallo en el scraping: {e}")
        sys.exit(1)

    print(f"      Total extraídos: {len(raw_projects)} proyecto(s)")

    if not raw_projects:
        print(
            "\n  No se encontraron proyectos. Posibles causas:\n"
            "  - Workana bloqueó la petición\n"
            "  - Error de red o respuesta vacía"
        )
        print("=" * 55)
        return

    # ── [2/4] Filtrado por keywords + propuestas + deduplicación ─────────────
    print(f"\n[2/4] Filtrando por keywords, propuestas y deduplicando...")
    # 2a. Filtro por keywords (local, sin coste)
    keyword_matches = filter_by_keywords(raw_projects, keywords)

    # 2b. Filtro por propuestas + deduplicación contra historial
    seen_urls: set[str] = set()
    seen_raw: dict = {}

    try:
        seen_urls, seen_raw = load_seen_projects(str(SEEN_PATH), max_age_days)
        print(f"      Historial cargado: {len(seen_urls)} URL(s) ya notificadas")
    except Exception as e:
        print(f"  [ADVERTENCIA] No se pudo cargar seen_projects.json: {e}. Continuando sin historial.")

    new_projects = filter_projects(keyword_matches, seen_urls, max_proposals)
    print(f"      Proyectos nuevos: {len(new_projects)}")

    if not new_projects:
        print("\n  Sin proyectos nuevos que notificar hoy.")
        print("=" * 55)
        return

    # ── [3/4] Envío Telegram ─────────────────────────────────────────────────
    print(f"\n[3/4] Enviando {len(new_projects)} proyecto(s) por Telegram...")
    run_date = datetime.now().strftime("%d/%m/%Y")
    message = format_projects_message(new_projects, run_date)

    try:
        send_message(message)
    except Exception as e:
        print(f"\n[ERROR] Fallo al enviar Telegram: {e}")
        sys.exit(1)

    # ── [4/4] Actualizar historial ────────────────────────────────────────────
    print("\n[4/4] Actualizando historial de proyectos notificados...")
    new_urls = [p["url"] for p in new_projects]
    try:
        save_seen_projects(str(SEEN_PATH), new_urls, seen_raw)
    except Exception as e:
        # No-fatal: worst case, mañana habrá duplicados pero la notificación
        # de hoy ya se envió correctamente.
        print(f"  [ADVERTENCIA] No se pudo guardar seen_projects.json: {e}")

    print("\n" + "=" * 55)
    print(f"  Proceso completado. {len(new_projects)} proyecto(s) notificado(s).")
    print("=" * 55)


if __name__ == "__main__":
    run_monitor()
