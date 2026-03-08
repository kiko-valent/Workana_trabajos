"""
Tool: filter_projects.py
Responsabilidad: Filtrar proyectos por número de propuestas y deduplicar
contra el historial de proyectos ya notificados (seen_projects.json).

seen_projects.json formato interno:
  {"https://www.workana.com/job/abc": "2026-03-07T10:00:00", ...}
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


def load_seen_projects(path: str, max_age_days: int = 30) -> tuple[set[str], dict]:
    """
    Carga el conjunto de URLs ya notificados desde seen_projects.json.
    Poda entradas más antiguas que max_age_days para evitar crecimiento
    ilimitado del archivo.

    Args:
        path:         Ruta absoluta a seen_projects.json
        max_age_days: Máximo de días a conservar una entrada

    Returns:
        Tupla (set_of_urls, raw_dict):
          - set_of_urls: conjunto de URLs para lookups rápidos O(1)
          - raw_dict: dict completo {url: timestamp} para merge posterior

    Comportamiento en caso de error:
        - Archivo inexistente → (set(), {})  [primera ejecución normal]
        - JSON inválido       → (set(), {})  [log warning, no crashear]
    """
    p = Path(path)
    if not p.exists():
        return set(), {}

    try:
        raw: dict = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  [ADVERTENCIA] seen_projects.json corrupto: {e}. Ignorando historial.")
        return set(), {}

    if not isinstance(raw, dict):
        print(f"  [ADVERTENCIA] seen_projects.json con formato inesperado. Ignorando.")
        return set(), {}

    # Podar entradas antiguas
    cutoff = datetime.now() - timedelta(days=max_age_days)
    pruned: dict = {}
    pruned_count = 0

    for url, ts_str in raw.items():
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts >= cutoff:
                pruned[url] = ts_str
            else:
                pruned_count += 1
        except (ValueError, TypeError):
            # Timestamp inválido → conservar la entrada por seguridad
            pruned[url] = ts_str

    if pruned_count > 0:
        print(f"  [dedup] {pruned_count} entrada(s) antigua(s) podadas de seen_projects.json")

    return set(pruned.keys()), pruned


def filter_by_keywords(projects: list[dict], keywords: list[str]) -> list[dict]:
    """
    Mantiene solo los proyectos cuyo título o descripción contienen
    al menos una de las keywords (búsqueda insensible a mayúsculas).

    Args:
        projects: Lista completa de proyectos scrapeados
        keywords: Lista de términos de config.json

    Returns:
        Lista de proyectos que coinciden con alguna keyword.
    """
    if not keywords:
        return projects  # Sin keywords configuradas: devolver todo

    matched = []
    for project in projects:
        skills_text = " ".join(project.get("skills", []))
        text = (project["title"] + " " + project["description"] + " " + skills_text).lower()
        for kw in keywords:
            if kw.lower() in text:
                project["matched_keyword"] = kw
                matched.append(project)
                break

    print(f"  [keywords] {len(matched)}/{len(projects)} proyecto(s) coinciden con las keywords")
    return matched


def filter_projects(
    projects: list[dict],
    seen_urls: set[str],
    max_proposals: int,
) -> list[dict]:
    """
    Aplica dos filtros sobre la lista de proyectos:
      1. Descarta proyectos con proposals > max_proposals
         (proposals == -1 pasa: no se pudo extraer el dato)
      2. Descarta URLs ya presentes en seen_urls

    Args:
        projects:      Lista de project dicts de scrape_workana
        seen_urls:     Set de URLs ya notificadas
        max_proposals: Máximo aceptable de propuestas

    Returns:
        Lista filtrada de proyectos nuevos.
    """
    result = []
    stats = {"proposals_rejected": 0, "already_seen": 0, "passed": 0}

    for project in projects:
        url = project["url"]
        proposals = project["proposals"]

        # Filtro 1: propuestas
        if proposals != -1 and proposals > max_proposals:
            stats["proposals_rejected"] += 1
            continue

        # Filtro 2: ya notificado
        if url in seen_urls:
            stats["already_seen"] += 1
            continue

        stats["passed"] += 1
        result.append(project)

    print(
        f"  [filtro] {stats['passed']} pasan | "
        f"{stats['proposals_rejected']} descartados por propuestas | "
        f"{stats['already_seen']} ya vistos"
    )
    return result


def save_seen_projects(path: str, new_urls: list[str], existing_raw: dict) -> None:
    """
    Persiste las nuevas URLs notificadas en seen_projects.json.
    Hace merge con las entradas existentes (conservando sus timestamps).

    Args:
        path:         Ruta absoluta a seen_projects.json
        new_urls:     URLs a añadir (recién notificadas)
        existing_raw: Dict {url: timestamp} cargado previamente
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    now_str = datetime.now().isoformat(timespec="seconds")
    merged = dict(existing_raw)  # copia para no mutar el original

    for url in new_urls:
        merged[url] = now_str

    p.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [dedup] seen_projects.json actualizado: {len(merged)} entrada(s) totales")
