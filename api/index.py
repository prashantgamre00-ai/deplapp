from app import app

# Vercel serverless function handler
handler = app.as_wsgi_app()

if __name__ == "__main__":
    app.run()
