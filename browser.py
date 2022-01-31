import socket
import ssl
import urllib.parse
import dukpy
import ctypes
import sdl2
import skia


def request(url, top_level_url, payload=None):
    scheme, url = url.split("://", 1)
    assert scheme in ["http", "https"], f"Unknown scheme {scheme}"

    port = 80 if scheme == "http" else 443

    host, path = url.split('/', 1)
    path = '/' + path

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP
    )
    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)

    method = "POST" if payload else "GET"
    body = f'{method} {path} HTTP/1.0\r\nHost: {host}\r\n'
    if payload:
        length = len(payload.encode("utf8"))
        body += f"Content-Length: {length}\r\n"
    if host in COOKIE_JAR:
        cookie, params = COOKIE_JAR[host]
        allow_cookie = True

        if top_level_url and params.get("samesite", "none") == "lax":
            _, _, top_level_host, _ = top_level_url.split("/", 3)
            top_level_host, _ = top_level_host.split(":", 1)
            allow_cookie = (host == top_level_host or method == "GET")
        if allow_cookie:
            body += f'Cookie: {cookie}\r\n'

    body += "\r\n" + (payload or "")

    s.connect((host, port))
    s.send(body.encode())

    response = s.makefile("r", encoding="utf8", newline="\r\n")

    statusline = response.readline()

    version, status, explanation = statusline.split(" ", 2)
    assert status == "200", f"{status}: {explanation}"

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    if 'set-cookie' in headers:
        params = {}
        if ';' in headers['set-cookie']:
            cookie, rest = headers["set-cookie"].split(';', 1)
            for param_pair in rest.split(';'):
                name, value = param_pair.strip().split("=", 1)
                params[name.lower()] = value.lower()
        else:
            cookie = headers["set-cookie"]
        COOKIE_JAR[host] = (cookie, params)

    body = response.read()
    s.close()

    return headers, body


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
FONTS = {}


def get_font(size, weight, style):
    key = (weight, style)
    if key not in FONTS:
        skia_weight = skia.FontStyle.kBold_Weight if weight == "bold" \
            else skia.FontStyle.kNormal_Weight
        skia_style = skia.FontStyle.kItalic_Slant if style == "italic" \
            else skia.FontStyle.kUpright_Slant
        skia_width = skia.FontStyle.kNormal_Width
        style_info = skia.FontStyle(skia_weight, skia_width, skia_style)

        font = skia.Typeface('Arial', style_info)
        FONTS[key] = font
    return skia.Font(FONTS[key], size)


def parse_color(color):
    if color == "white":
        return skia.ColorWHITE
    elif color == "lightblue":
        return skia.ColorSetARGB(0xFF, 0xAD, 0xD8, 0xE6)
    elif color == "orange":
        return skia.ColorSetARGB(0xFF, 0xFF, 0xA5, 0x00)
    elif color == "red":
        return skia.ColorRED
    elif color == "green":
        return skia.ColorGREEN
    elif color == "blue":
        return skia.ColorBLUE
    elif color == "gray":
        return skia.ColorGRAY
    else:
        return skia.ColorBLACK


def draw_line(canvas, x1, y1, x2, y2):
    path = skia.Path().moveTo(x1, y1).lineTo(x2, y2)
    paint = skia.Paint(Color=skia.ColorBLACK)
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(1)
    canvas.drawPath(path, paint)


def draw_text(canvas, x, y, text, font, color=None):
    sk_color = parse_color(color)
    paint = skia.Paint(AntiAlias=True, Color=sk_color)
    canvas.drawString(
        text, float(x), y - font.getMetrics().fAscent,
        font, paint
    )


def draw_rect(canvas, l, t, r, b, fill=None, width=1):
    paint = skia.Paint()
    if fill:
        paint.setStrokeWidth(width)
        paint.setColor(parse_color(fill))
    else:
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(1)
        paint.setColor(skia.ColorBLACK)
    rect = skia.Rect.MakeLTRB(l, t, r, b)
    canvas.drawRect(rect, paint)


