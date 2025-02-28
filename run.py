"""Run development server."""

import argparse

from metadata_api import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run development server on localhost.")
    parser.add_argument("--port", "-p", type=int, default=1337, help="Port to run the server on (default: 1337)")
    args = parser.parse_args()

    app = create_app(log_to_stdout=True)
    app.run(debug=True, host="localhost", port=args.port)
