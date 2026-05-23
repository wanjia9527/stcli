import os
import threading
import socket
from flask import Flask, send_from_directory


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def create_flask_app():
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    static_dir = os.path.abspath(static_dir)
    app = Flask(__name__, static_folder=static_dir)

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(static_dir, filename)

    return app, static_dir


def start_gui():
    import webview
    from web.bridge import ApiBridge

    flask_app, static_dir = create_flask_app()
    port = _find_free_port()

    server_thread = threading.Thread(
        target=lambda: flask_app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    bridge = ApiBridge()
    window = webview.create_window(
        title="stcli",
        url=f"http://127.0.0.1:{port}",
        js_api=bridge,
        width=1000,
        height=700,
        min_size=(800, 500),
    )
    bridge.set_window(window)
    webview.start(gui="edgechromium", debug=False)
