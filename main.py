#!/usr/bin/python3

# This is the same as mjpeg_server.py, but uses the h/w MJPEG encoder.

import io
import logging
import socketserver
from http import server
from threading import Condition
import json

# from picamera2 import Picamera2
# from picamera2.encoders import MJPEGEncoder
# from picamera2.outputs import FileOutput


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            with open("index.html", "r") as page:
                content = page.read().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
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
            with open("test.png", "rb") as image:
                frame = image.read()
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', len(frame))
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
        elif self.path == '/update.html':
            content = '{"status": "ok"}'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        print('POST request')
        self.send_response(204)
        self.end_headers()
        data = self.rfile.readline().strip()
        print("{} wrote:".format(self.client_address[0]))
        print(json.loads(data)['light_on'])


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
