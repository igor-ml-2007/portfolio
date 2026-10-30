"""Portfolio server. Public site is open; admin requires password."""
import hashlib
import json
import os
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http import HTTPStatus, cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
PASSWORD = os.environ.get("ADMIN_PASSWORD") or "atelier"
SESSION_TOKEN = hashlib.sha256(PASSWORD.encode("utf-8")).hexdigest()
COOKIE_NAME = "portfolio_admin"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
PUBLIC_ADMIN = {"/admin/login.html"}

# Email configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "gurdalievaekaterina1010@gmail.com")
FORM2EMAIL_URL = os.environ.get(
    "FORM2EMAIL_URL",
    "https://form2email.terragohan.com/f/jtugIZDWVInNWSEYZKSAS01gwW_3paINHmQq4qbYim0",
)
FORM2EMAIL_MANAGE = os.environ.get(
    "FORM2EMAIL_MANAGE",
    "https://form2email.terragohan.com/api/endpoints/e7Vy-OGp0NHEz5ZjSs6hBsgCDfIA_EoKlrUlCC1mRRw",
)
VERIFY_HINT = (
    "На почту художницы ушло письмо для подтверждения формы. "
    "Откройте его, нажмите ссылку и отправьте сообщение ещё раз. "
    "Проверьте «Спам» и «Промоакции»."
)


BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def post_json(url, payload=None, timeout=20):
    body = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": BROWSER_UA,
        },
        method="POST",
    )
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def parse_json(raw):
    try:
        data = json.loads(raw or "")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def extend_mail_endpoint():
    if not FORM2EMAIL_MANAGE:
        return
    try:
        status, raw = post_json(f"{FORM2EMAIL_MANAGE.rstrip('/')}/extend", {})
        print(f"Mail endpoint extend: {status} {raw[:200]}", flush=True)
    except Exception as error:
        print(f"Mail endpoint extend failed: {error}", flush=True)


def send_via_form2email(name, email, message):
    if not FORM2EMAIL_URL:
        return False, "Почта не настроена"
    try:
        status, raw = post_json(
            FORM2EMAIL_URL,
            {
                "name": name,
                "email": email,
                "subject": f"Сообщение с сайта от {name}",
                "message": message,
            },
        )
    except Exception as error:
        print(f"Form2Email send error: {error}", flush=True)
        return False, "Не удалось отправить сообщение"

    data = parse_json(raw)
    print(f"Form2Email response {status}: {raw[:400]}", flush=True)
    if status in {200, 201, 202, 204}:
        extend_mail_endpoint()
        return True, None
    detail = " ".join(
        str(data.get(key) or "")
        for key in ("error", "message", "detail", "title")
    ).lower()
    if status == 403 and ("verif" in detail or "not verified" in detail or "pending" in detail):
        return False, VERIFY_HINT
    return False, data.get("error") or data.get("message") or data.get("detail") or "Ошибка отправки email"


def send_via_smtp(name, email, message):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = "Новое сообщение с сайта-портфолио"
    msg["Reply-To"] = email
    msg.attach(
        MIMEText(
            f"Имя: {name}\nEmail: {email}\n\nСообщение:\n{message}\n",
            "plain",
            "utf-8",
        )
    )
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.send_message(msg)
    server.quit()
    print(f"Email sent successfully to {EMAIL_TO}", flush=True)
    return True, None


def send_email(name, email, message):
    """Send contact form to the artist inbox. Returns (ok, error_message)."""
    if SMTP_USER and SMTP_PASSWORD:
        try:
            return send_via_smtp(name, email, message)
        except Exception as error:
            print(f"Email send error: {error}", flush=True)
            return False, "Ошибка отправки email"
    return send_via_form2email(name, email, message)


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

        if path == "/api/contact":
            raw = self.read_body(64 * 1024)
            if raw is None:
                self.send_json({"error": "Слишком большие данные"}, HTTPStatus.BAD_REQUEST)
                return

            try:
                payload = json.loads(raw.decode("utf-8"))
                name = payload.get("name", "")
                email = payload.get("email", "")
                message = payload.get("message", "")

                if not name or not email or not message:
                    self.send_json({"error": "Все поля обязательны"}, HTTPStatus.BAD_REQUEST)
                    return

                ok, error = send_email(name, email, message)
                if ok:
                    self.send_json({"ok": True})
                else:
                    self.send_json({"error": error or "Ошибка отправки email"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.send_json({"error": "Некорректные данные"}, HTTPStatus.BAD_REQUEST)
            return

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

        # Parse multipart form data manually
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"error": "Некорректный Content-Type"}, HTTPStatus.BAD_REQUEST)
            return

        boundary = content_type.split("boundary=")[1].encode()
        content = self.rfile.read(length)

        # Simple multipart parser
        parts = content.split(b"--" + boundary)
        upload_data = None
        filename = None

        for part in parts[1:-1]:  # Skip first and last (empty) parts
            if b"filename=" in part:
                # Extract filename
                filename_match = re.search(rb'filename="([^"]+)"', part)
                if filename_match:
                    filename = filename_match.group(1).decode("utf-8")
                # Extract content (after headers)
                content_start = part.find(b"\r\n\r\n") + 4
                upload_data = part[content_start:]
                break

        if not upload_data or not filename:
            self.send_json({"error": "Файл не получен"}, HTTPStatus.BAD_REQUEST)
            return

        original = Path(filename).name
        extension = Path(original).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            self.send_json({"error": "Поддерживаются JPG, PNG, WEBP и GIF"}, HTTPStatus.BAD_REQUEST)
            return
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(original).stem).strip("-") or "work"
        destination = ROOT / "photos" / f"{stem}-{os.urandom(4).hex()}{extension}"
        with destination.open("wb") as output:
            output.write(upload_data)
        self.send_json({"path": f"/photos/{destination.name}"}, HTTPStatus.CREATED)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    extend_mail_endpoint()
    server = ThreadingHTTPServer(("0.0.0.0", port), PortfolioHandler)
    print(f"Portfolio: http://localhost:{port}", flush=True)
    print(f"Admin:     http://localhost:{port}/admin/", flush=True)
    print("Password:  " + PASSWORD, flush=True)
    server.serve_forever()
