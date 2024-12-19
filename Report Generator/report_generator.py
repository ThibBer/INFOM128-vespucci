from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Tuple
from git_operations import get_line_creation_date


def generate_html_report(
    create_table_statements: Dict[str, Tuple[Path, int]],
    table_references: Dict[str, List[Tuple[Path, int, str]]],
    unused_tables: List[Tuple[str, Path]],
    table_columns: Dict[str, List[str]],
    column_references: Dict[str, Dict[str, List[Tuple[Path, int, str]]]],
    unused_columns: Dict[str, List[str]],
    queries: List[Dict],
    output_path: Path,
    repo_url: str,
    clone_path: Path,
    branch: str = "master",
) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        f.write("<html><head><title>Database Table Usage Report</title></head><body>")
        f.write("<h1>Database Table Usage Report</h1>")

        # Summary Section
        f.write("<h2>Summary</h2>")
        f.write(f"<p>Total tables: {len(create_table_statements)}</p>")
        f.write(f"<p>Unused tables: {len(unused_tables)}</p>")
        if unused_tables:
            f.write("<ul>")
            for table, creation_file in unused_tables:
                creation_line = create_table_statements[table][1]
                relative_path = creation_file.relative_to(clone_path).as_posix()
                creation_date = get_line_creation_date(
                    clone_path, creation_file, creation_line
                )
                creation_date_text = (
                    f" (Created on: {creation_date})" if creation_date else ""
                )
                f.write(
                    f"<li><a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{creation_line}'>{table}</a> "
                    f"(Defined in: {relative_path}, Line: {creation_line}{creation_date_text})</li>"
                )
            f.write("</ul>")

        # Unused columns summary
        total_unused_columns = sum(len(cols) for cols in unused_columns.values())
        f.write(f"<p>Unused columns: {total_unused_columns}</p>")
        if total_unused_columns > 0:
            f.write("<ul>")
            for table, cols in unused_columns.items():
                creation_file, creation_line = create_table_statements[table]
                relative_path = creation_file.relative_to(clone_path).as_posix()
                f.write(
                    f"<li><strong>{table}</strong> (Defined in {relative_path}, line {creation_line}): "
                )
                f.write(", ".join(cols))
                f.write("</li>")
            f.write("</ul>")

        # Detailed Usage Section
        f.write("<h2>Detailed Table Usage</h2>")
        for table, references in table_references.items():
            f.write(f"<h3 id='{table}'>{table}</h3>")
            creation_data = create_table_statements.get(table)
            if creation_data:
                creation_file, creation_line = creation_data
                relative_path = creation_file.relative_to(clone_path).as_posix()
                creation_date = get_line_creation_date(
                    clone_path, creation_file, creation_line
                )
                creation_date_text = (
                    f" (Created on: {creation_date})" if creation_date else ""
                )
                f.write(
                    f"<p>Defined in: <a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{creation_line}'>"
                    f"{relative_path}, Line: {creation_line}</a>{creation_date_text}</p>"
                )
            else:
                f.write("<p>Definition file unknown.</p>")

            # Show columns
            f.write("<h4>Columns</h4>")
            f.write("<ul>")
            table_unused_cols = unused_columns.get(table, [])
            for col in table_columns.get(table, []):
                col_refs = column_references[table].get(col, [])
                if col_refs:
                    # Column is used
                    f.write(f"<li>{col} - used {len(col_refs)} times</li>")
                else:
                    # Unused column
                    f.write(f"<li>{col} - <strong>UNUSED</strong></li>")
            f.write("</ul>")

            if references:
                f.write("<h4>References</h4><ul>")
                for file_path, position, snippet in references:
                    relative_path = file_path.relative_to(clone_path).as_posix()
                    f.write(
                        f"<li>File: <a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{position}'>"
                        f"{relative_path}, Line: {position}</a>, Snippet: {snippet[:50]}</li>"
                    )
                f.write("</ul>")
            else:
                f.write("<p>No references found for this table.</p>")

            # Column references detailed section
            f.write("<h4>Column References</h4>")
            for col, col_refs in column_references[table].items():
                f.write(f"<h5>{col}</h5>")
                if col_refs:
                    f.write("<ul>")
                    for file_path, position, snippet in col_refs:
                        relative_path = file_path.relative_to(clone_path).as_posix()
                        f.write(
                            f"<li><a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{position}'>"
                            f"{relative_path}, Line {position}</a>: {snippet[:50]}</li>"
                        )
                    f.write("</ul>")
                else:
                    f.write("<p>No references found for this column.</p>")

        # Add Query Statistics Section
        generate_query_statistics_section(f, queries, clone_path, repo_url, branch)

        f.write("</body></html>")


