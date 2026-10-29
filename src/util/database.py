import sqlite3
from pathlib import Path

from src.util.unexpectedException import UnexpectedException


class DataBase:
    """Small SQLite helper shared by application services."""

    def __init__(self, name: str | Path):
        self.dbname = str(name)

    def executeScript(self, nameFile: str | Path) -> None:
        with open(nameFile, "r", encoding="utf-8") as sql_file:
            sql_script = sql_file.read()

        connection = self._connect()
        try:
            connection.executescript(sql_script)
            connection.commit()
        except sqlite3.DatabaseError as error:
            connection.rollback()
            raise UnexpectedException(str(error)) from error
        finally:
            connection.close()

    def executeQuery(self, query: str, *args: object) -> list[dict[str, object]]:
        connection = self._connect()
        try:
            cursor = connection.execute(query, args)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.DatabaseError as error:
            raise UnexpectedException(str(error)) from error
        finally:
            connection.close()

    def executeUpdateQuery(
        self, query: str, *args: object, multiple: bool = False
    ) -> int | None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            if multiple:
                cursor.executemany(query, args[0])
            else:
                cursor.execute(query, args)
            last_row_id = cursor.lastrowid
            connection.commit()
            return last_row_id
        except sqlite3.DatabaseError as error:
            connection.rollback()
            raise UnexpectedException(str(error)) from error
        finally:
            connection.close()

    def executeTransaction(
        self,
        query: str,
        args: tuple[object, ...],
        many_query: str,
        many_args: list[tuple[object, ...]],
    ) -> int | None:
        """Run an insert and its related rows atomically.

        The inserted id is prepended to each many_args row.
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(query, args)
            if cursor.rowcount == 0:
                connection.rollback()
                return None
            last_row_id = cursor.lastrowid
            cursor.executemany(
                many_query,
                [(last_row_id, *row) for row in many_args],
            )
            connection.commit()
            return last_row_id
        except sqlite3.DatabaseError as error:
            connection.rollback()
            raise UnexpectedException(str(error)) from error
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.dbname)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
