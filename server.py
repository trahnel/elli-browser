from cmath import log
import urllib.parse
from datetime import datetime
import socket
s = socket.socket(
    family=socket.AF_INET,
    type=socket.SOCK_STREAM,
    proto=socket.IPPROTO_TCP
)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(('', 8000))
s.listen()

ENTRIES = ['Tomte was here']


def show_comments():
    out = "<!doctype html>"
    for entry in ENTRIES:
        out += f"<p>{entry}</p>"

    out += "<form action=add method=post>"
    out += "<p><input name=guest></p>"
    out += "<p><button>Sign the book!</button></p>"
    out += "</form>"

    return out


def form_decode(body: str):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params


def add_entry(params):
    if 'guest' in params:
        ENTRIES.append(params['guest'])
    return show_comments()


def not_found(url, method):
    out = "<!doctype html>"
    out += f'<h1>{url} {method} not found!</h1>'
    return out


def do_request(method, url, headers, body):
    if method == "GET" and url == "/":
        return "200 OK", show_comments()

    if method == "POST" and url == "/add":
        params = form_decode(body)
        return "200 OK", add_entry(params)

    return "404 Not Found", not_found(url, method)


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

    status, body = do_request(method, url, headers, body)
    log_request(method, url, status)

    response = f'HTTP/1.0 {status}\r\n'
    length = len(body.encode("utf8"))
    response += f'Content-Length: {length}\r\n'
    response += f'\r\n{body}'
    conx.send(response.encode('utf8'))
    conx.close()


while True:
    conx, addr = s.accept()
    handle_connection(conx)