def generate_query_statistics_section(
    f, queries: List[Dict], clone_path: Path, repo_url: str, branch: str
):
    """
    Generate an HTML section with detailed, commented statistics about the database queries:
    - Their type (SELECT, DELETE, INSERT, UPDATE, CREATE, etc.)
    - Their complexity (based on a simple heuristic)
    - Their distribution over the code base (which files contain the most queries)
    """

    # Compute queries by type
    queries_by_type = defaultdict(list)
    for q in queries:
        queries_by_type[q["type"]].append(q)

    # Compute complexity statistics
    # For each type, what is the average complexity?
    complexity_stats = {}
    for qtype, qlist in queries_by_type.items():
        complexities = [q["complexity"] for q in qlist]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        complexity_stats[qtype] = (len(qlist), avg_complexity)

    # Distribution by file: count queries per file
    queries_by_file = defaultdict(int)
    for q in queries:
        relative_path = q["file"].relative_to(clone_path).as_posix()
        queries_by_file[relative_path] += 1

    # Sort files by number of queries descending
    files_sorted = sorted(queries_by_file.items(), key=lambda x: x[1], reverse=True)

    f.write("<h2>Query Statistics</h2>")
    f.write("<p>Below are detailed statistics about the queries found in the code:</p>")

    # Queries by type
    f.write("<h3>Queries by Type</h3>")
    f.write("<ul>")
    for qtype, qlist in queries_by_type.items():
        count = len(qlist)
        f.write(f"<li>{qtype}: {count} queries</li>")
    f.write("</ul>")

    # Complexity statistics
    f.write("<h3>Complexity Statistics</h3>")
    f.write("<p>Complexity is a naive heuristic counting SQL keywords and length.</p>")
    f.write(
        "<table border='1'><tr><th>Query Type</th><th>Count</th><th>Average Complexity</th></tr>"
    )
    for qtype, (count, avg_complexity) in complexity_stats.items():
        f.write(
            f"<tr><td>{qtype}</td><td>{count}</td><td>{avg_complexity:.2f}</td></tr>"
        )
    f.write("</table>")

    # Distribution by file
    f.write("<h3>Distribution Over Code Base</h3>")
    if files_sorted:
        f.write("<p>Files with the most queries:</p>")
        f.write("<ol>")
        for filepath, qcount in files_sorted:
            f.write(f"<li>{filepath}: {qcount} queries</li>")
        f.write("</ol>")
    else:
        f.write("<p>No queries found.</p>")

    # Also, we can show a few example queries for each type
    f.write("<h3>Example Queries</h3>")
    for qtype, qlist in queries_by_type.items():
        f.write(f"<h4>{qtype}</h4>")
        # Show first 5 queries of this type
        examples = qlist[:5]
        if examples:
            f.write("<ul>")
            for ex in examples:
                relative_path = ex["file"].relative_to(clone_path).as_posix()
                f.write(
                    f"<li><a href='{repo_url}/blob/{branch}/{quote(relative_path)}#L{ex['line']}'>"
                    f"{relative_path}, line {ex['line']}</a>: {ex['snippet'][:100]}... "
                    f"(complexity: {ex['complexity']})</li>"
                )
            f.write("</ul>")
        else:
            f.write("<p>No examples.</p>")
