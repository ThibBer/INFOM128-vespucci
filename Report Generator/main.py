from pathlib import Path
from git_operations import clone_repository
from analysis import (
    find_create_table_statements,
    find_table_references,
    find_unused_tables,
    find_unused_columns,
)
from files_utils import find_java_files
from lexer import lex_file
from parser import extract_constants
from report_generator import generate_html_report


def main():
    repo_url = input("Enter the repository URL: ").strip()
    script_dir = Path(__file__).parent.resolve()
    clone_path = script_dir / "repo_clone"
    output_path = script_dir / "database_usage_report.html"

    print("Cloning repository...")
    clone_repository(repo_url, clone_path)

    print("Finding CREATE TABLE statements...")
    create_table_statements, table_columns = find_create_table_statements(clone_path)
    print(f"Found {len(create_table_statements)} tables.")

    print("Extracting constants...")
    java_files = find_java_files(clone_path)
    constants_map = {}
    for jf in java_files:
        tokens = lex_file(jf)
        constants_map.update(extract_constants(tokens))
    print(f"Extracted {len(constants_map)} constants.")

    print("Finding table and column references and collecting query stats...")
    table_references, column_references, queries = find_table_references(
        clone_path, list(create_table_statements.keys()), constants_map, table_columns
    )

    print("Identifying unused tables...")
    unused_tables = find_unused_tables(create_table_statements, table_references)

    print("Identifying unused columns...")
    unused_columns = find_unused_columns(table_columns, column_references)

    if unused_tables:
        print("\nUnused tables:")
        for table, creation_file in unused_tables:
            print(f"- {table} (Defined in: {creation_file})")
    else:
        print("\nNo unused tables found.")

    if any(unused_columns.values()):
        print("\nUnused columns:")
        for t, cols in unused_columns.items():
            print(f"{t}: {', '.join(cols)}")
    else:
        print("\nNo unused columns found.")

    print("\nGenerating HTML report...")
    generate_html_report(
        create_table_statements,
        table_references,
        unused_tables,
        table_columns,
        column_references,
        unused_columns,
        queries,
        output_path,
        repo_url,
        clone_path,
    )
    print(f"Report generated at {output_path}")


if __name__ == "__main__":
    main()
