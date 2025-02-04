"""Run development server."""

from metadata_api import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="localhost", port=1337)
