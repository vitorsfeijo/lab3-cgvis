from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path


COLUMNS = (
    "author",
    "title",
    "source",
    "edition",
    "year",
    "section",
    "keywords",
    "abstract",
    "page",
    "link",
)

# Resolve paths from the converter's location, not from the terminal's
# current working directory.
SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent


class TableParser(HTMLParser):
    """Reads an HTML table and converts its rows into lists of text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        # _row stores the current row; _cell stores the current cell's content.
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._header = False
        self._header_row = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            # If <tr> tags are not closed, the next <tr> starts a new row
            # and indicates that the previous row has ended.
            if self._row:
                self.rows.append(self._row)
            self._row = []
            self._header_row = False
        elif tag in ("td", "th"):
            self._cell = []
            self._header = tag == "th"
            if self._header:
                self._header_row = True

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("td", "th") and self._cell is not None:
            value = "".join(self._cell).strip()
            if self._header:
                self.headers.append(value)
            elif self._row is not None:
                self._row.append(value)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row and not self._header_row:
                self.rows.append(self._row)
            self._row = None


def toml_string(value: str) -> str:
    """Escapes a string so that it is valid in TOML format."""
    return '"' + (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    ) + '"'


def convert(input_path: Path, output_path: Path) -> int:
    # Read the file once and pass its contents to the parser.
    parser = TableParser()
    parser.feed(input_path.read_text(encoding="utf-8"))
    parser.close()

    # Use column names found in the HTML, or fall back to the known names.
    if parser.headers:
        columns = tuple(parser.headers)
    else:
        columns = COLUMNS

    # The column order must match the format expected by the project.
    if tuple(columns) != COLUMNS:
        raise ValueError(
            f"Expected columns {COLUMNS}, found {tuple(columns)}"
        )

    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for row in parser.rows:
            # [[record]] creates a new entry in the TOML array of records.
            output.write("[[record]]\n")
            # Fill incomplete rows with empty fields.
            padded = row + [""] * (len(columns) - len(row))
            for column, value in zip(columns, padded):
                # Year and page are numeric; all other fields remain text.
                if column in ("year", "page") and value.isdigit():
                    output.write(f"{column} = {int(value)}\n")
                else:
                    output.write(f"{column} = {toml_string(value)}\n")
            output.write("\n")

    return len(parser.rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an HTML table to a TOML array of records."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DATASET_DIR / "Brapci-2019-03-26.html",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DATASET_DIR / "Brapci-2019-03-26.toml",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = convert(args.input, args.output)
    print(f"Converted {count} records to {args.output}")


if __name__ == "__main__":
    main()