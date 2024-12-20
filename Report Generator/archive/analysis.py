import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from files_utils import find_java_files
from parser import parse_files


def find_create_table_statements(
    project_dir: Path,
) -> Tuple[Dict[str, Tuple[Path, int]], Dict[str, List[str]]]:
    java_files = find_java_files(project_dir)
    return parse_files(java_files)


def find_table_references(
    project_dir: Path,
    tables: List[str],
    constants_map: Dict[str, str],
    table_columns: Dict[str, List[str]],
) -> Tuple[
    Dict[str, List[Tuple[Path, int, str]]],
    Dict[str, Dict[str, List[Tuple[Path, int, str]]]],
    List[Dict],
]:
    """
    Find references to tables and columns, and also gather query statistics.

    Added features:
    - We now identify query type and compute complexity.
    - We store all queries in a list with their type, file, line and complexity.

    Returns:
      table_references: {table_name: [(file_path, line_num, snippet), ...]}
      column_references: {table_name: {column_name: [(file_path, line_num, snippet), ...]}}
      queries: A list of dictionaries with info about each query:
               {'type': str, 'file': Path, 'line': int, 'snippet': str, 'complexity': int}
    """
    java_methods = [
        "execSQL",
        "rawQuery",
        "query",
        "insert",
        "update",
        "delete",
        "replace",
        "compileStatement",
        "execute",
        "prepareStatement",
        "executeQuery",
    ]
    create_pattern = re.compile(r"CREATE\s+TABLE", re.IGNORECASE)
    table_references = defaultdict(list)
    column_references = {t: defaultdict(list) for t in tables}

    # Precompute column map
    # column_map is not needed now because we do direct checks per table
    # We'll rely on scanning line for column references after table is found.

    queries = []

    for file_path in project_dir.rglob("*.java"):
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                stripped_line = line.strip()

                # Skip comment lines
                if (
                    stripped_line.startswith("//")
                    or stripped_line.startswith("/*")
                    or stripped_line.startswith("*/")
                    or stripped_line.startswith("*")
                ):
                    continue

                # Skip lines that define the table (not a usage)
                if create_pattern.search(stripped_line):
                    continue

                # Check if line calls a known DB method
                called_methods = [m for m in java_methods if m in stripped_line]
                if called_methods:
                    # Consider the first matched method as indicative of query type
                    # (Heuristic: usually only one DB method call per line)
                    method = called_methods[0]
                    # Classify query
                    qtype = classify_query_type(stripped_line, method)
                    complexity = compute_query_complexity(stripped_line)
                    queries.append(
                        {
                            "type": qtype,
                            "file": file_path,
                            "line": i + 1,
                            "snippet": stripped_line,
                            "complexity": complexity,
                        }
                    )

                    # Check table usage
                    for table in tables:
                        # Check table name or any constant referencing it
                        table_used = False
                        if (table in stripped_line) or any(
                            (
                                const in stripped_line
                                for const, literal in constants_map.items()
                                if literal == table
                            )
                        ):
                            table_references[table].append(
                                (file_path, i + 1, stripped_line)
                            )
                            table_used = True

                        if table_used:
                            # Check columns usage
                            for col in table_columns.get(table, []):
                                # Direct column usage or via constants?
                                if col in stripped_line:
                                    column_references[table][col].append(
                                        (file_path, i + 1, stripped_line)
                                    )
                                else:
                                    # Check constants for columns
                                    for const, literal in constants_map.items():
                                        if literal == col and const in stripped_line:
                                            column_references[table][col].append(
                                                (file_path, i + 1, stripped_line)
                                            )
                                            break
        except UnicodeDecodeError:
            pass  # skip files that cannot be decoded

    return table_references, column_references, queries


def find_unused_tables(
    create_table_statements: Dict[str, Tuple[Path, int]],
    table_references: Dict[str, List[Tuple[Path, int, str]]],
) -> List[Tuple[str, Path]]:
    unused = []
    for table, creation_file_line in create_table_statements.items():
        if not table_references.get(table):
            creation_file = creation_file_line[0]
            unused.append((table, creation_file))
    return unused


def find_unused_columns(
    table_columns: Dict[str, List[str]],
    column_references: Dict[str, Dict[str, List[Tuple[Path, int, str]]]],
) -> Dict[str, List[str]]:
    unused_cols = {}
    for table, cols in table_columns.items():
        for col in cols:
            if not column_references[table].get(col):
                if table not in unused_cols:
                    unused_cols[table] = []
                unused_cols[table].append(col)
    return unused_cols


def classify_query_type(line: str, method: str) -> str:
    """
    Classify query type based on SQL keywords and method name.
    Heuristics:
    - If line mentions SELECT, consider it SELECT.
    - If INSERT INTO appears, consider INSERT.
    - If UPDATE appears, consider UPDATE.
    - If DELETE FROM appears, consider DELETE.
    - If CREATE TABLE appears, consider CREATE.
    - Else fallback to method name heuristics:
      - query/rawQuery/executeQuery -> SELECT
      - insert -> INSERT
      - update -> UPDATE
      - delete -> DELETE
      - replace -> INSERT (REPLACE)
      - execSQL, compileStatement -> try to guess from SQL if present
    """
    upper_line = line.upper()
    if "SELECT" in upper_line:
        return "SELECT"
    if "INSERT INTO" in upper_line:
        return "INSERT"
    if "UPDATE " in upper_line:
        return "UPDATE"
    if "DELETE FROM" in upper_line:
        return "DELETE"
    if "CREATE TABLE" in upper_line:
        return "CREATE"

    # Fallback to method name
    if method in ["query", "rawQuery", "executeQuery"]:
        return "SELECT"
    if method == "insert" or method == "replace":
        return "INSERT"
    if method == "update":
        return "UPDATE"
    if method == "delete":
        return "DELETE"
    if method in ["execSQL", "compileStatement", "execute", "prepareStatement"]:
        # Hard to guess if not found keywords
        return "UNKNOWN"
    return "UNKNOWN"


def compute_query_complexity(line: str) -> int:
    """
    A naive complexity measure:
    Count occurrences of common SQL keywords (JOIN, WHERE, GROUP BY, ORDER BY, UNION, etc.)

    The more keywords appear, the more 'complex' we consider the query.
    This is a simple heuristic.
    """
    keywords = [
        "JOIN",
        "WHERE",
        "GROUP BY",
        "ORDER BY",
        "HAVING",
        "UNION",
        "EXCEPT",
        "INTERSECT",
    ]
    upper_line = line.upper()
    complexity = 0
    for kw in keywords:
        complexity += upper_line.count(kw)
    # Also consider length as a factor: longer SQL might be more complex
    # Add 1 complexity point per 100 characters as a rough heuristic
    complexity += len(line) // 100
    return complexity
