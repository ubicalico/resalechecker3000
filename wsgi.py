"""uWSGI entry point. uWSGI loads 'app' from this module (see deploy/uwsgi.ini)."""

from app import app

if __name__ == "__main__":
    app.run()
