from http.server import BaseHTTPRequestHandler, HTTPServer

class HandleRequests(BaseHTTPRequestHandler):
    def do_GET(self):
        print("Принял get запрос")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"hello !")


host = ''
port = 9090
print("start")
HTTPServer((host, port), HandleRequests).serve_forever()