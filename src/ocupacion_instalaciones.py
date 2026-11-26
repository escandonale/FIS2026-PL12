from typing import TypedDict

from src.util.database import DataBase
from src.util.pretty_tables import print_table


WEEKDAYS = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)

TIME_BANDS = {
    "1": ("Mañana", 9, 12),
    "2": ("Mediodía", 13, 17),
    "3": ("Tarde", 18, 22),
}


class HourOccupancy(TypedDict):
    hour: str
    occupied_days: int
    occupancy_percentage: float


class DayOccupancy(TypedDict):
    weekday: str
    occupied_hours: int
    occupancy_percentage: float


class OccupancyReport(TypedDict):
    installation: str
    time_band: str
    weekdays: list[str]
    hours: list[str]
    grid: dict[str, dict[str, list[str]]]
    hourly_occupancy: list[HourOccupancy]
    daily_occupancy: list[DayOccupancy]
    busiest_hours: list[str]
    busiest_days: list[str]


def get_installation_occupancy_report(
    database: DataBase, installation_id: int, time_band: str
) -> OccupancyReport:
    selected_band = next(
        (band for band in TIME_BANDS.values() if band[0] == time_band),
        None,
    )
    if selected_band is None:
        raise ValueError("La franja horaria seleccionada no es válida.")
    if type(installation_id) is not int or installation_id <= 0:
        raise ValueError("El identificador del espacio debe ser un entero positivo.")

    installation = database.executeQuery(
        "SELECT name FROM installation WHERE id = ?",
        installation_id,
    )
    if not installation:
        raise ValueError("No existe el espacio seleccionado.")

    _, first_hour, final_hour = selected_band
    hours = [
        f"{hour:02d}:00-{hour + 1:02d}:00"
        for hour in range(first_hour, final_hour)
    ]
    grid = {
        weekday: {hour: [] for hour in hours}
        for weekday in WEEKDAYS
    }

    activities = database.executeQuery(
        """
        SELECT
            activity.id,
            activity.category,
            activity.level,
            activity.start_time,
            activity.end_time,
            activity_day.weekday
        FROM activity
        JOIN activity_day ON activity_day.activity_id = activity.id
        WHERE activity.installation_id = ?
          AND activity.start_time < ?
          AND activity.end_time > ?
        ORDER BY activity.id, activity_day.weekday
        """,
        installation_id,
        f"{final_hour:02d}:00",
        f"{first_hour:02d}:00",
    )

    for activity in activities:
        weekday = str(activity["weekday"])
        label = (
            f"{activity['category']} - {activity['level']} "
            f"(actividad {activity['id']})"
        )
        for hour in range(first_hour, final_hour):
            slot_start = f"{hour:02d}:00"
            slot_end = f"{hour + 1:02d}:00"
            if (
                str(activity["start_time"]) < slot_end
                and str(activity["end_time"]) > slot_start
            ):
                grid[weekday][f"{slot_start}-{slot_end}"].append(label)

    hourly_occupancy: list[HourOccupancy] = []
    for hour in hours:
        occupied_days = sum(bool(grid[weekday][hour]) for weekday in WEEKDAYS)
        hourly_occupancy.append(
            {
                "hour": hour,
                "occupied_days": occupied_days,
                "occupancy_percentage": round(
                    occupied_days / len(WEEKDAYS) * 100,
                    1,
                ),
            }
        )

    daily_occupancy: list[DayOccupancy] = []
    for weekday in WEEKDAYS:
        occupied_hours = sum(bool(grid[weekday][hour]) for hour in hours)
        daily_occupancy.append(
            {
                "weekday": weekday,
                "occupied_hours": occupied_hours,
                "occupancy_percentage": round(
                    occupied_hours / len(hours) * 100,
                    1,
                ),
            }
        )

    occupied_hour_percentages = [
        entry["occupancy_percentage"] for entry in hourly_occupancy
    ]
    occupied_day_percentages = [
        entry["occupancy_percentage"] for entry in daily_occupancy
    ]
    max_hour_occupancy = max(occupied_hour_percentages, default=0)
    max_day_occupancy = max(occupied_day_percentages, default=0)
    busiest_hours = (
        [
            entry["hour"]
            for entry in hourly_occupancy
            if entry["occupancy_percentage"] == max_hour_occupancy
        ]
        if max_hour_occupancy > 0
        else []
    )
    busiest_days = (
        [
            entry["weekday"]
            for entry in daily_occupancy
            if entry["occupancy_percentage"] == max_day_occupancy
        ]
        if max_day_occupancy > 0
        else []
    )

    return {
        "installation": str(installation[0]["name"]),
        "time_band": time_band,
        "weekdays": list(WEEKDAYS),
        "hours": hours,
        "grid": grid,
        "hourly_occupancy": hourly_occupancy,
        "daily_occupancy": daily_occupancy,
        "busiest_hours": busiest_hours,
        "busiest_days": busiest_days,
    }


