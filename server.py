import html
import random
import socket
import urllib.parse
from datetime import datetime

ENTRIES = [('Tomte was here', 'santa'),
           ("No names. We are nameless!", "cerealkiller"),
           ("HACK THE PLANET!!!", "crashoverride"),
           ]

LOGINS = {
    'crashoverride': '0cool',
    'cerealkiller': 'emmanuel',
    '': ''
}

SESSIONS = {}


def do_login(session, params):
    if 'nonce' not in session or 'nonce' not in params:
        return
    if session['nonce'] != params['nonce']:
        return

    username = params.get('username')
    password = params.get('password')
    if username in LOGINS and LOGINS[username] == password:
        session["user"] = username
        return "200 OK", show_comments(session)

    out = '<!doctype html>'
    out += f'<h1>Invalid password for {username}</h1>'
    return "401 Unauthorized", out


def login_form(session):
    nonce = str(random.random())[2:]
    session['nonce'] = nonce

    body = '<!doctype html>'
    body += '<form action=/ method=post>'
    body += '<p>Username: <input name=username></p>'
    body += '<p>Password: <input name=password type=password></p>'
    body += '<p><button>Log in</button></p>'
    body += f'<input name=nonce type=hidden value={nonce}>'
    body += '</form>'
    return body


def show_comments(session):
    out = "<!doctype html>"

    for entry, who in ENTRIES:
        out += f'<p>{html.escape(entry)}\n'
        out += f'by <i> {html.escape(who)}</i></p>'

    if "user" in session:
        nonce = str(random.random())[2:]
        session['nonce'] = nonce

        out += f'<h1>Hello, {session["user"]}</h1>'
        out += '<form action=add method=post>'
        out += '<p><input name=guest></p>'
        out += '<p><button>Sign the book!</button></p>'
        out += f'<input name=nonce type=hidden value={nonce}>'
        out += '</form>'
    else:
        out += '<a href=/login>Sign in to write in the guest book</a>'

    out += "<label></label>"
    out += "<script src=/comment.js></script>"

    return out


def form_decode(body: str):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params


def add_entry(session, params):
    if 'nonce' not in session or 'nonce' not in params:
        return
    if session['nonce'] != params['nonce']:
        return
    if 'user' not in session:
        return

    if 'guest' in params and len(params['guest']) <= 100:
        ENTRIES.append((params['guest'], session['user']))


def not_found(url, method):
    out = "<!doctype html>"
    out += f'<h1>{url} {method} not found!</h1>'
    return out


def do_request(session, method, url, headers, body):
    if method == "GET" and url == "/":
        return "200 OK", show_comments(session)

    if method == "GET" and url == "/index.html":
        with open("index.html") as f:
            return "200 OK", f.read()

    if method == "GET" and url == "/index.js":
        with open("index.js") as f:
            return "200 OK", f.read()

    if method == "GET" and url == "/count":
        return "200 OK", show_count()

    if method == "POST" and url == "/":
        params = form_decode(body)
        return do_login(session, params)

    if method == "GET" and url == '/login':
        return "200 OK", login_form(session)

    if method == "GET" and url == "/comment.js":
        with open("comment.js") as f:
            return "200 OK", f.read()

    if method == "GET" and url == "/eventloop.js":
        with open("eventloop.js") as f:
            return "200 OK", f.read()

    if method == "GET" and url == "/opacity":
        return "200 OK", opacity()

    if method == "GET" and url == "/example13-opacity-raf.js":
        with open("example13-opacity-raf.js") as f:
            return "200 OK", f.read()

    if method == "POST" and url == "/add":
        params = form_decode(body)
        add_entry(session, params)
        return "200 OK", show_comments(session)

    return "404 Not Found", not_found(url, method)


def opacity():
    out = "<button>Fade out</button>"
    out += "<button>Fade in</button>"
    out += "<div>This text fades</div>"
    out += "<script src=example13-opacity-raf.js></script>"
    return out


def show_count():
    out = "<!doctype html>"
    out += "<div>"
    out += "  Let's count up to 99!"
    out += "</div>"
    out += "<div>Output</div>"
    out += "<script src=/eventloop.js></script>"
    return out


def log_request(method, url, status):
    # [24/Jan/2022 12:54:18] "POST /submit HTTP/1.0" 501 -
    now = datetime.now()
    now_str = now.strftime("%d/%m/%Y %H:%M:%S")
    print(f'[{now_str}] "{method} {url}" {status}')


def handle_connection(conx):
    req = conx.makefile("b")
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    assert method in ["GET", "POST"]

    headers = {}
    for line in req:
        line = line.decode('utf8')
        if line == '\r\n':
            break
        header, value = line.split(':', 1)
        headers[header.lower()] = value.strip()

    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf_8')
    else:
        body = None

    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]

    session = SESSIONS.setdefault(token, {})
    status, body = do_request(session, method, url, headers, body)
    log_request(method, url, status)

    response = f'HTTP/1.0 {status}\r\n'
    length = len(body.encode("utf8"))
    response += f'Content-Length: {length}\r\n'
    if 'cookie' not in headers:
        response += f'Set-Cookie: token={token}; SameSite=Lax\r\n'
    csp = "default-src http://localhost:8000"
    response += f"Content-Security-Policy: {csp}\r\n"

    response += f'\r\n{body}'

    conx.send(response.encode('utf8'))
    conx.close()


PORT = 8000
if __name__ == '__main__':
    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP
    )
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', PORT))
    s.listen()
    print(f"Server running on port {PORT}...")

    while True:
        conx, addr = s.accept()
        handle_connection(conx)
