from collections.abc import Iterable, Sequence

from prettytable import PrettyTable, TableStyle


def print_table(
    title: str, field_names: Sequence[str], rows: Iterable[Sequence[object]]
) -> None:
    table = PrettyTable()
    table.title = title
    table.field_names = field_names
    table.set_style(TableStyle.DOUBLE_BORDER)
    table.align = "l"
    for row in rows:
        table.add_row(row)
    print(table)
