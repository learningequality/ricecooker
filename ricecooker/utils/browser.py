import os, urllib, posixpath, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler


def preview_in_browser(directory, filename="index.html", port=8282):

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

    httpd = HTTPServer(("127.0.0.1", port), RequestHandler)

    webbrowser.open("http://127.0.0.1:{}/{}".format(port, filename))

    httpd.serve_forever()