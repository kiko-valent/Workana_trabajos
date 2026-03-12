"""
generate_proposal_response.py — Genera una propuesta profesional para Workana usando Claude API.

Dado el título y la descripción de un proyecto, devuelve un texto listo para enviar
como propuesta: presentación, enfoque técnico y preguntas para el cliente.
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_PROFILE = """
Desarrollador Python con dos años de experiencia en:
1. Automatizaciones y bots de Telegram
2. Web scraping con Firecrawl y Scrapy
3. Creación de agentes de IA para WhatsApp enfocados en asistentes para comercios y rastreo de pedidos
4. Desarrollo de RAG (Retrieval-Augmented Generation)
""".strip()

_SYSTEM_PROMPT = f"""Eres un asistente especializado en redactar propuestas profesionales para la plataforma Workana.
Escribe siempre en español, con tono profesional pero cercano y directo.

Perfil del candidato:
{_PROFILE}

Cuando recibas el título y la descripción de un proyecto, genera una propuesta con exactamente estas tres secciones en texto plano (sin markdown):

Presentación:
[2-3 frases. Muestra interés genuino y conecta brevemente tu experiencia con las necesidades del cliente.]

¿Cómo lo haría?:
[4-6 frases. Describe el enfoque técnico concreto: qué herramientas usarías, cómo estructurarías la solución. Sé específico para demostrar que entiendes el proyecto.]

Preguntas:
[Exactamente 2 preguntas inteligentes que demuestren que has leído con atención la descripción y que ayuden a entender mejor el alcance o los requisitos.]

Extensión máxima: 350 palabras."""


def generate_proposal(title: str, description: str) -> str:
    """
    Genera una propuesta profesional para un proyecto de Workana.

    Args:
        title: Título del proyecto.
        description: Descripción del proyecto.

    Returns:
        Texto de la propuesta generada por Claude.

    Raises:
        Exception: Si la llamada a la API falla.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Título del proyecto: {title}\n\nDescripción: {description}",
            }
        ],
    )
    return message.content[0].text
