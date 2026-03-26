from app import app, db
import os
from http.server import BaseHTTPRequestHandler

# Initialize database if it doesn't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Vercel serverless function handler class
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with app.test_client() as client:
            response = client.get(self.path)
            self.wfile.write(response.data)

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with app.test_client() as client:
            response = client.post(self.path)
            self.wfile.write(response.data)

if __name__ == "__main__":
    app.run()
