import subprocess
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Tuple, Optional
import os


class TokenType:
    IDENTIFIER = "IDENTIFIER"
    DOT = "DOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    SEMI = "SEMI"
    STRING = "STRING"
    OTHER = "OTHER"
    EOF = "EOF"


class Token:
    def __init__(self, ttype, value, line):
        self.type = ttype
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value}, line={self.line})"


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.length = len(text)
        self.line = 1

    def peek_char(self):
        if self.pos < self.length:
            return self.text[self.pos]
        return None

    def get_char(self):
        if self.pos < self.length:
            ch = self.text[self.pos]
            self.pos += 1
            if ch == "\n":
                self.line += 1
            return ch
        return None

    def skip_whitespace(self):
        while True:
            ch = self.peek_char()
            if ch is not None and ch.isspace():
                self.get_char()
            else:
                break

    def is_identifier_start(self, ch):
        return ch is not None and (ch.isalpha() or ch == "_")

    def is_identifier_part(self, ch):
        return ch is not None and (ch.isalnum() or ch == "_")

    def get_identifier(self):
        result = []
        start_line = self.line
        result.append(self.get_char())
        while True:
            ch = self.peek_char()
            if self.is_identifier_part(ch):
                result.append(self.get_char())
            else:
                break
        return "".join(result), start_line

    def get_string(self):
        # consume the opening quote
        start_line = self.line
        self.get_char()
        result = []
        while True:
            ch = self.get_char()
            if ch is None:
                # unexpected EOF in string
                break
            if ch == "\\":
                next_ch = self.get_char()
                if next_ch is not None:
                    result.append(next_ch)
            elif ch == '"':
                # end of string
                break
            else:
                result.append(ch)
        return "".join(result), start_line

    def get_next_token(self):
        self.skip_whitespace()
        start_line = self.line
        ch = self.peek_char()
        if ch is None:
            return Token(TokenType.EOF, None, self.line)
        if self.is_identifier_start(ch):
            ident, l = self.get_identifier()
            return Token(TokenType.IDENTIFIER, ident, l)
        if ch == '"':
            s, l = self.get_string()
            return Token(TokenType.STRING, s, l)
        if ch == ".":
            self.get_char()
            return Token(TokenType.DOT, ".", start_line)
        if ch == "(":
            self.get_char()
            return Token(TokenType.LPAREN, "(", start_line)
        if ch == ")":
            self.get_char()
            return Token(TokenType.RPAREN, ")", start_line)
        if ch == ";":
            self.get_char()
            return Token(TokenType.SEMI, ";", start_line)

        # For other single chars
        val = self.get_char()
        return Token(TokenType.OTHER, val, start_line)


