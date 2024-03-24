#!/usr/bin/python3

import base64
import csv
import os
import sqlite3
import struct
import threading
from datetime import datetime, time
import io
import json
import logging
import socketserver
from http import server
from time import sleep

import serial

raspi = os.name == 'posix'

if raspi:
    from PIL import Image, ImageDraw, ImageFont

    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput

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
                        draw.text((10, 10), now.strftime('%Y-%m-%d %H:%M:%S'), font=fnt, fill='white',
                                  stroke_fill='black', stroke_width=1)
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
        global connections
        content = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/json')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        connections += 1
    elif self.path == '/readings.csv':
        conn = sqlite3.connect('readings.db')
        c = conn.cursor()
        c.execute("select * from readings")

        with io.StringIO() as f:
            results = c.fetchall()

            # Extract the table headers.
            headers = [i[0] for i in c.description]

            # Open CSV file for writing.
            csv_file = csv.writer(f,
                                  delimiter=',', lineterminator='\r\n',
                                  quoting=csv.QUOTE_ALL, escapechar='\\')

            # Add the headers and data to the CSV file.
            csv_file.writerow(headers)
            csv_file.writerows(results)
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            # self.send_header('Transfer-Encoding', 'chunked')
            bin_data = f.getvalue().encode('utf-8')
            self.send_header('Content-Length', str(len(bin_data)))
            self.end_headers()
            self.wfile.write(bin_data)

        c.close()
        conn.close()
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

    # def do_POST(self):
    #     if self.headers.get('Authorization') is None:
    #         self.do_AUTHHEAD()
    #         self.wfile.write('no auth header received'.encode('utf-8'))
    #     elif self.headers.get('Authorization') == 'Basic ' + get_key():
    #         self.send_response(204)
    #         self.end_headers()
    #
    #         content_len = int(self.headers.get('Content-Length', 0))
    #         post_body = self.rfile.read(content_len)
    #         post_data = json.loads(post_body)
    #         handle_post(post_data)
    #     else:
    #         self.do_AUTHHEAD()
    #         self.wfile.write(self.headers.get('Authorization').encode('utf-8'))
    #         self.wfile.write('not authenticated'.encode('utf-8'))


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def in_between(now, start, end):
    if start <= end:
        return start <= now < end
    else:  # over midnight e.g., 23:30-04:15
        return start <= now or now < end


def write_loop():
    global connections
    while True:
        is_day = in_between(datetime.now().time(), time(hour=8, minute=0), time(hour=20, minute=0))
        ser.write(b'l' if connections > 0 or is_day else b'0')
        connections = 0
        sleep(10)


def serial_read():
    global data  # , last_check
    # conn = sqlite3.connect('readings.db')
    # c = conn.cursor()
    while raspi:
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

    #         if last_check + read_time < time.time():
    #             continue
    #
    #         last_check = time.time()
    #
    #         iso_time = datetime.now().isoformat()
    #
    #         query = f"""
    #             INSERT INTO readings (time, co2, soil, temperature, humidity)
    #             VALUES ('{iso_time}',{int(co2)},{int(soil)},{float(temperature)},{float(humidity)});
    #         """
    #
    #         c.execute(query)
    #         conn.commit()
    #
    # c.close()
    # conn.close()


if __name__ == "__main__":
    HOST, PORT = "", 8000

    data = {}
    connections = 0

    # read_time = 30

    # last_check = 0

    if raspi:
        picam2 = Picamera2()
        picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
        output = StreamingOutput()
        picam2.start_recording(MJPEGEncoder(), FileOutput(output))

        ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
        ser.reset_input_buffer()
    # else:
    # ser = serial.Serial('COM3', 115200, timeout=1)
    # ser.reset_input_buffer()

    db = sqlite3.connect('readings.db')
    cursor = db.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS readings( 
    time TEXT, 
    co2 INTEGER, 
    soil INTEGER, 
    temperature REAL, 
    humidity REAL);''')
    db.commit()

    t1 = threading.Thread(target=serial_read)
    t2 = threading.Thread(target=write_loop)
    t1.start()
    t2.start()

    # Create the server, binding to localhost on port 8000
    with StreamingServer((HOST, PORT), StreamingHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
            cursor.close()
            db.close()
            if raspi:
                ser.close()
