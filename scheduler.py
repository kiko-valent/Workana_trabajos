"""
scheduler.py — Bot de Telegram para el Monitor de Proyectos Workana.

Mantiene el contenedor vivo escuchando comandos de Telegram.
Sin ejecución diaria automática: la búsqueda solo se lanza manualmente.

Comandos Telegram:
  /trabajos  — Lanza la búsqueda de proyectos en Workana.
  /respuesta — Genera una propuesta profesional para un proyecto (usa Claude API).
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

from tools.generate_proposal_response import generate_proposal

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Lock para evitar ejecuciones simultáneas si el usuario spamea /trabajos
_run_lock = threading.Lock()

# Estado de conversación para el flujo /respuesta
# {chat_id: {"step": "waiting_title" | "waiting_description", "title": str}}
_respuesta_state: dict = {}


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


def _run_main() -> None:
    """Ejecuta main.py como subproceso (aislado para evitar conflictos de estado)."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[bot] {ts} — Ejecutando main.py...", flush=True)
    result = subprocess.run([sys.executable, "main.py"])
    print(f"[bot] Completado con código de salida: {result.returncode}", flush=True)


def poll_telegram() -> None:
    """
    Escucha mensajes de Telegram con long polling.
    Cuando detecta /trabajos, lanza la búsqueda.
    """
    if not TELEGRAM_TOKEN:
        print("[bot] TELEGRAM_BOT_TOKEN no configurado, polling desactivado.", flush=True)
        return

    offset = None
    print("[bot] Escuchando comandos de Telegram (/trabajos)...", flush=True)

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=40)
            data = resp.json()
            if not data.get("ok"):
                print(f"[bot] Error de API Telegram: {data.get('description')} (código {data.get('error_code')})", flush=True)
                time.sleep(10)
                continue
            updates = data.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "") or ""
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if "/respuesta" in text.lower():
                    print("[bot] Comando /respuesta recibido.", flush=True)
                    _respuesta_state[chat_id] = {"step": "waiting_title"}
                    _send("¿Cuál es el título del proyecto?")

                elif chat_id in _respuesta_state:
                    state = _respuesta_state[chat_id]
                    if state["step"] == "waiting_title":
                        _respuesta_state[chat_id] = {"step": "waiting_description", "title": text}
                        _send("Ahora pega la descripción del proyecto:")
                    elif state["step"] == "waiting_description":
                        title = state["title"]
                        _send("⏳ Generando propuesta...")
                        del _respuesta_state[chat_id]
                        try:
                            proposal = generate_proposal(title, text)
                            _send(proposal)
                        except Exception as e:
                            print(f"[bot] Error generando propuesta: {e}", flush=True)
                            _send("❌ Error al generar la propuesta. Comprueba que ANTHROPIC_API_KEY está configurada.")

                elif "/trabajos" in text.lower():
                    print("[bot] Comando /trabajos recibido.", flush=True)
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
print("[bot] Monitor de Proyectos Workana iniciado.", flush=True)
print("[bot] Comandos disponibles: /trabajos, /respuesta", flush=True)

poll_telegram()
