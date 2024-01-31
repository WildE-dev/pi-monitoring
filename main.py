#!/usr/bin/python3

import io
import logging
import socketserver
from http import server
from threading import Condition
import json
import base64

# from picamera2 import Picamera2
# from picamera2.encoders import MJPEGEncoder
# from picamera2.outputs import FileOutput

key = base64.b64encode("admin:SuperSecurePassword1".encode('utf-8'))
data = {
    "temperature": 22.4,
    "humidity": 67.3,
    "atm_pressure": 1.1
}


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

    #            try:
    #                while True:
    #                    with output.condition:
    #                        output.condition.wait()
    #                        frame = output.frame
    #                    self.wfile.write(b'--FRAME\r\n')
    #                    self.send_header('Content-Type', 'image/jpeg')
    #                    self.send_header('Content-Length', len(frame))
    #                    self.end_headers()
    #                    self.wfile.write(frame)
    #                    self.wfile.write(b'\r\n')
    #            except Exception as e:
    #                logging.warning(
    #                    'Removed streaming client %s: %s',
    #                    self.client_address, str(e))
    elif self.path == '/data.json':
        content = json.dumps(data).encode('utf-8')
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
    else:
        self.send_error(404)
        self.end_headers()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global key
        if self.headers.get('Authorization') is None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received'.encode('utf-8'))
        elif self.headers.get('Authorization') == 'Basic ' + key.decode('utf-8'):
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
        global key
        if self.headers.get('Authorization') is None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received'.encode('utf-8'))
        elif self.headers.get('Authorization') == 'Basic ' + key.decode('utf-8'):
            self.send_response(204)
            self.end_headers()

            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)
            global data
            data = json.loads(post_body)
            print(data)
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.get('Authorization').encode('utf-8'))
            self.wfile.write('not authenticated'.encode('utf-8'))


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    HOST, PORT = "", 8000

    # picam2 = Picamera2()
    # picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
    # output = StreamingOutput()
    # picam2.start_recording(MJPEGEncoder(), FileOutput(output))

    # Create the server, binding to localhost on port 8000
    with StreamingServer((HOST, PORT), StreamingHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()
