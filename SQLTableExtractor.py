import os
from pathlib import Path
from typing import Dict, Tuple, List


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
    [private] static final String IDENT = "VALUE";

    Also handle cases where `private` is missing or other access modifiers might appear.
    Also handle concatenation of strings and constants:
    static final String SOME_CONST = "A" + OTHER_CONST + "B";

    We'll do a more flexible search:
    - Find 'static'
    - Followed by 'final'
    - Followed by 'String'
    - Then IDENT
    - Then '='
    - Then a sequence of STRING/IDENTIFIER/+ until we hit a SEMI.
    """

    constants_map = {}
    i = 0
    length = len(tokens)
    while i < length:
        # We look for a sequence that includes: static final String <NAME> = ...
        # There might be an access modifier (private/public/protected) before static, so we skip extra IDENTIFIERS until we find 'static'.

        # Find 'static'
        if (
            i < length
            and tokens[i].type == TokenType.IDENTIFIER
            and tokens[i].value == "static"
        ):
            # Check if next tokens are 'final String'
            # Pattern: static final String IDENT = ...
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
                        # Evaluate rhs_tokens to produce a string
                        buffer_str = ""
                        for rt in rhs_tokens:
                            if rt.type == TokenType.STRING:
                                buffer_str += rt.value
                            elif rt.type == TokenType.IDENTIFIER:
                                # Substitute if we already have this constant
                                buffer_str += constants_map.get(rt.value, "")
                            # Ignore '+' and other tokens that are not STRING or IDENTIFIER
                            # (assuming only concatenations of known constants and strings)

                        constants_map[name] = buffer_str
                        i = j + 1
                        continue
        elif (
            i + 1 < length
            and tokens[i].type == TokenType.IDENTIFIER
            and tokens[i].value in ("private", "public", "protected")
        ):
            # If we encounter an access modifier followed by static, skip it and let the next iteration handle static.
            # We do this so the next iteration finds 'static' properly.
            pass

        i += 1

    return constants_map


class Parser:
    def __init__(self, tokens, constants_map=None):
        self.tokens = tokens
        self.pos = 0
        self.length = len(tokens)
        self.tables = []
        self.constants_map = constants_map if constants_map else {}
        # Store tables as tuples of (table_name, line_number)
        self.tables_with_lines = []

    def peek(self):
        if self.pos < self.length:
            return self.tokens[self.pos]
        return Token(TokenType.EOF, None, 0)

    def advance(self):
        if self.pos < self.length:
            self.pos += 1

    def parse(self):
        # Look for pattern: db '.' execSQL '(' ... ')'
        # and reconstruct the string inside execSQL.
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
                # end of execSQL arguments
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

        # The line we have is the line of at least one token that formed the SQL string.
        # It's approximate, but good enough for a reference to creation line.
        remainder = sql[idx + len("CREATE TABLE") :].strip()

        separators = ["(", ")", ";", ","]
        for sep in separators:
            remainder = remainder.replace(sep, " ")

        parts = remainder.split()

        i = 0
        # Skip IF NOT EXISTS
        if i < len(parts) and parts[i].upper() == "IF":
            i += 1
            if i < len(parts) and parts[i].upper() == "NOT":
                i += 1
                if i < len(parts) and parts[i].upper() == "EXISTS":
                    i += 1

        if i < len(parts):
            table_name = parts[i]
            if table_name:
                self.tables_with_lines.append((table_name, line))


def parse_files(java_files: List[str]) -> Dict[str, Tuple[Path, int]]:
    results_dict = {}
    for jf in java_files:
        tokens = lex_file(jf)
        constants_map = extract_constants(tokens)
        parser = Parser(tokens, constants_map)
        parser.parse()
        for t, line in parser.tables_with_lines:
            # If multiple definitions, the last one is overwritten.
            # You can adjust logic if needed.
            results_dict[t] = (Path(jf), line if line is not None else 1)
    print(f"Found {len(results_dict)} tables")
    return results_dict


def find_java_files(root_dir):
    java_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files


def find_create_table_statements(project_dir: Path) -> Dict[str, Tuple[Path, int]]:
    java_files = find_java_files(project_dir)
    return parse_files(java_files)
