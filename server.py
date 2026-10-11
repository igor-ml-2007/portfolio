"""Portfolio server. Public site is open; admin requires password."""
import cgi
import hashlib
import json
import os
import re
from http import HTTPStatus, cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PASSWORD = os.environ.get("ADMIN_PASSWORD") or "atelier"
SESSION_TOKEN = hashlib.sha256(PASSWORD.encode("utf-8")).hexdigest()
COOKIE_NAME = "portfolio_admin"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
PUBLIC_ADMIN = {"/admin/login.html"}


def read_session(header):
    jar = cookies.SimpleCookie()
    try:
        jar.load(header or "")
    except cookies.CookieError:
        return None
    if COOKIE_NAME not in jar:
        return None
    token = jar[COOKIE_NAME].value
    if token == SESSION_TOKEN:
        return True
    return None


class PortfolioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def authorized(self):
        return read_session(self.headers.get("Cookie"))

    def redirect(self, location, status=HTTPStatus.SEE_OTHER):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def require_login(self, html=True):
        if html:
            self.redirect("/admin/login.html")
            return
        self.send_json({"error": "Нужна авторизация"}, HTTPStatus.UNAUTHORIZED)

    def set_session_cookie(self):
        crumb = cookies.SimpleCookie()
        crumb[COOKIE_NAME] = SESSION_TOKEN
        crumb[COOKIE_NAME]["path"] = "/"
        crumb[COOKIE_NAME]["httponly"] = True
        crumb[COOKIE_NAME]["samesite"] = "Lax"
        crumb[COOKIE_NAME]["max-age"] = 60 * 60 * 24 * 30
        self.send_header("Set-Cookie", crumb.output(header="").strip())

    def clear_session_cookie(self):
        crumb = cookies.SimpleCookie()
        crumb[COOKIE_NAME] = ""
        crumb[COOKIE_NAME]["path"] = "/"
        crumb[COOKIE_NAME]["max-age"] = 0
        self.send_header("Set-Cookie", crumb.output(header="").strip())

    def read_body(self, limit=MAX_UPLOAD_BYTES):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > limit:
            return None
        return self.rfile.read(length)

    def parse_login(self, raw):
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return ""
            return str(payload.get("password", ""))
        fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        password = (fields.get("password") or [""])[0]
        return password

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/admin":
            self.redirect("/admin/")
            return

        if path == "/admin/logout":
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/admin/login.html")
            self.clear_session_cookie()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/admin/") and path not in PUBLIC_ADMIN:
            if not self.authorized():
                self.require_login()
                return

        if path == "/api/gallery":
            try:
                with (ROOT / "content/gallery.json").open(encoding="utf-8") as file:
                    data = json.load(file)
                # Ensure all required fields exist
                if "heroImage" not in data:
                    data["heroImage"] = ""
                if "artistImage" not in data:
                    data["artistImage"] = ""
                if "works" not in data:
                    data["works"] = []
                self.send_json(data)
            except (FileNotFoundError, json.JSONDecodeError):
                self.send_json({"works": [], "heroImage": "", "artistImage": ""})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            raw = self.read_body(64 * 1024)
            if raw is None:
                self.redirect("/admin/login.html?error=1")
                return
            password = self.parse_login(raw)
            if password == PASSWORD:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", "/admin/")
                self.set_session_cookie()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.redirect("/admin/login.html?error=1")
            return

        if path not in ("/api/gallery", "/api/upload"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            self.require_login(html=False)
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_UPLOAD_BYTES:
            self.send_json({"error": "Файл больше 12 МБ"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        if path == "/api/gallery":
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload.get("works"), list):
                    raise ValueError
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.send_json({"error": "Некорректные данные"}, HTTPStatus.BAD_REQUEST)
                return
            # Prepare the data to save
            save_data = {
                "works": payload["works"],
                "heroImage": payload.get("heroImage", ""),
                "artistImage": payload.get("artistImage", "")
            }
            temporary = ROOT / "content/gallery.tmp"
            temporary.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(ROOT / "content/gallery.json")
            self.send_json({"ok": True})
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )
        upload = form["image"] if "image" in form else None
        # cgi.FieldStorage deliberately does not support truth-value testing for
        # uploaded files.  `if not upload` raised TypeError here and turned every
        # upload into a 500 response.
        if upload is None or not getattr(upload, "file", None):
            self.send_json({"error": "Файл не получен"}, HTTPStatus.BAD_REQUEST)
            return
        original = Path(upload.filename or "image.jpg").name
        extension = Path(original).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            self.send_json({"error": "Поддерживаются JPG, PNG, WEBP и GIF"}, HTTPStatus.BAD_REQUEST)
            return
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(original).stem).strip("-") or "work"
        destination = ROOT / "photos" / f"{stem}-{os.urandom(4).hex()}{extension}"
        with destination.open("wb") as output:
            output.write(upload.file.read())
        self.send_json({"path": f"/photos/{destination.name}"}, HTTPStatus.CREATED)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), PortfolioHandler)
    print("Portfolio: http://localhost:8000", flush=True)
    print("Admin:     http://localhost:8000/admin/", flush=True)
    print("Password:  " + PASSWORD, flush=True)
    server.serve_forever()
