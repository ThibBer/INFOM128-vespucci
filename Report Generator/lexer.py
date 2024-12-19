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
