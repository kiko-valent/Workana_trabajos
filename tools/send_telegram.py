"""
Tool: send_telegram.py
Responsabilidad: Formatear y enviar el resumen de proyectos Workana a Telegram.

Usa HTML parse_mode (más robusto que Markdown para títulos scrapeados que
pueden contener caracteres especiales como _, *, [, ]).
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4000  # Telegram permite 4096; dejamos margen de seguridad


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Envía un mensaje de texto al chat de Telegram configurado.
    Si el texto supera MAX_MESSAGE_LENGTH, lo divide en múltiples mensajes.

    Args:
        text:       Texto del mensaje (soporta HTML)
        parse_mode: "HTML" (por defecto) o "Markdown"

    Returns:
        True si todos los mensajes se enviaron correctamente.

    Raises:
        EnvironmentError: Si faltan variables de entorno.
        requests.HTTPError: Si la API de Telegram devuelve error.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN no está configurada en .env")
    if not TELEGRAM_CHAT_ID:
        raise EnvironmentError("TELEGRAM_CHAT_ID no está configurada en .env")

    chunks = _split_message(text)
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for i, chunk in enumerate(chunks, 1):
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        if len(chunks) > 1:
            print(f"  [telegram] Mensaje {i}/{len(chunks)} enviado.")

    print(f"  [telegram] Notificación enviada al chat {TELEGRAM_CHAT_ID}")
    return True


def format_projects_message(projects: list[dict], run_date: str) -> str:
    """
    Formatea la lista de proyectos nuevos en un mensaje HTML listo para Telegram.

    Args:
        projects:  Lista de project dicts filtrados
        run_date:  Fecha en formato DD/MM/YYYY

    Returns:
        String HTML para enviar a Telegram.

    Formato por proyecto:
        <b>Título del proyecto</b>
        Descripción breve del proyecto...
        Propuestas: 5 | Presupuesto: $100-500 USD
        <a href="https://www.workana.com/job/...">Ver proyecto</a>
    """
    lines = [f"<b>Proyectos nuevos en Workana</b> — {run_date}\n"]

    for project in projects:
        title = _escape_html(project["title"])
        description = _escape_html(project.get("description", ""))
        url = project["url"]

        proposals = project.get("proposals", -1)
        proposals_str = str(proposals) if proposals >= 0 else "?"

        budget = project.get("budget", "")
        budget_str = _escape_html(budget) if budget else "No especificado"

        lines.append(f"<b>{title}</b>")
        if description:
            lines.append(description)
        lines.append(f"Propuestas: {proposals_str} | Presupuesto: {budget_str}")
        lines.append(f'<a href="{url}">Ver proyecto</a>')
        lines.append("---")

    lines.append(f"\nTotal: {len(projects)} proyecto(s) nuevo(s)")
    return "\n".join(lines)


def _split_message(text: str) -> list[str]:
    """
    Divide el mensaje en chunks de MAX_MESSAGE_LENGTH caracteres,
    intentando cortar en separadores '---' para no partir proyectos a la mitad.
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    segments = text.split("\n---\n")
    current_chunk = ""

    for segment in segments:
        candidate = current_chunk + ("\n---\n" if current_chunk else "") + segment
        if len(candidate) > MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = segment
        else:
            current_chunk = candidate

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:MAX_MESSAGE_LENGTH]]


def _escape_html(text: str) -> str:
    """Escapa caracteres especiales HTML: &, <, >"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
