import re
from datetime import date
from typing import TypedDict

from tabulate import tabulate

from src.util.database import DataBase


class ActivityDemand(TypedDict):
    id: int
    category: str
    level: str
    installation: str | None
    available_places: int
    confirmed_registrations: int
    waiting_list: int
    total_demand: int
    balance: str


class DemandReport(TypedDict):
    season: str
    most_demanded: list[ActivityDemand]
    least_demanded: list[ActivityDemand]


def _season_for_activity_start(value: str) -> str | None:
    try:
        activity_start = date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"La fecha de inicio de actividad no es válida: {value!r}."
        ) from None
    if activity_start.isoformat() != value:
        raise ValueError(
            f"La fecha de inicio de actividad no es válida: {value!r}."
        )

    if activity_start.month >= 10:
        return f"{activity_start.year}-{activity_start.year + 1}"
    if activity_start.month <= 6:
        return f"{activity_start.year - 1}-{activity_start.year}"
    return None


def get_activity_seasons(database: DataBase) -> list[str]:
    rows = database.executeQuery(
        "SELECT DISTINCT start_date FROM activity WHERE start_date IS NOT NULL"
    )
    seasons = {
        season
        for row in rows
        if (season := _season_for_activity_start(row["start_date"])) is not None
    }
    return sorted(seasons, reverse=True)


def get_activity_demand_report(
    database: DataBase, season: str, limit: int = 5
) -> DemandReport:
    match = re.fullmatch(r"(\d{4})-(\d{4})", season)
    if match is None or int(match.group(2)) != int(match.group(1)) + 1:
        raise ValueError("La temporada debe tener el formato AAAA-AAAA.")
    if limit <= 0:
        raise ValueError("El límite de actividades debe ser mayor que cero.")

    start_year = int(match.group(1))
    activities = database.executeQuery(
        """
        SELECT
            activity.id,
            activity.category,
            activity.level,
            installation.name AS installation,
            activity.available_places,
            COUNT(CASE WHEN inscripcion.estado = 'confirmado' THEN 1 END)
                AS confirmed_registrations,
            COUNT(CASE WHEN inscripcion.estado = 'lista de espera' THEN 1 END)
                AS waiting_list
        FROM activity
        LEFT JOIN installation ON installation.id = activity.installation_id
        LEFT JOIN inscripcion ON inscripcion.activity_id = activity.id
        WHERE activity.start_date >= ?
          AND activity.start_date < ?
        GROUP BY
            activity.id,
            activity.category,
            activity.level,
            installation.name,
            activity.available_places
        """,
        date(start_year, 10, 1).isoformat(),
        date(start_year + 1, 7, 1).isoformat(),
    )

    ranked: list[ActivityDemand] = []
    for activity in activities:
        confirmed = int(activity["confirmed_registrations"])
        waiting = int(activity["waiting_list"])
        demand = confirmed + waiting
        capacity = int(activity["available_places"])
        balance = (
            "Satisfecho"
            if confirmed == capacity and waiting == 0
            else "Falta de plazas"
            if demand > capacity
            else "Sobreoferta"
            if demand < capacity
            else "Equilibrio"
        )
        ranked.append(
            {
                "id": int(activity["id"]),
                "category": str(activity["category"]),
                "level": str(activity["level"]),
                "installation": activity["installation"],
                "available_places": capacity,
                "confirmed_registrations": confirmed,
                "waiting_list": waiting,
                "total_demand": demand,
                "balance": balance,
            }
        )

    most_demanded = sorted(
        ranked, key=lambda activity: (-activity["total_demand"], activity["id"])
    )[:limit]
    least_demanded = sorted(
        ranked, key=lambda activity: (activity["total_demand"], activity["id"])
    )[:limit]
    return {
        "season": season,
        "most_demanded": most_demanded,
        "least_demanded": least_demanded,
    }


def iniciar_informe_demanda(database: DataBase) -> None:
    seasons = get_activity_seasons(database)
    if not seasons:
        print("No hay actividades con fecha de inicio en una temporada octubre-junio.")
        return

    print("\nTEMPORADAS DISPONIBLES")
    for index, season in enumerate(seasons, start=1):
        print(f"{index}. {season}")

    selection = input("Selecciona una temporada: ").strip()
    try:
        season_index = int(selection) - 1
    except ValueError:
        print("Introduce un número de temporada válido.")
        return
    if not 0 <= season_index < len(seasons):
        print("No existe esa temporada.")
        return

    report = get_activity_demand_report(database, seasons[season_index])
    print(f"\nDEMANDA DE ACTIVIDADES - TEMPORADA {report['season']}")
    _print_activity_ranking("TOP 5 MÁS DEMANDADAS", report["most_demanded"])
    _print_activity_ranking("TOP 5 MENOS DEMANDADAS", report["least_demanded"])


def _print_activity_ranking(
    title: str, activities: list[ActivityDemand]
) -> None:
    if not activities:
        print(f"\n{title}")
        print("No hay actividades para esta temporada.")
        return

    headers = [
        "ID",
        "Actividad",
        "Nivel",
        "Instalación",
        "Plazas ofertadas",
        "Inscripciones confirmadas",
        "Lista de espera",
        "Demanda total",
        "Balance",
    ]
    rows = [
        [
            activity["id"],
            activity["category"],
            activity["level"],
            activity["installation"] or "Sin asignar",
            activity["available_places"],
            activity["confirmed_registrations"],
            activity["waiting_list"],
            activity["total_demand"],
            activity["balance"],
        ]
        for activity in activities
    ]
    formatted_table = tabulate(
        rows,
        headers=headers,
        tablefmt="grid",
        colalign=("left",) * len(headers),
        headersglobalalign="left",
    )
    table_width = len(formatted_table.splitlines()[0])
    print(f"\n{title.center(table_width, '=')}")
    print(formatted_table)
