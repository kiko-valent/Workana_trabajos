"""
scheduler.py — Scheduler para ejecución diaria en Docker / EasyPanel.

Mantiene el contenedor vivo y ejecuta main.py una vez al día a la hora
configurada en UTC. Sin dependencias externas.

Ajustar RUN_HOUR_UTC según tu zona horaria:
  España invierno (CET  = UTC+1): RUN_HOUR_UTC = 9   → 10:00h local
  España verano   (CEST = UTC+2): RUN_HOUR_UTC = 8   → 10:00h local
"""

import sys
import time
import subprocess
from datetime import datetime, timedelta

# ── Configuración ─────────────────────────────────────────────────────────────
RUN_HOUR_UTC = 9    # 9 UTC = 10:00h España hora invierno
RUN_MINUTE_UTC = 0
# ──────────────────────────────────────────────────────────────────────────────


def seconds_until_next_run() -> float:
    now = datetime.utcnow()
    target = now.replace(hour=RUN_HOUR_UTC, minute=RUN_MINUTE_UTC, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_monitor():
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[scheduler] {ts} — Ejecutando main.py...", flush=True)
    result = subprocess.run([sys.executable, "main.py"])
    print(f"[scheduler] Completado con código de salida: {result.returncode}", flush=True)


print("[scheduler] Monitor de Proyectos Workana iniciado.", flush=True)
print(f"[scheduler] Ejecución programada: {RUN_HOUR_UTC:02d}:{RUN_MINUTE_UTC:02d} UTC diariamente.", flush=True)

while True:
    secs = seconds_until_next_run()
    next_dt = datetime.utcnow() + timedelta(seconds=secs)
    print(
        f"[scheduler] Próxima ejecución: {next_dt.strftime('%Y-%m-%d %H:%M UTC')} "
        f"(en {secs / 3600:.1f}h)",
        flush=True,
    )
    time.sleep(secs)
    run_monitor()
