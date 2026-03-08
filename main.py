"""
main.py — Orquestador del Monitor de Proyectos Workana
WAT Framework: coordina los tools en el orden correcto.

Flujo (activado por /trabajos en Telegram):
  [1/3] Scrape de Workana (1 llamada Firecrawl, todos los proyectos visibles)
  [2/3] Filtrar: últimas 24h + máximo 4 propuestas
  [3/3] Enviar todos los resultados por Telegram (o avisar que no hay ninguno)

Uso:
  python main.py
  O via comando /trabajos en Telegram (gestionado por scheduler.py)
"""

import sys
from datetime import datetime
from dotenv import load_dotenv

# Forzar UTF-8 en stdout para evitar errores de encoding en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

from tools.scrape_workana import scrape_workana
from tools.filter_projects import filter_by_time, filter_projects
from tools.send_telegram import format_projects_message, send_message

MAX_PROPOSALS = 4
MAX_HOURS = 24
WORKANA_LANGUAGE = "es"


def run_monitor():
    print("=" * 55)
    print("  Monitor de Proyectos Workana")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 55)

    # ── [1/3] Scraping (1 crédito Firecrawl) ─────────────────────────────────
    print(f"\n[1/3] Scrapeando Workana (1 llamada Firecrawl)...")
    try:
        raw_projects = scrape_workana(WORKANA_LANGUAGE)
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

    # ── [2/3] Filtrado por tiempo y propuestas ────────────────────────────────
    print(f"\n[2/3] Filtrando: últimas {MAX_HOURS}h y máx. {MAX_PROPOSALS} propuestas...")
    time_filtered = filter_by_time(raw_projects, MAX_HOURS)
    final_projects = filter_projects(time_filtered, MAX_PROPOSALS)
    print(f"      Proyectos que pasan todos los filtros: {len(final_projects)}")

    if not final_projects:
        print("\n  Sin proyectos que notificar.")
        send_message("No hay proyectos disponibles en este momento.")
        print("=" * 55)
        return

    # ── [3/3] Envío Telegram ─────────────────────────────────────────────────
    print(f"\n[3/3] Enviando {len(final_projects)} proyecto(s) por Telegram...")
    run_date = datetime.now().strftime("%d/%m/%Y")
    message = format_projects_message(final_projects, run_date)

    try:
        send_message(message)
    except Exception as e:
        print(f"\n[ERROR] Fallo al enviar Telegram: {e}")
        sys.exit(1)

    print("\n" + "=" * 55)
    print(f"  Proceso completado. {len(final_projects)} proyecto(s) notificado(s).")
    print("=" * 55)


if __name__ == "__main__":
    run_monitor()
