from app import app, db
import os

# Initialize database if it doesn't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Export app for Vercel
handler = app

if __name__ == "__main__":
    app.run()
