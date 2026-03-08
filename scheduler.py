"""
scheduler.py — Scheduler para ejecución diaria en Docker / EasyPanel.

Mantiene el contenedor vivo y ejecuta main.py una vez al día a la hora
configurada en UTC. Sin dependencias externas.

Ajustar RUN_HOUR_UTC según tu zona horaria:
  España invierno (CET  = UTC+1): RUN_HOUR_UTC = 9   → 10:00h local
  España verano   (CEST = UTC+2): RUN_HOUR_UTC = 8   → 10:00h local

Comando Telegram:
  Escribe ./trabajos en el chat para lanzar la búsqueda manualmente.
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuración scheduler ────────────────────────────────────────────────────
RUN_HOUR_UTC = 9    # 9 UTC = 10:00h España hora invierno
RUN_MINUTE_UTC = 0
# ──────────────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Lock para evitar ejecuciones simultáneas (scheduler + comando manual)
_run_lock = threading.Lock()


def _send(text: str) -> None:
    """Envía un mensaje de texto al chat configurado."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def seconds_until_next_run() -> float:
    now = datetime.utcnow()
    target = now.replace(hour=RUN_HOUR_UTC, minute=RUN_MINUTE_UTC, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _run_main() -> None:
    """Ejecuta main.py como subproceso (aislado para evitar conflictos de estado)."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[scheduler] {ts} — Ejecutando main.py...", flush=True)
    result = subprocess.run([sys.executable, "main.py"])
    print(f"[scheduler] Completado con código de salida: {result.returncode}", flush=True)


def run_monitor() -> None:
    """Lanza _run_main() con lock para evitar ejecuciones paralelas."""
    if _run_lock.acquire(blocking=False):
        try:
            _run_main()
        finally:
            _run_lock.release()
    else:
        print("[scheduler] Ya hay una ejecución en curso, saltando.", flush=True)


def poll_telegram() -> None:
    """
    Escucha mensajes de Telegram con long polling.
    Cuando detecta './trabajos', lanza la búsqueda manualmente.
    """
    if not TELEGRAM_TOKEN:
        print("[bot] TELEGRAM_BOT_TOKEN no configurado, polling desactivado.", flush=True)
        return

    offset = None
    print("[bot] Escuchando comandos de Telegram (./trabajos)...", flush=True)

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=40)
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                text = update.get("message", {}).get("text", "") or ""
                if "./trabajos" in text.lower():
                    print("[bot] Comando ./trabajos recibido.", flush=True)
                    _send("🔍 Buscando trabajos en Workana...")
                    if _run_lock.acquire(blocking=False):
                        try:
                            _run_main()
                        finally:
                            _run_lock.release()
                    else:
                        _send("⏳ Ya hay una búsqueda en curso, espera un momento.")

        except Exception as e:
            print(f"[bot] Error en polling: {e}", flush=True)
            time.sleep(5)


# ── Arranque ───────────────────────────────────────────────────────────────────
print("[scheduler] Monitor de Proyectos Workana iniciado.", flush=True)
print(f"[scheduler] Ejecución programada: {RUN_HOUR_UTC:02d}:{RUN_MINUTE_UTC:02d} UTC diariamente.", flush=True)

bot_thread = threading.Thread(target=poll_telegram, daemon=True, name="telegram-poll")
bot_thread.start()

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
