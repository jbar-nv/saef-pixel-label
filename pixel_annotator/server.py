from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
import re
import sys
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from .database import Database


ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
IMAGE_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "annotations.sqlite3"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_header_options(value: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in value.split(";")]
    main = parts[0].lower() if parts else ""
    options: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            raw = raw[1:-1]
        options[key.strip().lower()] = raw
    return main, options


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    media_type, options = parse_header_options(content_type)
    if media_type != "multipart/form-data" or "boundary" not in options:
        raise ApiError(HTTPStatus.BAD_REQUEST, "Expected multipart form data.")

    boundary = options["boundary"].encode("utf-8")
    delimiter = b"--" + boundary
    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}

    for part in body.split(delimiter):
        if not part or part in {b"--\r\n", b"--"}:
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if part.endswith(b"--"):
            part = part[:-2]

        header_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers: dict[str, str] = {}
        for raw_line in header_blob.split(b"\r\n"):
            line = raw_line.decode("utf-8", errors="replace")
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        disposition = headers.get("content-disposition", "")
        _, disposition_options = parse_header_options(disposition)
        name = disposition_options.get("name")
        if not name:
            continue

        filename = disposition_options.get("filename")
        if filename is not None:
            files[name] = {
                "filename": filename,
                "content_type": headers.get("content-type", "application/octet-stream"),
                "content": content,
            }
        else:
            fields[name] = content.decode("utf-8", errors="replace")

    return fields, files


def safe_join(base: Path, requested_path: str) -> Path:
    decoded = unquote(requested_path).lstrip("/")
    target = (base / decoded).resolve()
    base_resolved = base.resolve()
    if base_resolved != target and base_resolved not in target.parents:
        raise ApiError(HTTPStatus.NOT_FOUND, "File not found.")
    return target


def clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class PixelAnnotationHandler(BaseHTTPRequestHandler):
    server_version = "PixelAnnotation/0.1"

    @property
    def database(self) -> Database:
        return self.server.database  # type: ignore[attr-defined]

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/api/bootstrap":
                username = query.get("user", [""])[0]
                dataset_id = clean_int(query.get("dataset_id", [None])[0], 0)
                active_dataset_id = self.database.resolve_dataset_id(dataset_id)
                self.send_json(
                    {
                        "users": self.database.list_users(),
                        "datasets": self.database.list_datasets(),
                        "active_dataset_id": active_dataset_id,
                        "categories": self.database.list_categories(),
                        "images": self._images_with_urls(username, active_dataset_id),
                    }
                )
                return

            if path == "/api/users":
                self.send_json({"users": self.database.list_users()})
                return

            match = re.fullmatch(r"/api/images/(\d+)", path)
            if match:
                username = query.get("user", [""])[0]
                detail = self.database.image_detail(int(match.group(1)), username)
                detail["image"]["url"] = f'/uploads/{detail["image"]["filename"]}'
                self.send_json(detail)
                return

            match = re.fullmatch(r"/api/images/(\d+)/export\.json", path)
            if match:
                export = self.database.export_distribution(int(match.group(1)))
                self.send_download_json(
                    export,
                    f'pixel-distribution-image-{export["image"]["id"]}.json',
                )
                return

            match = re.fullmatch(r"/api/images/(\d+)/export\.csv", path)
            if match:
                self.send_csv(int(match.group(1)))
                return

            if path.startswith("/uploads/"):
                target = safe_join(IMAGE_DIR, path.removeprefix("/uploads/"))
                self.send_file(target)
                return

            if path == "/":
                self.send_file(STATIC_DIR / "index.html")
                return

            target = safe_join(STATIC_DIR, path)
            self.send_file(target)
        except ApiError as exc:
            self.send_error_json(exc.status, exc.message)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except Exception as exc:  # pragma: no cover
            self.log_error("Unhandled error: %s", exc)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected server error.")

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/images":
                self.handle_image_upload()
                return

            if path == "/api/categories":
                payload = self.read_json()
                name = str(payload.get("name", "")).strip()
                color = str(payload.get("color", "#0f8f7a")).strip()
                if not HEX_COLOR_PATTERN.fullmatch(color):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Category color must be a hex value.")
                self.send_json(self.database.create_category(name, color), HTTPStatus.CREATED)
                return

            if path == "/api/datasets":
                payload = self.read_json()
                dataset = self.database.create_dataset(str(payload.get("name", "")))
                self.send_json(dataset, HTTPStatus.CREATED)
                return

            if path == "/api/users":
                payload = self.read_json()
                user = self.database.create_user(str(payload.get("username", "")))
                self.send_json(user, HTTPStatus.CREATED)
                return

            match = re.fullmatch(r"/api/images/(\d+)/pixels/random", path)
            if match:
                payload = self.read_json()
                count = min(max(clean_int(payload.get("count"), 0), 0), 10000)
                seed_value = payload.get("seed")
                seed = clean_int(seed_value) if seed_value not in (None, "") else None
                inserted = self.database.add_random_pixels(int(match.group(1)), count, seed)
                self.send_json({"inserted": inserted})
                return

            match = re.fullmatch(r"/api/images/(\d+)/pixels", path)
            if match:
                payload = self.read_json()
                pixel = self.database.add_pixel(
                    int(match.group(1)),
                    clean_int(payload.get("x"), -1),
                    clean_int(payload.get("y"), -1),
                )
                self.send_json(pixel, HTTPStatus.CREATED)
                return

            if path == "/api/annotations":
                payload = self.read_json()
                self.database.set_annotation(
                    clean_int(payload.get("pixel_id"), -1),
                    str(payload.get("username", "")),
                    clean_int(payload.get("category_id"), -1),
                )
                self.send_json({"ok": True})
                return

            raise ApiError(HTTPStatus.NOT_FOUND, "Endpoint not found.")
        except ApiError as exc:
            self.send_error_json(exc.status, exc.message)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover
            self.log_error("Unhandled error: %s", exc)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected server error.")

    def do_PUT(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            match = re.fullmatch(r"/api/categories/(\d+)", path)
            if match:
                payload = self.read_json()
                name = str(payload.get("name", "")).strip()
                color = str(payload.get("color", "#0f8f7a")).strip()
                if not HEX_COLOR_PATTERN.fullmatch(color):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Category color must be a hex value.")
                category = self.database.update_category(int(match.group(1)), name, color)
                self.send_json(category)
                return

            match = re.fullmatch(r"/api/datasets/(\d+)", path)
            if match:
                payload = self.read_json()
                dataset = self.database.update_dataset(
                    int(match.group(1)),
                    str(payload.get("name", "")),
                )
                self.send_json(dataset)
                return

            match = re.fullmatch(r"/api/users/(\d+)", path)
            if match:
                payload = self.read_json()
                user = self.database.update_user(
                    int(match.group(1)),
                    str(payload.get("username", "")),
                )
                self.send_json(user)
                return

            match = re.fullmatch(r"/api/pixels/(\d+)", path)
            if match:
                payload = self.read_json()
                pixel = self.database.move_pixel(
                    int(match.group(1)),
                    clean_int(payload.get("x"), -1),
                    clean_int(payload.get("y"), -1),
                )
                self.send_json(pixel)
                return

            raise ApiError(HTTPStatus.NOT_FOUND, "Endpoint not found.")
        except ApiError as exc:
            self.send_error_json(exc.status, exc.message)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover
            self.log_error("Unhandled error: %s", exc)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected server error.")

    def do_DELETE(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            match = re.fullmatch(r"/api/categories/(\d+)", path)
            if match:
                result = self.database.delete_category(int(match.group(1)))
                self.send_json(result)
                return

            match = re.fullmatch(r"/api/users/(\d+)", path)
            if match:
                result = self.database.delete_user(int(match.group(1)))
                self.send_json(result)
                return

            match = re.fullmatch(r"/api/images/(\d+)", path)
            if match:
                result = self.database.delete_image(int(match.group(1)))
                filename = str(result.pop("filename", ""))
                deleted_file = 0
                if filename:
                    target = safe_join(IMAGE_DIR, filename)
                    if target.exists():
                        target.unlink()
                        deleted_file = 1
                result["deleted_file"] = deleted_file
                self.send_json(result)
                return

            match = re.fullmatch(r"/api/images/(\d+)/pixels", path)
            if match:
                result = self.database.reset_image_pixels(int(match.group(1)))
                self.send_json(result)
                return

            match = re.fullmatch(r"/api/images/(\d+)/annotations", path)
            if match:
                deleted = self.database.reset_image_annotations(int(match.group(1)))
                self.send_json({"deleted_annotations": deleted})
                return

            raise ApiError(HTTPStatus.NOT_FOUND, "Endpoint not found.")
        except ApiError as exc:
            self.send_error_json(exc.status, exc.message)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover
            self.log_error("Unhandled error: %s", exc)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected server error.")

    def handle_image_upload(self) -> None:
        if Image is None:
            raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "Pillow is required for image uploads.")

        body = self.read_body(MAX_UPLOAD_BYTES)
        fields, files = parse_multipart(self.headers.get("Content-Type", ""), body)
        image_file = files.get("image")
        if image_file is None or not image_file["content"]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Image file is required.")

        original_name = Path(image_file["filename"]).name or "image"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Unsupported image format.")

        content = image_file["content"]
        try:
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Could not read image file.") from exc

        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        target_path = IMAGE_DIR / stored_name
        target_path.write_bytes(content)

        display_name = fields.get("name", "").strip() or original_name
        pixel_count = min(max(clean_int(fields.get("pixel_count"), 25), 0), 10000)
        dataset_id = clean_int(fields.get("dataset_id"), 0)
        image_record = self.database.create_image(
            display_name,
            stored_name,
            width,
            height,
            dataset_id,
        )
        inserted = self.database.add_random_pixels(image_record.id, pixel_count)
        detail = self.database.image_detail(image_record.id, fields.get("user", ""))
        detail["image"]["url"] = f'/uploads/{detail["image"]["filename"]}'
        detail["inserted_pixels"] = inserted
        self.send_json(detail, HTTPStatus.CREATED)

    def read_body(self, max_bytes: int = 1024 * 1024) -> bytes:
        content_length = clean_int(self.headers.get("Content-Length"), 0)
        if content_length <= 0:
            return b""
        if content_length > max_bytes:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.")
        return self.rfile.read(content_length)

    def read_json(self) -> dict[str, Any]:
        body = self.read_body()
        if not body:
            return {}
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid JSON payload.") from exc
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON payload must be an object.")
        return payload

    def _images_with_urls(
        self,
        username: str = "",
        dataset_id: int | None = None,
    ) -> list[dict[str, Any]]:
        images = self.database.list_images(username, dataset_id)
        for image in images:
            image["url"] = f'/uploads/{image["filename"]}'
        return images

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"error": message}, status)

    def send_download_json(self, payload: Any, filename: str) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_csv(self, image_id: int) -> None:
        export = self.database.export_distribution(image_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "image_id",
                "image_name",
                "pixel_id",
                "x",
                "y",
                "total_votes",
                "consensus",
                "category",
                "votes",
                "probability",
            ]
        )
        for pixel in export["pixels"]:
            for category in export["categories"]:
                name = category["name"]
                writer.writerow(
                    [
                        export["image"]["id"],
                        export["image"]["name"],
                        pixel["pixel_id"],
                        pixel["x"],
                        pixel["y"],
                        pixel["total_votes"],
                        pixel["consensus"] or "",
                        name,
                        pixel["votes"].get(name, 0),
                        f'{pixel["probabilities"].get(name, 0):.8f}',
                    ]
                )
        body = output.getvalue().encode("utf-8")
        filename = f'pixel-distribution-image-{export["image"]["id"]}.csv'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "File not found.")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


class PixelAnnotationServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], database: Database):
        super().__init__(server_address, PixelAnnotationHandler)
        self.database = database


def build_server(host: str, port: int, database_path: Path = DB_PATH) -> PixelAnnotationServer:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    database = Database(database_path)
    database.initialize()
    return PixelAnnotationServer((host, port), database)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the pixel annotation web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=DB_PATH)
    args = parser.parse_args(argv)

    server = build_server(args.host, args.port, args.database)
    url = f"http://{args.host}:{args.port}"
    print(f"Pixel annotator running at {url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
