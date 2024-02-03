#!/usr/bin/python3

import base64
from datetime import datetime
import io
import json
import logging
import socketserver
import time
from http import server
from threading import Condition, Lock

from smbus import SMBus
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import DHT
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

DHTPin = 11  # define the pin of DHT11
LEDPin = 15
WaterPin = 13

settings = {
    "light": False,
    "water": False
}

data = {}
data_update_time = 0

fnt = ImageFont.truetype("fonts/UbuntuMono-Regular.ttf", 36)


def get_key():
    with open('key.txt') as file:
        return base64.b64encode(file.readline().strip().encode('utf-8')).decode('utf-8')


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
    for i in post_data:
        if i in settings:
            settings[i] = post_data[i]

    GPIO.output(LEDPin, GPIO.HIGH if settings["light"] else GPIO.LOW)
    GPIO.output(WaterPin, GPIO.HIGH if settings["water"] else GPIO.LOW)


def get_data():
    global data_update_time
    global data

    if data_update_time >= time.time() - 5:
        return json.dumps(data)

    data_update_time = time.time()

    chk = dht.readDHT11()  # Read DHT11 and get a return value.
    if chk == dht.DHTLIB_OK:  # Determine whether data read is normal according to the return value.
        data["temperature"] = dht.temperature
        data["humidity"] = dht.humidity
    else:
        logging.warning("DHT11 Error: " + str(chk))

    data["soil_humidity"] = round(read_ads7830(0) / 2.55)

    return json.dumps(data)


def read_ads7830(location):
    locations = [0x84, 0xc4, 0x94, 0xd4, 0xa4, 0xe4, 0xb4, 0xf4]
    bus.write_byte(0x4b, locations[location])
    return bus.read_byte(0x4b)


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    HOST, PORT = "", 8000

    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
    output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LEDPin, GPIO.OUT)
    GPIO.setup(WaterPin, GPIO.OUT)

    bus = SMBus(1)

    lock = Lock()
    dht = DHT.DHT(DHTPin, lock)  # create a DHT class object

    # Create the server, binding to localhost on port 8000
    with StreamingServer((HOST, PORT), StreamingHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
            GPIO.cleanup()
