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

    Also handle concatenation of strings and constants:
    static final String SOME_CONST = "A" + OTHER_CONST + "B";
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
        # Look for CREATE TABLE (IF NOT EXISTS)
        upper_sql = sql.upper()
        idx = upper_sql.find("CREATE TABLE")
        if idx == -1:
            return

        # Extract table name and columns
        # A naive parsing approach:
        # CREATE TABLE [IF NOT EXISTS] table_name ( col_definitions )
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(sql)
        if match:
            table_name = match.group(2)
            cols_str = match.group(3)
            # Parse columns
            columns = self.parse_columns(cols_str)
            self.tables_with_lines.append((table_name, line))
            self.tables_columns[table_name] = columns

    def parse_columns(self, cols_str: str) -> List[str]:
        # Split by commas not inside parentheses (simple approach)
        # Then trim each column definition and extract the first token as column name
        columns = []
        # Remove trailing ) or ; if any and extra spaces
        cols_str = cols_str.strip().rstrip(");")

        # Split by commas
        col_defs = [c.strip() for c in cols_str.split(",")]

        # We'll consider a line a column definition if it starts with an identifier
        # and not a known constraint keyword like PRIMARY, FOREIGN, UNIQUE
        constraint_keywords = {
            "PRIMARY",
            "FOREIGN",
            "UNIQUE",
            "CHECK",
            "CONSTRAINT",
            "KEY",
        }
        for cdef in col_defs:
            parts = cdef.split()
            if len(parts) > 0:
                first = parts[0].strip('"`[]')
                if first.upper() not in constraint_keywords:
                    # Consider this a column
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


def find_table_references(
    project_dir: Path,
    tables: List[str],
    constants_map: Dict[str, str],
    table_columns: Dict[str, List[str]],
) -> Tuple[
    Dict[str, List[Tuple[Path, int, str]]],
    Dict[str, Dict[str, List[Tuple[Path, int, str]]]],
]:
    """
    Find references to tables and columns.
    We look for lines that:
      - Call known database operations.
      - Contain a table name or constant referencing that table.
      - If we find the table, we also check for column usage by searching for column names or their constants.

    Returns:
      table_references: {table_name: [(file_path, line_num, snippet), ...]}
      column_references: {table_name: {column_name: [(file_path, line_num, snippet), ...]}}
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

    # Maps literal table values to constants, for quick lookup
    literal_to_table = {v: k for k, v in constants_map.items() if v in tables}

    # Build a column lookup as well: map from literal column name to table/column
    # Note: multiple tables can have same column name, we must consider all possibilities.
    # We'll handle columns table-by-table after confirming the table usage.
    column_map = defaultdict(list)  # column_name -> [(table_name, column_name)]
    for tbl, cols in table_columns.items():
        for c in cols:
            column_map[c].append((tbl, c))

    # Also consider constants for columns
    # Reverse mapping for constants that map to strings that are columns in some table
    for const, val in constants_map.items():
        if val in tables:
            # It's a table constant
            pass
        # Check if val is a column in any table
        if val in column_map:
            # Add constant to column_map with the same references
            # We will handle substitution logic at runtime of line scanning.
            column_map[const].extend(column_map[val])

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

                if any(method in stripped_line for method in java_methods):
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
                            # Line references this table
                            table_references[table].append(
                                (file_path, i + 1, stripped_line)
                            )
                            table_used = True

                        if table_used:
                            # Now check columns of this table
                            # For each column in that table, check if it appears
                            # directly or via constants that resolve to it.
                            for col in table_columns.get(table, []):
                                # The column can appear as itself or any constant that maps to it
                                # First check direct appearance
                                col_used = False
                                if col in stripped_line:
                                    column_references[table][col].append(
                                        (file_path, i + 1, stripped_line)
                                    )
                                    col_used = True
                                else:
                                    # Check if any constant represents this column
                                    for const, literal in constants_map.items():
                                        if literal == col and const in stripped_line:
                                            column_references[table][col].append(
                                                (file_path, i + 1, stripped_line)
                                            )
                                            col_used = True
                                            break
        except UnicodeDecodeError:
            pass  # skip files that cannot be decoded

    return table_references, column_references


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


def generate_html_report(
    create_table_statements: Dict[str, Tuple[Path, int]],
    table_references: Dict[str, List[Tuple[Path, int, str]]],
    unused_tables: List[Tuple[str, Path]],
    table_columns: Dict[str, List[str]],
    column_references: Dict[str, Dict[str, List[Tuple[Path, int, str]]]],
    unused_columns: Dict[str, List[str]],
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

    print("Finding table and column references...")
    table_references, column_references = find_table_references(
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
        output_path,
        repo_url,
        clone_path,
    )
    print(f"Report generated at {output_path}")


if __name__ == "__main__":
    main()
