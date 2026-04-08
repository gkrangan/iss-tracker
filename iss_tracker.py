import argparse
import csv
import json
import os
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue, Empty

API_URL = "http://api.open-notify.org/iss-now.json"


def get_iss_position():
    with urllib.request.urlopen(API_URL, timeout=10) as response:
        if response.status != 200:
            raise ConnectionError(f"Failed to fetch data: {response.status}")
        body = response.read().decode("utf-8")
        data = json.loads(body)

    if data.get("message") != "success":
        raise ValueError("API returned failure")

    position = data["iss_position"]
    lat = position["latitude"]
    lon = position["longitude"]
    timestamp = data["timestamp"]
    return lat, lon, timestamp


def format_readable(timestamp, lat, lon):
    readable_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(timestamp))
    return f"{readable_time} | Latitude: {lat} | Longitude: {lon}"


def ensure_csv_header(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp_utc", "latitude", "longitude"])


def append_csv_row(path, timestamp, lat, lon):
    with open(path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(timestamp)), lat, lon])


def parse_args():
    parser = argparse.ArgumentParser(description="Track the ISS position from the Open Notify API.")
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between position requests (default: 5.0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of samples to collect before exiting; 0 means run forever.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional CSV file path to log ISS position updates.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the tracker with a simple GUI instead of the console.",
    )
    return parser.parse_args()


def fetch_loop(interval, output, count, queue, stop_event):
    sample_count = 0
    if output:
        ensure_csv_header(output)

    while not stop_event.is_set() and (count == 0 or sample_count < count):
        try:
            lat, lon, timestamp = get_iss_position()
            readable = format_readable(timestamp, lat, lon)
            queue.put((readable, lat, lon, timestamp, None))
            if output:
                append_csv_row(output, timestamp, lat, lon)
        except Exception as exc:
            queue.put((None, None, None, None, str(exc)))
        sample_count += 1
        if count and sample_count >= count:
            break
        stop_event.wait(interval)

    queue.put(("__DONE__", None, None, None, None))


def run_console(interval, output, count):
    if output:
        ensure_csv_header(output)
        print(f"Logging ISS positions to {output}")

    print(f"Tracking ISS position every {interval} seconds. Press Ctrl+C to stop.")
    sample_count = 0

    try:
        while count == 0 or sample_count < count:
            lat, lon, timestamp = get_iss_position()
            readable = format_readable(timestamp, lat, lon)
            print(readable)
            if output:
                append_csv_row(output, timestamp, lat, lon)
            sample_count += 1
            if count and sample_count >= count:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped tracking.")
    except Exception as e:
        print(f"Error: {e}")


def run_gui(interval, output, count):
    class ISSRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(self.html_page().encode("utf-8"))
            elif self.path == "/data":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                state = self.server.state
                self.wfile.write(json.dumps(state).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return

        def html_page(self):
            return """
<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'>
  <title>ISS Tracker</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    h1 { margin-bottom: 10px; }
    .label { margin: 6px 0; }
    .status { color: #555; margin-top: 14px; }
    #map { height: 400px; width: 100%; margin-top: 20px; }
  </style>
</head>
<body>
  <h1>ISS Tracker</h1>
  <div class='label'><strong>Timestamp:</strong> <span id='timestamp'>waiting...</span></div>
  <div class='label'><strong>Latitude:</strong> <span id='latitude'>-</span></div>
  <div class='label'><strong>Longitude:</strong> <span id='longitude'>-</span></div>
  <div class='status' id='status'>Starting...</div>
  <div id="map"></div>
  <script>
    var map = L.map('map').setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    var issMarker = L.marker([0, 0]).addTo(map).bindPopup('ISS Position');

    async function refresh() {
      try {
        const response = await fetch('/data');
        const data = await response.json();
        if (data.error) {
          document.getElementById('status').textContent = 'Error: ' + data.error;
          return;
        }
        if (data.finished) {
          document.getElementById('status').textContent = 'Finished sampling';
        } else {
          document.getElementById('status').textContent = 'Tracking ISS position';
        }
        if (data.latest) {
          document.getElementById('timestamp').textContent = data.latest.timestamp;
          document.getElementById('latitude').textContent = data.latest.latitude;
          document.getElementById('longitude').textContent = data.latest.longitude;
          var lat = parseFloat(data.latest.latitude);
          var lon = parseFloat(data.latest.longitude);
          issMarker.setLatLng([lat, lon]).openPopup();
          map.setView([lat, lon], 4);
        }
      } catch (err) {
        document.getElementById('status').textContent = 'Error fetching data.';
      }
    }
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""

    def start_server():
        with HTTPServer(("localhost", 0), ISSRequestHandler) as server:
            server.state = {"latest": None, "error": None, "finished": False}
            port = server.server_port
            url = f"http://localhost:{port}"
            print(f"Opening browser GUI at {url}")
            webbrowser.open(url)
            fetch_thread = threading.Thread(
                target=fetch_loop_for_server,
                args=(interval, output, count, server, stop_event),
                daemon=True,
            )
            fetch_thread.start()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass

    def stop_server():
        stop_event.set()

    def fetch_loop_for_server(interval, output, count, server, stop_event):
        sample_count = 0
        if output:
            ensure_csv_header(output)

        while not stop_event.is_set() and (count == 0 or sample_count < count):
            try:
                lat, lon, timestamp = get_iss_position()
                readable = format_readable(timestamp, lat, lon)
                server.state["latest"] = {
                    "timestamp": readable,
                    "latitude": lat,
                    "longitude": lon,
                }
                server.state["error"] = None
                if output:
                    append_csv_row(output, timestamp, lat, lon)
            except Exception as exc:
                server.state["error"] = str(exc)
            sample_count += 1
            if count and sample_count >= count:
                break
            stop_event.wait(interval)

        server.state["finished"] = True
        server.shutdown()

    stop_event = threading.Event()
    start_server()


def main():
    args = parse_args()

    if args.interval <= 0:
        raise ValueError("Interval must be greater than zero.")

    if args.gui:
        run_gui(args.interval, args.output, args.count)
    else:
        run_console(args.interval, args.output, args.count)


if __name__ == "__main__":
    main()
