"""Formatação dos menus, propostas e resultados da CLI."""

from rich import box
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from askdb.queries.models import QueryResult


def literal(value: object, *, multiline: bool = False) -> str:
    text = "NULL" if value is None else str(value)
    return "".join(
        char if char.isprintable() or (multiline and char in "\n\t") else ascii(char)[1:-1]
        for char in text
    )


class Terminal:
    def __init__(self, *, write=print, console: Console | None = None):
        self.write = write
        self.console = console if console is not None else (
            Console() if write is print else Console(width=240, color_system=None)
        )

    def render(self, content) -> None:
        if self.write is print:
            self.console.print(content)
        else:
            with self.console.capture() as capture:
                self.console.print(content)
            self.write(capture.get().rstrip("\n"))

    def line(self, text: str = "", *, style: str = "") -> None:
        self.render(Text(literal(text, multiline=True), style=style))

    def section(self, title: str) -> None:
        self.line()
        self.line(title, style="bold cyan")

    def sql(self, sql: str) -> None:
        self.render(Syntax(literal(sql, multiline=True), "sql", theme="ansi_dark",
                           background_color="default", word_wrap=True))

    def result(self, result: QueryResult) -> None:
        self.section("Resultado")
        if not result.rows:
            self.line("Nenhuma linha retornada.")
        else:
            table = Table(box=box.SIMPLE_HEAD, padding=(0, 1), header_style="bold cyan")
            for column in result.columns:
                table.add_column(Text(literal(column)))
            for row in result.rows:
                table.add_row(*(Text(literal(value)) for value in row))
            self.render(table)
        self.line(f"{len(result.rows)} linha(s) | {result.duration_ms:.1f} ms", style="dim")
        if result.truncated:
            self.line("Resultado truncado no limite configurado. A consulta não será repetida automaticamente.",
                      style="yellow")