def paint_visual_effects(node, cmds, rect):
    blend_mode = parse_blend_mode(node.style.get("mix-blend-mode"))
    opacity = float(node.style.get("opacity", 1.0))
    border_radius = float(node.style.get("border-radius", "0px")[:-2])

    needs_clip = node.style.get("overflow", "visible") == "clip"
    needs_blend_isolation = blend_mode != skia.BlendMode.kSrcOver or \
        needs_clip or opacity != 1.0

    if needs_clip:
        clip_radius = border_radius
    else:
        clip_radius = 0

    return [
        SaveLayer(skia.Paint(BlendMode=blend_mode, Alphaf=opacity), [
            ClipRRect(rect, clip_radius, cmds, should_clip=needs_clip)
        ], should_save=needs_blend_isolation),
    ]


def parse_blend_mode(blend_mode_str):
    if blend_mode_str == "multiply":
        return skia.BlendMode.kMultiply
    if blend_mode_str == "difference":
        return skia.BlendMode.kDifference
    return skia.BlendMode.kSrcOver


def linespace(font):
    metrics = font.getMetrics()
    return metrics.fDescent - metrics.fAscent


class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)


class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr("<" + self.tag + ">")


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        text = ""
        in_tag = False

        for c in self.body:
            if c == "<":
                in_tag = True
                if text:
                    self.add_text(text)
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def get_attributes(self, text: str):
        parts = [part.strip() for part in text.split(" ", 1)]
        tag = parts[0].lower()

        attributes = {}
        if (len(parts) > 1):
            words = parts[1].split('"')
            attrs = ['"'.join(words[i:i+2]).strip() +
                     '"' for i in range(0, len(words)-1, 2)]
            for attrpair in attrs:
                if "=" in attrpair:
                    key, value = attrpair.split("=", 1)
                    if len(value) > 2 and value[0] in ["'", "\""]:
                        value = value[1: -1]
                    attributes[key.lower()] = value
                else:
                    attributes[attrpair.lower()] = ''
        return tag, attributes

    def add_text(self, text):
        if text.isspace():
            return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith('!'):
            return
        self.implicit_tags(tag)
        if tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        elif tag.startswith('/'):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == "html" and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

    def finish(self):
        if len(self.unfinished) == 0:
            self.add_tag("html")
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()


BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"


]


def layout_mode(node):
    if isinstance(node, Text):
        return 'inline'
    if node.children:
        for child in node.children:
            if isinstance(child, Text):
                continue
            if child.tag in BLOCK_ELEMENTS:
                return 'block'
        return 'inline'
    return 'block'


class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag


class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent
        return False


INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


