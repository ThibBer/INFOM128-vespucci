import re

from pathlib import Path

from typing import Dict, List, Tuple
from lexer import lex_file, Token, TokenType


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
