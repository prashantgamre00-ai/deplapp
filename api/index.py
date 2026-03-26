from app import app, db
import os

# Initialize database if it doesn't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Vercel serverless function handler
handler = app.as_wsgi_app()

if __name__ == "__main__":
    app.run()
