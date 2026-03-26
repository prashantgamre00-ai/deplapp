from app import app, db, Tool
import os
from http.server import BaseHTTPRequestHandler
from io import BytesIO

# Initialize database if it doesn't exist
def init_database():
    with app.app_context():
        try:
            db.create_all()
            print("Database initialized successfully - v2")
            # Check if we have any tools
            tool_count = Tool.query.count()
            print(f"Current tool count: {tool_count}")
        except Exception as e:
            print(f"Database initialization error: {e}")

# Initialize database
init_database()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print("Processing GET request - v2")
        self.handle_flask_request('GET')
    
    def do_POST(self):
        print("Processing POST request - v2")
        self.handle_flask_request('POST')
    
    def do_PUT(self):
        print("Processing PUT request - v2")
        self.handle_flask_request('PUT')
    
    def do_DELETE(self):
        print("Processing DELETE request - v2")
        self.handle_flask_request('DELETE')
    
    def handle_flask_request(self, method):
        try:
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b''
            
            # Create WSGI environ
            environ = {
                'REQUEST_METHOD': method,
                'SCRIPT_NAME': '',
                'PATH_INFO': self.path,
                'QUERY_STRING': self.path.split('?', 1)[1] if '?' in self.path else '',
                'CONTENT_TYPE': self.headers.get('Content-Type', ''),
                'CONTENT_LENGTH': str(len(body)),
                'SERVER_NAME': 'localhost',
                'SERVER_PORT': '80',
                'SERVER_PROTOCOL': 'HTTP/1.1',
                'wsgi.version': (1, 0),
                'wsgi.url_scheme': 'https',
                'wsgi.input': BytesIO(body),
                'wsgi.errors': self.wfile,
                'wsgi.multithread': False,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False,
            }
            
            # Add headers
            for key, value in self.headers.items():
                key = key.upper().replace('-', '_')
                if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                    key = 'HTTP_' + key
                environ[key] = value
            
            # Response collector
            response_status = None
            response_headers = []
            
            def start_response(status, headers):
                nonlocal response_status, response_headers
                response_status = status
                response_headers = headers
            
            # Call Flask app
            result = app(environ, start_response)
            
            # Send response
            if response_status:
                status_code = int(response_status.split()[0])
                self.send_response(status_code)
                
                for key, value in response_headers:
                    self.send_header(key, value)
                self.end_headers()
                
                for data in result:
                    if data:
                        self.wfile.write(data)
            else:
                self.send_error(500)
                
        except Exception as e:
            print(f"Handler error: {e}")
            self.send_error(500)

if __name__ == "__main__":
    app.run()
