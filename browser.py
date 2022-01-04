import tkinter
import tkinter.font


def request(url):
    scheme, url = url.split("://", 1)
    assert scheme in ["http", "https"], "Unknown scheme {}".format(scheme)

    port = 80 if scheme == "http" else 443

    host, path = url.split('/', 1)
    path = '/' + path

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    import socket
    import ssl

    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP
    )
    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)

    s.connect((host, port))

    data = "GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n".format(
        host=host, path=path)
    s.send(data.encode())

    response = s.makefile("r", encoding="utf8", newline="\r\n")

    statusline = response.readline()

    version, status, explanation = statusline.split(" ", 2)
    assert status == "200", "{}: {}".format(status, explanation)

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    body = response.read()
    s.close()

    return headers, body


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100


class Text:
    def __init__(self, text):
        self.text = text


class Tag:
    def __init__(self, tag):
        self.tag = tag


def lex(body: str):
    out = []
    text = ""
    in_tag = False

    for c in body:
        if c == "<":
            in_tag = True
            if text:
                out.append(Text(text))
            text = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(text))
            text = ""
        else:
            text += c
    if not in_tag and text:
        out.append(Text(text))
    return out


FONTS = {}


def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]


class Layout:
    def __init__(self, tokens):
        self.line = []
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP

        self.weight = "normal"
        self.style = "roman"
        self.size = 16

        for tok in tokens:
            self.token(tok)

        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            self.text(tok)

        elif isinstance(tok, Tag):
            self.tag(tok)

    def text(self, tok):
        font = get_font(self.size, self.weight, self.style)
        for word in tok.text.split():
            w = font.measure(word)
            if self.cursor_x + w >= WIDTH - HSTEP:
                self.flush()
            self.line.append(
                (self.cursor_x, word, font))
            self.cursor_x += w + font.measure(" ")

    def tag(self, tok):
        if tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag in ['br', 'br /']:
            self.flush()
        elif tok.tag in ['p', '/p']:
            self.flush()
            self.cursor_y += VSTEP

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        self.cursor_x = HSTEP
        self.line = []

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()

        self.scroll = 0
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<MouseWheel>", self.mousewheel)

        self.display_list = []

    def load(self, url):
        headers, body = request(url)
        print(body)
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, w, f in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue

            self.canvas.create_text(
                x, y - self.scroll, text=w, font=f, anchor='nw')

    def scrollup(self, e):
        if self.scroll > 0:
            self.scroll -= SCROLL_STEP
            self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def mousewheel(self, e):
        if e.delta == -1:
            self.scroll += SCROLL_STEP
            self.draw()
        elif e.delta == 1 and self.scroll > 0:
            self.scroll -= SCROLL_STEP
            self.draw()


if __name__ == "__main__":
    import sys
    # Browser().load('http://localhost:8000/')
    # Browser().load('https://www.zggdwx.com/xiyou/1.html')
    Browser().load(sys.argv[1])
    tkinter.mainloop()
