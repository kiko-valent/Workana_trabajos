"""
Tool: filter_projects.py
Responsabilidad: Filtrar proyectos por tiempo de publicación y número de propuestas.
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


def filter_by_time(projects: list[dict], max_hours: int = 24) -> list[dict]:
    """
    Mantiene solo los proyectos publicados dentro de las últimas max_hours horas.

    Proyectos con hours_published == -1 (dato no disponible) se incluyen
    para no descartar proyectos válidos por falta de dato.

    Args:
        projects:  Lista de project dicts (con clave 'hours_published')
        max_hours: Ventana de tiempo en horas (por defecto 24)

    Returns:
        Lista filtrada.
    """
    result = []
    skipped = 0

    for project in projects:
        age = project.get("hours_published", -1)
        if age == -1 or age <= max_hours:
            result.append(project)
        else:
            skipped += 1

    print(
        f"  [tiempo] {len(result)} pasan (últimas {max_hours}h) | "
        f"{skipped} descartados por antigüedad"
    )
    return result


def filter_projects(
    projects: list[dict],
    max_proposals: int,
) -> list[dict]:
    """
    Filtra proyectos por número máximo de propuestas.

    Args:
        projects:      Lista de project dicts de scrape_workana
        max_proposals: Máximo aceptable de propuestas (ej. 4)

    Returns:
        Lista filtrada.
    """
    result = []
    rejected = 0

    for project in projects:
        proposals = project["proposals"]

        # proposals == -1 significa dato no disponible: pasar el filtro
        if proposals != -1 and proposals > max_proposals:
            rejected += 1
            continue

        result.append(project)

    print(
        f"  [propuestas] {len(result)} pasan | "
        f"{rejected} descartados (>{max_proposals} propuestas)"
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
