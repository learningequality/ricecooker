import os
import posixpath
import sys
import urllib
import webbrowser

from http.server import HTTPServer, HTTPStatus, SimpleHTTPRequestHandler

SERVER = "127.0.0.1"
PORT = 8282


class IFrameServerRequestHandler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_access_control_headers()
        self.send_response(200, "ok")

    def send_access_control_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With")

    def do_GET(self):
        path = self.translate_path(self.path)
        print("path = {}".format(path))
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            fs = os.fstat(f.fileno())
            self.send_header("Content-Length", str(fs.st_size))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

            self.send_access_control_headers()

            self.send_header("Content-Security-Policy",
                             "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: http://{}:{}".format(SERVER, PORT))
            self.end_headers()
        except:
            f.close()
            raise

        if f:
            try:
                self.copyfile(f, self.wfile)
            finally:
                f.close()
        return


def preview_in_browser(directory, filename="index.html"):

    class RequestHandler(SimpleHTTPRequestHandler):

        def translate_path(self, path):
            # abandon query parameters
            path = path.split('?',1)[0]
            path = path.split('#',1)[0]
            path = posixpath.normpath(urllib.parse.unquote(path))
            words = path.split('/')
            words = filter(None, words)
            path = directory
            for word in words:
                drive, word = os.path.splitdrive(word)
                head, word = os.path.split(word)
                if word in (os.curdir, os.pardir): continue
                path = os.path.join(path, word)
            return path

    httpd = HTTPServer((SERVER, PORT), RequestHandler)

    webbrowser.open("http://{}:{}/{}".format(SERVER, PORT, filename))

    httpd.serve_forever()

def iframe_preview(filepath):

    filename = "index.html"
    directory = filepath
    if not os.path.isdir(filepath):
        filename = os.path.basename(filepath)
        directory = os.path.dirname(filepath)

    os.chdir(directory)
    httpd = HTTPServer((SERVER, PORT), IFrameServerRequestHandler)

    webbrowser.open("http://{}:{}/{}".format(SERVER, PORT, filename))

    httpd.serve_forever()

def load_server(path, iframe=False):
    if iframe:
        print("Starting local server and iframe sandbox...")
        iframe_preview(path)

    else:
        print("Starting local server...")
        preview_in_browser(path)
