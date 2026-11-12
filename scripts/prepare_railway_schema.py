"""Convert a MySQL Workbench structure-only dump to a safe Railway bootstrap.

The input must be a structure-only mysqldump (no INSERT statements). The output
contains CREATE TABLE, TRIGGER, PROCEDURE and VIEW statements only; it strips
DROP statements and the local DEFINER account, and removes mysqldump's temporary
placeholder views. It must be imported only into an empty target database.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


def extract_schema(source: str) -> str:
    if re.search(r"(?m)^-- Dumping data for table `[^`]+`", source):
        raise ValueError("Input contains table data. Supply a structure-only export, not a data dump.")

    tables = re.findall(
        r"(?ms)^CREATE TABLE `[^`]+` \(.*?^\) ENGINE=.*?;$",
        source,
    )

    pre_routines = source.split("-- Dumping routines for database", 1)[0]
    triggers = []
    for match in re.finditer(r"(?ms)^DELIMITER ;;\s*(.*?)\s*;;\s*DELIMITER ;", pre_routines):
        chunk = match.group(1).strip()
        if "TRIGGER" not in chunk:
            continue
        chunk = re.sub(r"/\*!\d+\s*CREATE\s*\*/", "CREATE", chunk)
        chunk = re.sub(r"/\*!\d+\s*DEFINER=.*?\*/", "", chunk)
        chunk = re.sub(r"/\*!\d+\s*(TRIGGER\b.*?END)\s*\*/", r"\1", chunk, flags=re.S)
        triggers.append(re.sub(r"\s+", " ", chunk).strip())

    if "-- Dumping routines for database" not in source:
        raise ValueError("Could not find the mysqldump routines section.")
    routine_region = source.split("-- Dumping routines for database", 1)[1]
    routines = []
    routine_pattern = (
        r"(?ms)^DELIMITER ;;\s*(CREATE DEFINER=.*?PROCEDURE `[^`]+`\s*\(.*?\n"
        r"END(?:\s+\w+)?\s*)\s*;;\s*DELIMITER ;"
    )
    for match in re.finditer(routine_pattern, routine_region):
        chunk = match.group(1).strip()
        chunk = re.sub(r"^CREATE DEFINER=`[^`]+`@`[^`]+`", "CREATE", chunk, count=1)
        routines.append(re.sub(r"\s+", " ", chunk).strip())

    views = []
    section_pattern = r"(?m)^-- Final view structure for view `([^`]+)`\s*$"
    sections = list(re.finditer(section_pattern, source))
    for index, section in enumerate(sections):
        name = section.group(1)
        body_end = sections[index + 1].start() if index + 1 < len(sections) else len(source)
        body = source[section.end():body_end]
        view_match = re.search(r"/\*!50001\s+VIEW `[^`]+` AS (.*?)\s*\*/;", body, flags=re.S)
        if not view_match:
            raise ValueError(f"Could not parse final definition for view {name}.")
        select_sql = view_match.group(1).strip()
        views.append(
            f"CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `{name}` AS {select_sql};"
        )

    expected = {"tables": 15, "triggers": 14, "procedures": 11, "views": 7}
    actual = {"tables": len(tables), "triggers": len(triggers), "procedures": len(routines), "views": len(views)}
    if actual != expected:
        raise ValueError(f"Unexpected schema object counts. Expected {expected}; found {actual}.")

    output = [
        "-- AIIMS Connect: structure-only bootstrap for an EMPTY MySQL 8.0+ database.",
        "-- No patient rows, credentials, appointments or transaction data are included.",
        "-- No DROP statements are generated. Never import over an existing database.",
        "-- In Workbench, select the empty target schema before executing this file.",
        "-- The account importing this file becomes the definer for its routines/views/triggers.",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
        "\n\n".join(tables),
        "",
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
        "DELIMITER $$",
        "\n\n".join(trigger + "$$" for trigger in triggers),
        "DELIMITER ;",
        "",
        "DELIMITER $$",
        "\n\n".join(routine + "$$" for routine in routines),
        "DELIMITER ;",
        "",
        "\n\n".join(views),
        "",
        "-- Bootstrap completed.",
    ]
    result = "\n\n".join(output) + "\n"
    if re.search(r"(?im)^\s*DROP\s+", result):
        raise ValueError("Internal safety check failed: DROP statement found in generated SQL.")
    if re.search(r"`[^`]+`@`[^`]+`", result):
        raise ValueError("Internal safety check failed: explicit DEFINER account remains.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to the structure-only mysqldump file")
    parser.add_argument("output", type=Path, help="path for the safe bootstrap SQL file")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")

    try:
        source = args.input.read_text(encoding="utf-8-sig")
        generated = extract_schema(source)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Schema export preparation failed: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"Created: {args.output.resolve()}")
    print(f"Bytes: {len(generated.encode('utf-8')):,}")
    print("Objects: 15 tables, 14 triggers, 11 procedures, 7 views")
    print("Safety: no rows, no explicit local DEFINER account, no DROP statements")
    print("WARNING: import only into a new, empty target database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
