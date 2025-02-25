"""Run development server."""

from metadata_api import create_app

if __name__ == "__main__":
    app = create_app(log_to_stdout=True)
    app.run(debug=True, host="localhost", port=1337)
