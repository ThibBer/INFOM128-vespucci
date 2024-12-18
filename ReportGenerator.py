import subprocess
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Tuple
from SQLTableExtractor import find_create_table_statements


def clone_repository(repo_url: str, clone_path: Path) -> None:
    """
    Clone the given repository into the specified directory if it does not exist.

    :param repo_url: URL of the repository to clone.
    :param clone_path: Local path where the repository should be cloned.
    """
    if not clone_path.exists():
        subprocess.run(["git", "clone", repo_url, str(clone_path)], check=True)


def find_table_references(
    project_dir: Path, tables: List[str]
) -> Dict[str, List[Tuple[Path, int, str]]]:
    """
    Scan Java files in the given project directory for references to the specified tables.

    References are:
      - Lines calling known database operations.
      - Containing a table name.

    Ignored:
      - Lines with CREATE TABLE statements (considered definitions, not usage).
      - Comment lines (starting with //, /*, * or */).

    :param project_dir: The directory containing the project files.
    :param tables: A list of table names to search for.
    :return: A dictionary mapping each table name to a list of tuples:
             (file_path, line_number, line_snippet).
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
    ]
    create_pattern = re.compile(r"CREATE\s+TABLE", re.IGNORECASE)
    table_references = defaultdict(list)

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

                # Check if line calls a known DB method and contains any of the tables
                if any(method in stripped_line for method in java_methods):
                    for table in tables:
                        if table in stripped_line:
                            table_references[table].append(
                                (file_path, i + 1, stripped_line)
                            )
        except UnicodeDecodeError:
            pass  # skip files that cannot be decoded

    return table_references


def find_unused_tables(
    create_table_statements: Dict[str, Path],
    table_references: Dict[str, List[Tuple[Path, int, str]]],
) -> List[Tuple[str, Path]]:
    """
    Identify tables that are not referenced anywhere in the code.

    :param create_table_statements: Mapping of table names to the files that define them.
    :param table_references: Mapping of table names to their occurrences in code.
    :return: A list of tuples containing the table name and the file in which it's defined for all unused tables.
    """
    unused = []
    for table, creation_file in create_table_statements.items():
        if not table_references.get(table):
            unused.append((table, creation_file))
    return unused


def generate_html_report(
    create_table_statements: Dict[str, Tuple[Path, int]],
    table_references: Dict[str, List[Tuple[Path, int, str]]],
    unused_tables: List[Tuple[str, Tuple[Path, int]]],
    output_path: Path,
    repo_url: str,
    clone_path: Path,
    branch: str = "master",
) -> None:
    """
    Generate an HTML report summarizing the database table usage.

    :param create_table_statements: Mapping of table names to the files and lines that define them.
    :param table_references: Mapping of table names to a list of references.
    :param unused_tables: List of unused tables with their definition file and line number.
    :param output_path: The path where the HTML report will be written.
    :param repo_url: The original repository URL.
    :param clone_path: The path where the repository was cloned.
    :param branch: The branch name of the repository (defaults to "master").
    """
    with output_path.open("w", encoding="utf-8") as f:
        f.write("<html><head><title>Database Table Usage Report</title></head><body>")
        f.write("<h1>Database Table Usage Report</h1>")

        # Summary Section
        f.write("<h2>Summary</h2>")
        f.write(f"<p>Total tables: {len(create_table_statements)}</p>")
        f.write(f"<p>Unused tables: {len(unused_tables)}</p>")
        if unused_tables:
            f.write("<ul>")
            for table, (creation_file, creation_line) in unused_tables:
                relative_path = creation_file.relative_to(clone_path).as_posix()
                f.write(
                    f"<li><a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{creation_line}'>{table}</a> "
                    f"(Defined in: {relative_path}, Line: {creation_line})</li>"
                )
            f.write("</ul>")

        # Detailed Usage Section
        f.write("<h2>Detailed Table Usage</h2>")
        for table, references in table_references.items():
            f.write(f"<h3 id='{table}'>{table}</h3>")
            creation_data = create_table_statements.get(table)
            if creation_data:
                creation_file, creation_line = creation_data
                relative_path = creation_file.relative_to(clone_path).as_posix()
                f.write(
                    f"<p>Defined in: <a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{creation_line}'>"
                    f"{relative_path}, Line: {creation_line}</a></p>"
                )
            else:
                f.write("<p>Definition file unknown.</p>")

            if references:
                f.write("<ul>")
                for file_path, position, snippet in references:
                    relative_path = file_path.relative_to(clone_path).as_posix()
                    f.write(
                        f"<li>File: <a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{position}'>"
                        f"{relative_path}, Line: {position}</a>, Snippet: {snippet[:50]}</li>"
                    )
                f.write("</ul>")
            else:
                f.write("<p>No references found.</p>")

        f.write("</body></html>")


def main():
    repo_url = input("Enter the repository URL: ").strip()
    script_dir = Path(__file__).parent.resolve()
    clone_path = script_dir / "repo_clone"
    output_path = script_dir / "database_usage_report.html"

    print("Cloning repository...")
    clone_repository(repo_url, clone_path)

    print("Finding CREATE TABLE statements...")
    create_table_statements = find_create_table_statements(clone_path)
    print(f"Found {len(create_table_statements)} tables.")

    print("Finding table references...")
    table_references = find_table_references(
        clone_path, list(create_table_statements.keys())
    )

    print("Identifying unused tables...")
    unused_tables = find_unused_tables(create_table_statements, table_references)

    if unused_tables:
        print("\nUnused tables:")
        for table, creation_file in unused_tables:
            print(f"- {table} (Defined in: {creation_file})")
    else:
        print("\nNo unused tables found.")

    print("\nGenerating HTML report...")
    generate_html_report(
        create_table_statements,
        table_references,
        unused_tables,
        output_path,
        repo_url,
        clone_path,
    )
    print(f"Report generated at {output_path}")


if __name__ == "__main__":
    main()
