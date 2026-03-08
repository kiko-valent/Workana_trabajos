"""
Tool: scrape_workana.py
Responsabilidad: Hacer scraping de Workana via Firecrawl y parsear los proyectos.

Estrategia (1 crédito por llamada):
  - Una sola llamada a Firecrawl para https://www.workana.com/jobs?language=es
  - El filtrado se hace localmente en Python (sin coste adicional)

Estructura del markdown de Workana (ejemplo real):
  ## [Título del Proyecto](https://www.workana.com/job/slug?ref=projects_1)
  Published: 11 hours agoBids: 4
  Descripción breve del proyecto... [View more](...)
  USD 500 - 1,000
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"


def scrape_workana(language: str = "es") -> list[dict]:
    """
    Scrapeea la página principal de proyectos de Workana (1 crédito Firecrawl).
    Devuelve todos los proyectos visibles sin filtrar.

    Args:
        language: Código de idioma para la URL de Workana (por defecto "es")

    Returns:
        Lista de project dicts con keys:
          title            (str)
          description      (str)
          proposals        (int, -1 si no disponible)
          budget           (str, vacío si no disponible)
          url              (str, URL limpia sin ?ref=)
          hours_published  (int, horas desde publicación; -1 si no disponible)

    Raises:
        EnvironmentError: FIRECRAWL_API_KEY no configurada.
        requests.HTTPError: Error de la API de Firecrawl (e.g. 402 sin créditos).
    """
    if not FIRECRAWL_API_KEY:
        raise EnvironmentError("FIRECRAWL_API_KEY no está configurada en .env")

    url = f"https://www.workana.com/jobs?language={language}"
    print(f"  [firecrawl] Scrapeando: {url}")

    resp = requests.post(
        FIRECRAWL_URL,
        headers={
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        },
        timeout=60,
    )
    resp.raise_for_status()

    data = resp.json()
    markdown = data.get("data", {}).get("markdown", "")

    if not markdown or len(markdown) < 500:
        print(f"  [firecrawl] Respuesta demasiado corta ({len(markdown)} chars). Posible bloqueo.")
        return []

    projects = _parse_markdown(markdown)
    print(f"  [firecrawl] {len(projects)} proyecto(s) extraídos de la página.")
    return projects


def _parse_markdown(markdown: str) -> list[dict]:
    """
    Parsea el markdown de Workana y extrae todos los proyectos.

    Patrón real de cada proyecto en el markdown de Workana:
      ## [Título](https://www.workana.com/job/slug?ref=projects_1)
      Published: X hours agoBids: N
      Descripción... [View more](...)
      [Skill1](...) [Skill2](...)
      USD XXX - YYY
    """
    # Encabezados de proyecto: ## [Título](URL /job/)
    job_pattern = re.compile(
        r"^## \[([^\]]+)\]\((https://www\.workana\.com/job/[^\)]+)\)",
        re.MULTILINE,
    )

    matches = list(job_pattern.finditer(markdown))
    if not matches:
        print("  [parser] No se encontraron proyectos con el patrón esperado.")
        return []

    projects = []

    for i, match in enumerate(matches):
        title_raw = match.group(1).strip()
        url_raw = match.group(2).strip()

        # Limpiar URL: quitar ?ref=... para que sea más limpia
        url = re.sub(r"\?ref=[^\s)]*", "", url_raw).strip()

        # Limpiar título de markdown residual
        title = re.sub(r"[*_`]", "", title_raw).strip()
        if not title or len(title) < 4:
            continue

        # Bloque de contexto entre este proyecto y el siguiente
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        context = markdown[start:end]

        proposals = _extract_bids(context)
        hours_published = _extract_hours_published(context)
        description = _extract_description(context)
        budget = _extract_budget(context)
        skills = _extract_skills(context)

        projects.append({
            "title": title,
            "description": description,
            "proposals": proposals,
            "budget": budget,
            "url": url,
            "skills": skills,
            "hours_published": hours_published,
        })

    return projects


def _extract_hours_published(context: str) -> int:
    """
    Extrae la antigüedad del proyecto desde la línea Published.
    Convierte todo a horas enteras.

    Formatos reconocidos (del markdown de Workana via Firecrawl):
      "Published: 11 hours agoBids: 4"
      "Published: 1 hour agoBids: 0"
      "Published: 2 days agoBids: 1"
      "Published: 45 minutes agoBids: 7"

    Returns:
        Horas desde la publicación (int >= 1).
        -1 si no se puede determinar.
    """
    m = re.search(
        r"Published:\s*(\d+)\s*(minute|hour|day)s?\s*ago",
        context,
        re.IGNORECASE,
    )
    if not m:
        return -1

    value = int(m.group(1))
    unit = m.group(2).lower()

    if unit == "minute":
        return 1  # menos de 1 hora → siempre pasa el filtro de 24h
    if unit == "hour":
        return value
    if unit == "day":
        return value * 24

    return -1


def _extract_bids(context: str) -> int:
    """
    Extrae el número de propuestas del contexto.
    Workana usa: "Published: X hours agoBids: N"
    Retorna -1 si no se encuentra.
    """
    m = re.search(r"Bids:\s*(\d+)", context, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return -1


def _extract_description(context: str) -> str:
    """
    Extrae la descripción del proyecto.
    Es el texto libre entre la línea Published/Bids y el [View more] o las skills.
    """
    lines = context.splitlines()
    desc_lines = []
    collecting = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Saltar la línea de metadatos Published/Bids
        if re.match(r"^Published:", line, re.IGNORECASE):
            collecting = True
            continue

        if not collecting:
            continue

        # Parar en skills ([**Skill**](...)), imágenes o acciones
        if line.startswith("[**") or line.startswith("[![") or "[Place a bid]" in line:
            break
        # Parar en presupuesto
        if re.match(r"^(USD|Less than|More than)", line, re.IGNORECASE):
            break
        # Tomar texto antes de [View more]
        if "[View more]" in line:
            text_before = line.split("[View more]")[0].strip().rstrip(".")
            if text_before and len(text_before) > 10:
                desc_lines.append(text_before)
            break

        # Saltar líneas decorativas
        if re.match(r"^[*_\-#>|\\]+$", line) or line.startswith("http"):
            continue

        desc_lines.append(line)
        if len(" ".join(desc_lines)) > 200:
            break

    description = " ".join(desc_lines).strip()
    if len(description) > 220:
        description = description[:217] + "..."
    return description


def _extract_skills(context: str) -> list[str]:
    """
    Extrae las etiquetas de skills del contexto.
    Workana las muestra como: [**Python**](...) [**Machine Learning**](...)
    """
    return re.findall(r"\[\*\*([^\]]+)\*\*\]", context)


def _extract_budget(context: str) -> str:
    """
    Extrae el presupuesto del contexto.
    Formatos de Workana:
      - "USD 500 - 1,000"
      - "USD 15 - 45 / hour"
      - "Less than USD 15 / hour"
      - "Less than USD 50"
    """
    patterns = [
        r"Less than USD [\d,]+(?: / hour)?",
        r"More than USD [\d,]+(?: / hour)?",
        r"USD [\d,]+ - [\d,]+(?: / hour)?",
        r"USD [\d,]+(?: / hour)?",
    ]
    for pattern in patterns:
        m = re.search(pattern, context, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""
