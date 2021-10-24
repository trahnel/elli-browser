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

  data = "GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n".format(host=host, path=path)
  s.send(data.encode())

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

def lex(body):
  text = ""
  in_angle = False
  in_body = False
  for i in range(0, len(body)):
    c = body[i]
    if c == "<":
      in_angle = True
      if (body[i+1:i+5] == "body"):
        in_body = True
      if (body[i+1:i+6] == "/body"):
        in_body = False
    elif c == ">":
      in_angle = False
    elif in_body and not in_angle:
      text += c
  return text;

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

def layout(text):
  display_list = []
  cursor_x, cursor_y = HSTEP, VSTEP
  for c in text:
    if c == "\n":
      cursor_y += VSTEP
      cursor_x = HSTEP

    display_list.append((cursor_x, cursor_y, c))
    cursor_x += HSTEP

    if cursor_x >= WIDTH - HSTEP:
      cursor_y += VSTEP
      cursor_x = HSTEP
  return display_list;

import tkinter
class Browser:
  def __init__(self):
    self.window = tkinter.Tk()
    self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
    self.canvas.pack()

    self.scroll = 0
    self.window.bind("<Up>", self.scrollup)
    self.window.bind("<Down>", self.scrolldown)

  def load(self, url):
    headers, body = request(url)
    text = lex(body)
    self.display_list = layout(text)
    self.draw()

  def draw(self):
    self.canvas.delete("all")
    for x, y, c in self.display_list:
      if y > self.scroll + HEIGHT: continue
      if y + VSTEP < self.scroll: continue
      self.canvas.create_text(x, y - self.scroll, text=c)

  def scrollup(self, e):
    if self.scroll > 0:
      self.scroll -= SCROLL_STEP
      self.draw()
  
  def scrolldown(self, e):
    self.scroll += SCROLL_STEP
    self.draw()

if __name__ == "__main__":
  import sys
  url = sys.argv[1]
  Browser().load(url)
  tkinter.mainloop()