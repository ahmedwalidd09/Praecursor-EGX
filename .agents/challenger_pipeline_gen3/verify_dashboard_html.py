import sys
from pathlib import Path
from html.parser import HTMLParser

class StrictHTMLValidator(HTMLParser):
    VOID_TAGS = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr', '!doctype'
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t not in self.VOID_TAGS:
            self.stack.append((t, self.getpos()))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self.VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Line {self.getpos()[0]}:{self.getpos()[1]} - Unexpected </{t}> with empty stack")
        elif self.stack[-1][0] == t:
            self.stack.pop()
        else:
            open_tags = [x[0] for x in self.stack]
            if t in open_tags:
                while self.stack and self.stack[-1][0] != t:
                    popped, pos = self.stack.pop()
                    self.errors.append(f"Unclosed tag <{popped}> from line {pos[0]}:{pos[1]} when encountering </{t}>")
                self.stack.pop()
            else:
                self.errors.append(f"Line {self.getpos()[0]}:{self.getpos()[1]} - Unexpected </{t}> (stack top: <{self.stack[-1][0]}>)")

    def validate(self, content: str) -> tuple[bool, list[str]]:
        self.feed(content)
        if self.stack:
            for tag, pos in self.stack:
                self.errors.append(f"Unclosed tag <{tag}> opened at line {pos[0]}:{pos[1]}")
        return len(self.errors) == 0, self.errors

def main():
    dashboard_path = Path("reports/dashboard.html")
    if not dashboard_path.exists():
        print(f"ERROR: {dashboard_path} does not exist!")
        sys.exit(1)
    
    html = dashboard_path.read_text(encoding="utf-8")
    validator = StrictHTMLValidator()
    is_valid, errors = validator.validate(html)
    
    if is_valid:
        print("SUCCESS: reports/dashboard.html is well-formed with 0 tag errors!")
        sys.exit(0)
    else:
        print(f"FAILED: reports/dashboard.html contains {len(errors)} tag errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
