from app import app, db
import os
import sys
import json

# Initialize database if it doesn't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database initialization error: {e}")

def handler(request):
    """Vercel serverless function handler"""
    try:
        # Build environ dict for Flask
        environ = {
            'REQUEST_METHOD': request.get('method', 'GET'),
            'SCRIPT_NAME': '',
            'PATH_INFO': request.get('path', '/'),
            'QUERY_STRING': request.get('query', {}),
            'CONTENT_TYPE': request.get('headers', {}).get('content-type', ''),
            'CONTENT_LENGTH': str(len(request.get('body', b''))),
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '80',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'https',
            'wsgi.input': request.get('body', b''),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }
        
        # Add headers to environ
        for key, value in request.get('headers', {}).items():
            key = key.upper().replace('-', '_')
            if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                key = 'HTTP_' + key
            environ[key] = value
        
        # Response collector
        response_status = None
        response_headers = []
        response_body = []
        
        def start_response(status, headers):
            nonlocal response_status, response_headers
            response_status = status
            response_headers = headers
            return response_body.append
        
        # Call Flask app
        result = app(environ, start_response)
        
        # Collect response body
        for data in result:
            if data:
                response_body.append(data)
        
        # Build response
        status_code = int(response_status.split()[0])
        headers_dict = {key: value for key, value in response_headers}
        body = b''.join(response_body)
        
        return {
            'statusCode': status_code,
            'headers': headers_dict,
            'body': body.decode('utf-8') if body else ''
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

if __name__ == "__main__":
    app.run()
