import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>Server is working!</h1>')
    
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"success": true, "message": "API working"}')

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

print("Checking ports...")
for port in [5000, 8000, 8080, 3000]:
    if check_port(port):
        print(f"Port {port} is in use")
    else:
        print(f"Port {port} is available")

port = 8000
print(f"\nStarting server on port {port}...")
print(f"Open: http://localhost:{port}")
server = HTTPServer(('0.0.0.0', port), SimpleHandler)
server.serve_forever()