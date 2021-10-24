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
    ctx = ssl.create_default_context();
    s = ctx.wrap_socket(s, server_hostname=host)
 
  s.connect((host, port))

  s.send(b"GET /index.html HTTP/1.0\r\n" +
        b"Host: quizicgame.com\r\n" +
        b"\r\n")

  response = s.makefile("r", encoding="utf8", newline="\r\n")

  statusline = response.readline()

  version, status, explanation = statusline.split(" ", 2)
  assert status == "200", "{}: {}".format(status, explanation)

  headers = {}
  while True:
    line = response.readline()
    if (line == "\r\n"): break
    header, value = line.split(":", 1)
    headers[header.lower()] = value.strip()

  body = response.read()
  s.close()

  return headers, body

def show(body):
  in_angle = False
  for c in body:
    if c == "<":
      in_angle = True
    elif c == ">":
      in_angle = False
    elif not in_angle:
      print(c, end="")

def load(url):
  headers, body = request(url)
  show(body)

if __name__ == "__main__":
  import sys
  url = sys.argv[1]
  load(url)