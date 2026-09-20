import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from extract import create_http_session, fetch_page


def test_fetch_page_retries_after_service_unavailable(
    tmp_path: Path,
) -> None:
    products = [{"id": 1, "title": "Test product"}]
    response_body = json.dumps(products).encode("utf-8")
    requested_paths = []

    class CatalogHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requested_paths.append(self.path)

            if len(requested_paths) == 1:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    with HTTPServer(("127.0.0.1", 0), CatalogHandler) as server:
        port = server.server_port
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        try:
            with create_http_session() as session:
                # Local test traffic must not depend on environment proxy settings.
                session.trust_env = False

                result = fetch_page(
                    session=session,
                    base_url=f"http://127.0.0.1:{port}",
                    page=1,
                    page_size=25,
                    timeout=2,
                    output_dir=tmp_path,
                )
        finally:
            server.shutdown()
            server_thread.join(timeout=5)

    assert result == products
    assert requested_paths == [
        "/products?_page=1&_limit=25",
        "/products?_page=1&_limit=25",
    ]

    saved_file = tmp_path / "page_0001.json"

    assert saved_file.read_bytes() == response_body