def compute_style(node, property, value):
    if property == 'font-size':
        if value.endswith("px"):
            return value
        elif value.endswith("%"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]
            node_pct = float(value[:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            return str(node_pct*parent_px) + "px"
        else:
            return None
    else:
        return value


def style(node, rules):
    node.style = {}

    # Inherited styles
    for prop, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[prop] = node.parent.style[prop]
        else:
            node.style[prop] = default_value

    # Selector styles
    for selector, body in rules:
        if not selector.matches(node):
            continue
        for prop, value in body.items():
            computed_value = compute_style(node, prop, value)
            if not computed_value:
                continue
            node.style[prop] = computed_value

    # Inline styles
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for prop, value in pairs.items():
            node.style[prop] = value
    for child in node.children:
        style(child, rules)


def cascade_priority(rule):
    selector, body = rule
    return selector.priority


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == 'normal':
            style = "roman"
        size = float(self.node.style["font-size"][:-2])
        self.font = get_font(size, weight, style)

        self.width = self.font.measureText(self.word)
        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = linespace(self.font)

    def paint(self, display_list):
        color = self.node.style["color"]
        display_list.append(
            DrawText(self.x, self.y, self.word, self.font, color))

    def __repr__(self):
        return "TextLayout(x={}, y={}, width={}, height={}, font={}, word={}".format(
            self.x, self.y, self.width, self.height, self.font, self.word)


INPUT_WIDTH_PX = 200


class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == 'normal':
            style = "roman"
        size = float(self.node.style["font-size"][:-2])
        self.font = get_font(size, weight, style)

        self.width = INPUT_WIDTH_PX
        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = linespace(self.font)

    def paint(self, display_list):
        cmds = []
        rect = skia.Rect.MakeLTRB(
            self.x, self.y, self.x + self.width, self.y + self.height)
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            cmds.append(DrawRRect(rect, radius, bgcolor))

        if self.node.tag == "input":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "button":
            text = self.node.children[0].text

        color = self.node.style["color"]
        cmds.append(DrawText(self.x, self.y, text, self.font, color))

        cmds = paint_visual_effects(self.node, cmds, rect)
        display_list.extend(cmds)

    def __repr__(self):
        return "InputLayout(x={}, y={}, width={}, height={}, font={}, word={}".format(
            self.x, self.y, self.width, self.height, self.font, self.word)


class InlineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.children = []
        self.previous = previous

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        self.new_line()
        self.recurse(self.node)
        for line in self.children:
            line.layout()
        self.height = sum([line.height for line in self.children])

    def recurse(self, node):
        if isinstance(node, Text):
            self.text(node)
        else:
            if node.tag == 'br':
                self.new_line()
            elif node.tag == 'input' or node.tag == 'button':
                self.input(node)
            else:
                for child in node.children:
                    self.recurse(child)

    def get_font(self, node):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        return get_font(size, weight, style)

    def new_line(self):
        self.previous_word = None
        self.cursor_x = self.x
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def input(self, node):
        w = INPUT_WIDTH_PX
        if self.cursor_x + w > self.x + self.width:
            self.new_line()
        line = self.children[-1]
        input = InputLayout(node, line, self.previous_word)
        line.children.append(input)
        self.previous_word = input
        font = self.get_font(node)
        self.cursor_x += w + font.measureText(" ")

    def text(self, node):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == 'normal':
            style = "roman"
        size = float(node.style["font-size"][:-2])
        font = get_font(size, weight, style)
        for word in node.text.split():
            w = font.measureText(word)
            if self.cursor_x + w > self.width - HSTEP:
                self.new_line()
            line = self.children[-1]
            text = TextLayout(node, word, line, self.previous_word)
            line.children.append(text)
            self.previous_word = text
            self.cursor_x += w + font.measureText(" ")

    def paint(self, display_list):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        rect = skia.Rect.MakeLTRB(
            self.x, self.y, self.x + self.width, self.y + self.height)
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            cmds.append(DrawRRect(rect, radius, bgcolor))
        for child in self.children:
            child.paint(cmds)

        cmds = paint_visual_effects(self.node, cmds, rect)
        display_list.extend(cmds)

    def __repr__(self):
        return "InlineLayout(x={}, y={}, width={}, height={})".format(
            self.x, self.y, self.width, self.height)


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        max_ascent = max([-word.font.getMetrics().fAscent
                          for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline + word.font.getMetrics().fAscent
        max_descent = max([word.font.getMetrics().fDescent
                           for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

    def __repr__(self):
        return "LineLayout(x={}, y={}, width={}, height={})".format(
            self.x, self.y, self.width, self.height)


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.children = []
        self.previous = previous

    def layout(self):
        previous = None
        for child in self.node.children:
            if layout_mode(child) == 'inline':
                next_block = InlineLayout(child, self, previous)
            else:
                next_block = BlockLayout(child, self, previous)
            self.children.append(next_block)
            previous = next_block

        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for child in self.children:
            child.layout()

        self.height = sum([child.height for child in self.children])

    def paint(self, display_list):
        cmds = []
        rect = skia.Rect.MakeLTRB(
            self.x, self.y, self.x + self.width, self.y + self.height)
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            cmds.append(DrawRRect(rect, radius, bgcolor))

        for child in self.children:
            child.paint(cmds)

        cmds = paint_visual_effects(self.node, cmds, rect)
        display_list.extend(cmds)

    def __repr__(self):
        return "BlockLayout(x={}, y={}, width={}, height={})".format(
            self.x, self.y, self.width, self.height)


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = WIDTH - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height + 2*VSTEP

    def paint(self, display_list):
        self.children[0].paint(display_list)

    def __repr__(self) -> str:
        return "DocumentLayout()"


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.right = x1 + font.measureText(text)
        self.bottom = y1 + linespace(font)
        self.rect = skia.Rect.MakeLTRB(x1, y1, self.right, self.bottom)
        self.text = text
        self.font = font
        self.color = color

    def execute(self, scroll: int, canvas):
        draw_text(canvas,
                  self.left,
                  self.top - scroll,
                  self.text,
                  self.font,
                  self.color)


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.rect = skia.Rect.MakeLTRB(x1, y1, x2, y2)
        self.color = color

    def execute(self, scroll, canvas):
        draw_rect(canvas,
                  self.left,
                  self.top - scroll,
                  self.right,
                  self.bottom - scroll,
                  self.color,
                  width=0,
                  )


class SaveLayer:
    def __init__(self, sk_paint, cmds,
                 should_save=True, should_paint_cmds=True):
        self.should_save = should_save
        self.should_paint_cmds = should_paint_cmds
        self.sk_paint = sk_paint
        self.cmds = cmds
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.cmds:
            self.rect.join(cmd.rect)

    def execute(self, scroll, canvas):
        if self.should_save:
            canvas.saveLayer(paint=self.sk_paint)
        if self.should_paint_cmds:
            for cmd in self.cmds:
                cmd.execute(scroll, canvas)
        if self.should_save:
            canvas.restore()


class ClipRRect:
    def __init__(self, rect, radius, cmds, should_clip=True):
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.cmds = cmds
        self.should_clip = should_clip

    def execute(self, scroll, canvas):
        if self.should_clip:
            canvas.save()
            rrect_offset = skia.RRect.makeOffset(self.rrect, 0, -scroll)
            canvas.clipRRect(rrect_offset)

        for cmd in self.cmds:
            cmd.execute(scroll, canvas)

        if self.should_clip:
            canvas.restore()


class DrawRRect:
    def __init__(self, rect, radius, color):
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.color = color

    def execute(self, scroll, canvas):
        sk_color = parse_color(self.color)
        rrect_offset = skia.RRect.makeOffset(self.rrect, 0, -scroll)
        canvas.drawRRect(rrect_offset, paint=skia.Paint(Color=sk_color))


def resolve_url(url: str, current: str):
    if "://" in url:
        return url
    elif url.startswith("/"):
        scheme, hostpath = current.split("://", 1)
        host, oldpath = hostpath.split("/", 1)
        return scheme + "://" + host + url
    else:
        dir, _ = current.rsplit("/", 1)
        while url.startswith("../"):
            url = url[3:]
            if dir.count("/") == 2:
                continue
            dir, _ = dir.rsplit("/", 1)
        return dir + "/" + url


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


class CSSParser:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        assert self.i > start
        return self.s[start: self.i]

    def literal(self, literal: str):
        assert self.i < len(self.s) and self.s[self.i] == literal
        self.i += 1

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(':')
        self.whitespace()
        val = self.word()
        return prop.lower(), val

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop.lower()] = val
                self.whitespace()
                self.literal(';')
                self.whitespace()
            except AssertionError:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars: str):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1

    def selector(self):
        out = TagSelector(self.word().lower())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.lower())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                self.whitespace()
                rules.append((selector, body))
            except AssertionError:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules


EVENT_DISPATCH_CODE = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"


def url_origin(url):
    scheme_colon, _, host, _ = url.split('/', 3)
    return f'{scheme_colon}//{host}'


class JSContext:
    def __init__(self, tab) -> None:
        self.tab = tab
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function(
            "XMLHttpRequest_send", self.XMLHttpRequest_send)

        self.node_to_handle = {}
        self.handle_to_node = {}

        with open("runtime.js") as f:
            self.interp.evaljs(f.read())

    def run(self, code):
        return self.interp.evaljs(code)

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    def querySelectorAll(self, selector_text):
        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(self.tab.nodes, [])
                 if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]

    def getAttribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        return elt.attributes.get(attr, None)

    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_CODE, type=type, handle=handle)
        return not do_default

    def innerHTML_set(self, handle, s):
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children

        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt

        self.tab.render()

    def XMLHttpRequest_send(self, method, url, body):
        full_url = resolve_url(url, self.tab.url)
        if not self.tab.allowed_request(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        if url_origin(full_url) != url_origin(self.tab.url):
            raise Exception('Cross-Origin XHR request not allowed')

        headers, out = request(full_url, self.tab.url, payload=body)
        return out


CHROME_PX = 100
COOKIE_JAR = {}


class Tab:
    def __init__(self) -> None:
        self.display_list = []
        self.scroll = 0
        self.history = []
        self.focus = None
        self.url = None

        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()

    def load(self, url, body=None):
        # Request
        headers, body = request(url, self.url, body)

        self.history.append(url)
        self.url = url

        self.allowed_origins = None
        if "content-security-policy" in headers:
            csp = headers["content-security-policy"].split()
            if len(csp) > 0 and csp[0] == "default-src":
                self.allowed_origins = csp[1:]

        # DOM tree
        self.nodes = HTMLParser(body).parse()
        # print_tree(self.nodes)

        # Load styles
        # Browser default styles
        self.rules = self.default_style_sheet.copy()

        # Imported styles
        links = [node.attributes["href"]
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "link"
                 and "href" in node.attributes
                 and node.attributes.get("rel") == "stylesheet"]
        for link in links:
            style_url = resolve_url(link, url)
            if not self.allowed_request(style_url):
                print("Blocked style", link, "due to CSP")
                continue
            try:
                header, body = request(style_url, url)
            except:
                continue
            self.rules.extend(CSSParser(body).parse())

        # Import scripts
        scripts = [node.attributes["src"] for node in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == 'script'
                   and 'src' in node.attributes]

        self.js = JSContext(self)
        for script in scripts:
            script_url = resolve_url(script, url)
            if not self.allowed_request(script_url):
                print("Blocked script", script, "due to CSP")
                continue
            header, body = request(script_url, url)
            try:
                self.js.run(body)
            except dukpy.JSRuntimeError as e:
                print("Script", script, "crashed", e)

        self.render()

    def render(self):
        # Styling
        style(self.nodes, sorted(self.rules, key=cascade_priority))

        # Layout tree
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        # print_tree(self.document)

        # Paint
        self.display_list = []
        self.document.paint(self.display_list)

    def draw(self, canvas):
        for cmd in self.display_list:
            if cmd.rect.fTop > self.scroll + HEIGHT - CHROME_PX:
                continue
            if cmd.rect.fBottom < self.scroll:
                continue
            cmd.execute(self.scroll - CHROME_PX, canvas)

        if self.focus:
            obj = [obj for obj in tree_to_list(self.document, [])
                   if obj.node == self.focus][0]
            text = self.focus.attributes.get("value", "")
            x = obj.x + obj.font.measureText(text)
            y = obj.y - self.scroll + CHROME_PX
            draw_line(canvas, x, y, x, y + obj.height)

    def scroll_up(self):
        if self.scroll > 0:
            self.scroll = max(0, self.scroll - SCROLL_STEP)

    def scroll_down(self):
        max_y = self.document.height - (HEIGHT - CHROME_PX)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def click(self, x, y):
        self.focus = None
        y += self.scroll

        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x+obj.width
                and obj.y <= y < obj.y+obj.height]
        if not objs:
            return
        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == 'a' and "href" in elt.attributes:
                if self.js.dispatch_event("click", elt):
                    return
                url = resolve_url(elt.attributes['href'], self.url)
                return self.load(url)
            elif elt.tag == 'input':
                if self.js.dispatch_event("click", elt):
                    return
                self.focus = elt
                elt.attributes["value"] = ""
                return self.render()
            elif elt.tag == 'button':
                if self.js.dispatch_event("click", elt):
                    return
                while elt:
                    if elt.tag == 'form' and 'action' in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            elt = elt.parent

    def key_press(self, char):
        if self.focus:
            if self.js.dispatch_event("keydown", self.focus):
                return
            self.focus.attributes["value"] += char
            self.render()

    def submit_form(self, elt):
        if self.js.dispatch_event("submit", elt):
            return
        inputs = [node for node in tree_to_list(elt, [])
                  if isinstance(node, Element)
                  and node.tag == 'input'
                  and "name" in node.attributes]

        body = ""
        for input in inputs:
            name = input.attributes.get("name")
            value = input.attributes.get("value", "")
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            body += "&" + name + "=" + value
        body = body[1:]

        url = resolve_url(elt.attributes["action"], self.url)
        self.load(url, body)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def allowed_request(self, url):
        return self.allowed_origins == None or \
            url_origin(url) in self.allowed_origins


class Browser:
    def __init__(self):
        self.sdl_window = sdl2.SDL_CreateWindow(
            b"Browser", sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED, WIDTH, HEIGHT, sdl2.SDL_WINDOW_SHOWN)

        self.root_surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(
                WIDTH, HEIGHT,
                ct=skia.kRGBA_8888_ColorType,
                at=skia.kUnpremul_AlphaType
            )
        )

        if sdl2.SDL_BYTEORDER == sdl2.SDL_BIG_ENDIAN:
            self.RED_MASK = 0xff000000
            self.GREEN_MASK = 0x00ff0000
            self.BLUE_MASK = 0x0000ff00
            self.ALPHA_MASK = 0x000000ff
        else:
            self.RED_MASK = 0x000000ff
            self.GREEN_MASK = 0x0000ff00
            self.BLUE_MASK = 0x00ff0000
            self.ALPHA_MASK = 0xff000000

        self.scroll = 0
        self.url = None
        self.tabs = []
        self.active_tab = None

        self.focus = None
        self.address_bar = ""

    def load(self, url):
        new_tab = Tab()
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.draw()

    def draw(self):
        # Clear all
        canvas = self.root_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        # Draw active tab content
        self.tabs[self.active_tab].draw(canvas)

        # Overwrite any half characters in chrome (tabs + address bar) area
        draw_rect(canvas, 0, 0, WIDTH, CHROME_PX, fill="white")

        # Draw tabs
        tabfont = skia.Font(skia.Typeface('Arial'), 20)
        for i, tab in enumerate(self.tabs):
            name = f"Tab {i}"
            x1, x2 = 40 + 80 * i, 120 + 80 * i
            draw_line(canvas, x1, 0, x1, 40)
            draw_line(canvas, x2, 0, x2, 40)
            draw_text(canvas, x1 + 10, 10, name, tabfont)
            if i == self.active_tab:
                draw_line(canvas, 0, 40, x1, 40)
                draw_line(canvas, x2, 40, WIDTH, 40)

        # Plus button to add a tab
        buttonfont = skia.Font(skia.Typeface('Arial'), 30)
        draw_rect(canvas, 10, 10, 30, 30)
        draw_text(canvas, 11, 4, "+", buttonfont)

        # Draw address bar
        draw_rect(canvas, 40, 50, WIDTH - 10, 90)
        if self.focus == "address bar":
            draw_text(canvas, 55, 55, self.address_bar, buttonfont)
            w = buttonfont.measureText(self.address_bar)
            draw_line(canvas, 55 + w, 55, 55 + w, 85)
        else:
            url = self.tabs[self.active_tab].url
            draw_text(canvas, 55, 55, url, buttonfont)

        # Draw back button
        draw_rect(canvas, 10, 50, 35, 90)
        path = skia.Path().moveTo(15, 70).lineTo(30, 55).lineTo(30, 85)
        paint = skia.Paint(Color=skia.ColorBLACK, Style=skia.Paint.kFill_Style)
        canvas.drawPath(path, paint)

        skia_image = self.root_surface.makeImageSnapshot()
        skia_bytes = skia_image.tobytes()

        depth = 32  # Bits per pixel
        pitch = 4 * WIDTH  # Bytes per row
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes, WIDTH, HEIGHT, depth, pitch,
            self.RED_MASK, self.GREEN_MASK, self.BLUE_MASK, self.ALPHA_MASK
        )

        rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        # SDL_BlitSurface does the actual copy
        sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        sdl2.SDL_UpdateWindowSurface(self.sdl_window)

    def handle_key(self, e):
        if len(e.char) == 0:
            return
        if not (0x20 <= ord(e.char) < 0x7f):
            return
        if self.focus == "address bar":
            self.address_bar += e.char
            self.draw()
        elif self.focus == "content":
            self.tabs[self.active_tab].key_press(e.char)
            self.draw()

    def handle_up(self):
        self.tabs[self.active_tab].scroll_up()
        self.draw()

    def handle_down(self):
        self.tabs[self.active_tab].scroll_down()
        self.draw()

    def handle_enter(self, e):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()

    def handle_backspace(self, e):
        if self.focus == "address bar":
            self.address_bar = self.address_bar[:-1]
            self.draw()

    def handle_scroll_up(self):
        self.tabs[self.active_tab].scroll_up()
        self.draw()

    def handle_scroll_down(self):
        self.tabs[self.active_tab].scroll_down()
        self.draw()

    def handle_mouse_wheel(self, e):
        if e.y == -1:
            self.handle_scroll_down()
        elif e.y == 1:
            self.handle_scroll_up()

    def handle_click(self, e):
        if e.y < CHROME_PX:
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:  # Tabs
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:  # + button, new tab
                self.load("https://browser.engineering/")
            elif 10 <= e.x < 35 and 40 <= e.y < 90:  # Back button
                self.tabs[self.active_tab].go_back()
            elif 50 <= e.x < WIDTH - 10 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
        else:
            self.focus = "content"
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
        self.draw()

    def handle_quit(self):
        sdl2.SDL_DestroyWindow(self.sdl_window)


if __name__ == "__main__":
    import sys
    sdl2.SDL_Init(sdl2.SDL_INIT_EVENTS)
    browser = Browser()
    # browser.load(sys.argv[1])
    browser.load("http://localhost:8000/")

    event = sdl2.SDL_Event()
    while True:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                browser.handle_quit()
                sdl2.SDL_Quit()
                sys.exit()
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                browser.handle_click(event.button)
            elif event.type == sdl2.SDL_MOUSEWHEEL:
                browser.handle_mouse_wheel(event.wheel)
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_RETURN:
                    browser.handle_enter()
                elif event.key.keysym.sym == sdl2.SDLK_BACKSPACE:
                    browser.handle_backspace()
                elif event.key.keysym.sym == sdl2.SDLK_DOWN:
                    browser.handle_down()
                elif event.key.keysym.sym == sdl2.SDLK_UP:
                    browser.handle_up()
            elif event.type == sdl2.SDL_TEXTINPUT:
                browser.handle_key(event.text.text.decode('utf8'))