def lex_file(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lexer = Lexer(text)
    tokens = []
    while True:
        tok = lexer.get_next_token()
        tokens.append(tok)
        if tok.type == TokenType.EOF:
            break
    return tokens


def extract_constants(tokens):
    """
    Extract constants of forms like:
    static final String IDENT = "VALUE";

    Also handle concatenation of strings and constants.
    """
    constants_map = {}
    length = len(tokens)
    i = 0
    while i < length:
        # Look for pattern: static final String <NAME> = ...
        if (
            i < length
            and tokens[i].type == TokenType.IDENTIFIER
            and tokens[i].value == "static"
        ):
            # Check if next tokens are 'final String'
            if (
                i + 1 < length
                and tokens[i + 1].type == TokenType.IDENTIFIER
                and tokens[i + 1].value == "final"
                and i + 2 < length
                and tokens[i + 2].type == TokenType.IDENTIFIER
                and tokens[i + 2].value == "String"
                and i + 3 < length
                and tokens[i + 3].type == TokenType.IDENTIFIER
            ):
                name = tokens[i + 3].value
                # Next should be '='
                if (
                    i + 4 < length
                    and tokens[i + 4].type == TokenType.OTHER
                    and tokens[i + 4].value == "="
                ):
                    # Collect right hand side until SEMI
                    j = i + 5
                    rhs_tokens = []
                    while (
                        j < length
                        and tokens[j].type != TokenType.SEMI
                        and tokens[j].type != TokenType.EOF
                    ):
                        rhs_tokens.append(tokens[j])
                        j += 1
                    if j < length and tokens[j].type == TokenType.SEMI:
                        # Evaluate rhs_tokens
                        buffer_str = ""
                        for rt in rhs_tokens:
                            if rt.type == TokenType.STRING:
                                buffer_str += rt.value
                            elif rt.type == TokenType.IDENTIFIER:
                                # Substitute if we already have this constant
                                buffer_str += constants_map.get(rt.value, "")
                            # Ignore '+' and other tokens
                        constants_map[name] = buffer_str
                        i = j + 1
                        continue
        i += 1
    return constants_map


class Parser:
    def __init__(self, tokens, constants_map=None):
        self.tokens = tokens
        self.pos = 0
        self.length = len(tokens)
        self.tables_with_lines = []
        self.tables_columns = {}  # table_name -> list of columns
        self.constants_map = constants_map if constants_map else {}

    def peek(self):
        if self.pos < self.length:
            return self.tokens[self.pos]
        return Token(TokenType.EOF, None, 0)

    def advance(self):
        if self.pos < self.length:
            self.pos += 1

    def parse(self):
        # Look for pattern: db '.' execSQL '(' ... ')'
        while self.peek().type != TokenType.EOF:
            t = self.peek()
            if t.type == TokenType.IDENTIFIER and t.value == "db":
                self.advance()
                if self.peek().type == TokenType.DOT:
                    self.advance()
                    if (
                        self.peek().type == TokenType.IDENTIFIER
                        and self.peek().value == "execSQL"
                    ):
                        self.advance()
                        if self.peek().type == TokenType.LPAREN:
                            self.advance()
                            sql, line = self.extractFullSQL()  # parse the argument
                            if sql:
                                self.extract_tables(sql, line)
            else:
                self.advance()

    def extractFullSQL(self):
        # Parse until matching closing parenthesis
        paren_depth = 1
        sql_parts = []
        min_line = None
        while True:
            current = self.peek()
            if current.type == TokenType.EOF:
                break
            if current.type == TokenType.RPAREN:
                paren_depth -= 1
                self.advance()
                if paren_depth == 0:
                    break
            elif current.type == TokenType.STRING:
                sql_parts.append(current.value)
                if min_line is None or current.line < min_line:
                    min_line = current.line
                self.advance()
            elif current.type == TokenType.IDENTIFIER:
                resolved = self.constants_map.get(current.value, "")
                if resolved and (min_line is None or current.line < min_line):
                    min_line = current.line
                sql_parts.append(resolved)
                self.advance()
            elif current.type == TokenType.OTHER and current.value == "+":
                self.advance()
            elif current.type == TokenType.LPAREN:
                paren_depth += 1
                self.advance()
            else:
                self.advance()

        return "".join(sql_parts), (
            min_line
            if min_line is not None
            else (self.peek().line if self.peek().line else 0)
        )

    def extract_tables(self, sql, line):
        # Look for CREATE TABLE statements and extract table name and columns
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(sql)
        if match:
            table_name = match.group(2)
            cols_str = match.group(3)
            columns = self.parse_columns(cols_str)
            self.tables_with_lines.append((table_name, line))
            self.tables_columns[table_name] = columns

    def parse_columns(self, cols_str: str) -> List[str]:
        # Simple column parsing
        cols_str = cols_str.strip().rstrip(");")
        col_defs = [c.strip() for c in cols_str.split(",")]

        constraint_keywords = {
            "PRIMARY",
            "FOREIGN",
            "UNIQUE",
            "CHECK",
            "CONSTRAINT",
            "KEY",
        }
        columns = []
        for cdef in col_defs:
            parts = cdef.split()
            if len(parts) > 0:
                first = parts[0].strip('"`[]')
                if first.upper() not in constraint_keywords:
                    columns.append(first)
        return columns


def parse_files(
    java_files: List[str],
) -> Tuple[Dict[str, Tuple[Path, int]], Dict[str, List[str]]]:
    results_dict = {}
    tables_columns = {}
    for jf in java_files:
        tokens = lex_file(jf)
        constants_map = extract_constants(tokens)
        parser = Parser(tokens, constants_map)
        parser.parse()
        for t, line in parser.tables_with_lines:
            results_dict[t] = (Path(jf), line if line is not None else 1)
        for t in parser.tables_columns:
            tables_columns[t] = parser.tables_columns[t]
    print(f"Found {len(results_dict)} tables")
    return results_dict, tables_columns


def find_java_files(root_dir):
    java_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files


def find_create_table_statements(
    project_dir: Path,
) -> Tuple[Dict[str, Tuple[Path, int]], Dict[str, List[str]]]:
    java_files = find_java_files(project_dir)
    return parse_files(java_files)


def clone_repository(repo_url: str, clone_path: Path) -> None:
    if not clone_path.exists():
        subprocess.run(["git", "clone", repo_url, str(clone_path)], check=True)


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


def get_line_creation_date(
    repo_path: Path, file_path: Path, line_number: int
) -> Optional[str]:
    try:
        relative_path = file_path.relative_to(repo_path).as_posix()
        result = subprocess.run(
            [
                "git",
                "blame",
                "--date=iso",
                "-L",
                f"{line_number},{line_number}",
                relative_path,
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        match = re.search(r"(\d{4}-\d{2}-\d{2})", output)
        if match:
            return match.group(1)
    except subprocess.CalledProcessError:
        pass
    return None


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
