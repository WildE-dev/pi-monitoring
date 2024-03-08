#!/usr/bin/python3

import base64
import struct
import threading
from datetime import datetime
import io
import json
import logging
import socketserver
import time
from http import server
import serial

raspi = False

if raspi:
    from PIL import Image, ImageDraw, ImageFont

    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput

settings = {
    "light": False,
    "water": False
}

data = {}

if raspi:
    fnt = ImageFont.truetype("fonts/UbuntuMono-Regular.ttf", 36)


def get_key():
    with open('key.txt') as file:
        return base64.b64encode(file.readline().strip().encode('utf-8')).decode('utf-8')


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

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

        if raspi:
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                        im = Image.open(io.BytesIO(frame))
                        draw = ImageDraw.Draw(im)
                        now = datetime.now()
                        draw.text((10, 10), now.strftime('%Y-%m-%d %H:%M:%S'), font=fnt, fill='white', stroke_fill='black', stroke_width=1)
                        with io.BytesIO() as frame_data:
                            im.save(frame_data, format="JPEG")
                            new_frame = frame_data.getvalue()
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(new_frame))
                    self.end_headers()
                    self.wfile.write(new_frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
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
        elif self.headers.get('Authorization') == 'Basic ' + get_key():
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
        elif self.headers.get('Authorization') == 'Basic ' + get_key():
            self.send_response(204)
            self.end_headers()

            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)
            post_data = json.loads(post_body)
            handle_post(post_data)
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.get('Authorization').encode('utf-8'))
            self.wfile.write('not authenticated'.encode('utf-8'))


def handle_post(post_data):
    global settings
    global ser
    for i in post_data:
        if i in settings:
            settings[i] = post_data[i]

    ser.write(b'l' if settings["light"] else b'0')


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def serial_read():
    global data
    while True:
        ser.read_until(b'\n')
        if ser.in_waiting >= 12:
            [co2] = struct.unpack("H", ser.read(2))
            [soil] = struct.unpack("h", ser.read(2))
            [temperature] = struct.unpack("f", ser.read(4))
            [humidity] = struct.unpack("f", ser.read(4))

            if int(co2) <= 0 or int(soil) < 0 or float(humidity) < 0:
                continue

            data["co2"] = int(co2)
            data["soil_humidity"] = int(soil)
            data["temperature"] = float(temperature)
            data["humidity"] = float(humidity)


if __name__ == "__main__":
    HOST, PORT = "", 8000

    if raspi:
        picam2 = Picamera2()
        picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
        output = StreamingOutput()
        picam2.start_recording(MJPEGEncoder(), FileOutput(output))

        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
    else:
        ser = serial.Serial('COM3', 115200, timeout=1)

    ser.reset_input_buffer()

    t = threading.Thread(target=serial_read)
    t.start()

    # Create the server, binding to localhost on port 8000
    with StreamingServer((HOST, PORT), StreamingHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
            ser.close()
