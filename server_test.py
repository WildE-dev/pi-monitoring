#!/usr/bin/python3

import base64
import io
import json
import socketserver
from http import server
from threading import Condition

# from picamera2 import Picamera2
# from picamera2.encoders import MJPEGEncoder
# from picamera2.outputs import FileOutput

settings = {
    "light": False
}


def get_key():
    with open('key.txt') as file:
        return base64.b64encode(file.read().encode('utf-8'))


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


def get_page(self):
    if self.path == '/':
        with open("static/index.html", "r") as page:
            content = page.read().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    elif self.path == '/stream.mjpg':
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()

        # Test image
        with open("static/test.png", "rb") as image:
            frame = image.read()
            self.wfile.write(b'--FRAME\r\n')
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)
            self.wfile.write(b'\r\n')
    elif self.path == '/data.json':
        content = get_data().encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/json')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)
    elif self.path == '/script.js':
        with open("static/script.js", "r") as script:
            content = script.read().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    elif self.path == '/styles.css':
        with open("static/styles.css", "r") as script:
            content = script.read().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/css')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    else:
        self.send_error(404)
        self.end_headers()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization') is None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received'.encode('utf-8'))
        elif self.headers.get('Authorization') == 'Basic ' + get_key().decode('utf-8'):
            get_page(self)
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.get('Authorization').encode('utf-8'))
            self.wfile.write('not authenticated'.encode('utf-8'))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Test"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_POST(self):
        if self.headers.get('Authorization') is None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received'.encode('utf-8'))
        elif self.headers.get('Authorization') == 'Basic ' + get_key().decode('utf-8'):
            self.send_response(204)
            self.end_headers()

            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)

            post_data = json.loads(post_body)

            handle_post(post_data)
            print(post_data)
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.get('Authorization').encode('utf-8'))
            self.wfile.write('not authenticated'.encode('utf-8'))


def handle_post(post_data):
    global settings
    if "light" in post_data:
        settings['light'] = post_data['light']

    print(settings)


def get_data():
    dummy_data = {
        "temperature": 22.4,
        "humidity": 67.3,
        "soil_humidity": 82.1
    }
    return json.dumps(dummy_data)


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    HOST, PORT = "", 8000

    # Create the server, binding to localhost on port 8000
    with StreamingServer((HOST, PORT), StreamingHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