def print_installation_occupancy_report(report: OccupancyReport) -> None:
    grid_rows = [
        [
            hour,
            *[
                " / ".join(report["grid"][weekday][hour]) or "Disponible"
                for weekday in report["weekdays"]
            ],
        ]
        for hour in report["hours"]
    ]
    print_table(
        f"OCUPACIÓN SEMANAL - {report['installation']} - {report['time_band']}",
        ["Hora", *report["weekdays"]],
        grid_rows,
    )
    print_table(
        "OCUPACIÓN POR HORA",
        ["Hora", "Días ocupados", "Ocupación"],
        [
            [
                entry["hour"],
                f"{entry['occupied_days']}/{len(report['weekdays'])}",
                f"{entry['occupancy_percentage']:.1f}%",
            ]
            for entry in report["hourly_occupancy"]
        ],
    )
    print_table(
        "OCUPACIÓN POR DÍA",
        ["Día", "Horas ocupadas", "Ocupación"],
        [
            [
                entry["weekday"],
                f"{entry['occupied_hours']}/{len(report['hours'])}",
                f"{entry['occupancy_percentage']:.1f}%",
            ]
            for entry in report["daily_occupancy"]
        ],
    )
    print_table(
        "TENDENCIA DE OCUPACIÓN",
        ["Tramo horario más ocupado", "Día(s) más ocupado(s)"],
        [[
            ", ".join(report["busiest_hours"]) or "Sin ocupación programada",
            ", ".join(report["busiest_days"]) or "Sin ocupación programada",
        ]],
    )


def iniciar_consulta_ocupacion(database: DataBase) -> None:
    installations = database.executeQuery(
        "SELECT id, name FROM installation ORDER BY name"
    )
    if not installations:
        print("No hay espacios disponibles para consultar.")
        return

    print_table(
        "ESPACIOS DISPONIBLES",
        ["ID", "Espacio"],
        [[installation["id"], installation["name"]] for installation in installations],
    )
    installation_ids = {int(installation["id"]) for installation in installations}
    while True:
        try:
            installation_id = int(input("Introduce el ID del espacio: ").strip())
        except ValueError:
            print("El ID del espacio debe ser un número entero.")
            continue
        if installation_id in installation_ids:
            break
        print("No existe un espacio con ese ID.")

    band_options = [
        [option, f"{name} ({start:02d}:00-{end:02d}:00)"]
        for option, (name, start, end) in TIME_BANDS.items()
    ]
    print_table("FRANJAS HORARIAS", ["Opción", "Franja"], band_options)
    while True:
        selection = input("Selecciona una franja horaria: ").strip()
        if selection in TIME_BANDS:
            time_band = TIME_BANDS[selection][0]
            break
        print("Selecciona una opción de franja válida.")

    report = get_installation_occupancy_report(
        database,
        installation_id,
        time_band,
    )
    print_installation_occupancy_report(report)
