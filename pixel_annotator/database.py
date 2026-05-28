from __future__ import annotations

import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CATEGORIES = [
    ("background", "#44515f"),
    ("target", "#0f8f7a"),
    ("boundary", "#d78b1f"),
    ("uncertain", "#8a5cf6"),
]
DEFAULT_DATASET_NAME = "Default dataset"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ImageRecord:
    id: int
    name: str
    filename: str
    width: int
    height: int
    created_at: str


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY,
                    dataset_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL UNIQUE,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS pixels (
                    id INTEGER PRIMARY KEY,
                    image_id INTEGER NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                    UNIQUE (image_id, x, y)
                );

                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY,
                    pixel_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (pixel_id) REFERENCES pixels(id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories(id),
                    UNIQUE (pixel_id, username)
                );

                CREATE INDEX IF NOT EXISTS idx_pixels_image ON pixels(image_id);
                CREATE INDEX IF NOT EXISTS idx_annotations_pixel ON annotations(pixel_id);
                CREATE INDEX IF NOT EXISTS idx_annotations_user ON annotations(username);
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                """
            )
            default_dataset_id = self._ensure_default_dataset(conn)
            self._ensure_images_dataset_column(conn, default_dataset_id)
            self._ensure_users_from_annotations(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_images_dataset ON images(dataset_id)"
            )
            for name, color in DEFAULT_CATEGORIES:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO categories (name, color, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (name, color, utc_now()),
                )

    def _ensure_users_from_annotations(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, created_at)
            SELECT username, MIN(created_at)
            FROM annotations
            WHERE TRIM(username) != ''
            GROUP BY username
            """
        )

    def _ensure_user(self, conn: sqlite3.Connection, username: str) -> dict[str, Any]:
        clean_user = username.strip()
        if not clean_user:
            raise ValueError("Username is required.")
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, created_at)
            VALUES (?, ?)
            """,
            (clean_user, utc_now()),
        )
        row = conn.execute(
            """
            SELECT id, username, created_at
            FROM users
            WHERE username = ?
            """,
            (clean_user,),
        ).fetchone()
        return dict(row)

    def _ensure_default_dataset(self, conn: sqlite3.Connection) -> int:
        conn.execute(
            """
            INSERT OR IGNORE INTO datasets (name, created_at)
            VALUES (?, ?)
            """,
            (DEFAULT_DATASET_NAME, utc_now()),
        )
        row = conn.execute(
            "SELECT id FROM datasets WHERE name = ?",
            (DEFAULT_DATASET_NAME,),
        ).fetchone()
        return int(row["id"])

    def _ensure_images_dataset_column(
        self,
        conn: sqlite3.Connection,
        default_dataset_id: int,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(images)").fetchall()
        }
        if "dataset_id" not in columns:
            conn.execute("ALTER TABLE images ADD COLUMN dataset_id INTEGER")
        conn.execute(
            "UPDATE images SET dataset_id = ? WHERE dataset_id IS NULL",
            (default_dataset_id,),
        )

    def resolve_dataset_id(self, dataset_id: int | None = None) -> int:
        with self.session() as conn:
            if dataset_id is not None and dataset_id > 0:
                row = conn.execute(
                    "SELECT id FROM datasets WHERE id = ?",
                    (dataset_id,),
                ).fetchone()
                if row is not None:
                    return int(row["id"])
            row = conn.execute(
                "SELECT id FROM datasets ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                return self._ensure_default_dataset(conn)
            return int(row["id"])

    def list_datasets(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.name,
                    d.created_at,
                    COUNT(i.id) AS image_count
                FROM datasets d
                LEFT JOIN images i ON i.dataset_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC, d.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_dataset(self, name: str) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Dataset name is required.")
        with self.session() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO datasets (name, created_at)
                    VALUES (?, ?)
                    """,
                    (clean_name, utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Dataset "{clean_name}" already exists.') from exc
            row = conn.execute(
                """
                SELECT
                    d.id,
                    d.name,
                    d.created_at,
                    COUNT(i.id) AS image_count
                FROM datasets d
                LEFT JOIN images i ON i.dataset_id = d.id
                WHERE d.id = ?
                GROUP BY d.id
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)

    def update_dataset(self, dataset_id: int, name: str) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Dataset name is required.")
        with self.session() as conn:
            if (
                conn.execute("SELECT 1 FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
                is None
            ):
                raise ValueError("Dataset not found.")
            try:
                conn.execute(
                    "UPDATE datasets SET name = ? WHERE id = ?",
                    (clean_name, dataset_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Dataset "{clean_name}" already exists.') from exc
            row = conn.execute(
                """
                SELECT
                    d.id,
                    d.name,
                    d.created_at,
                    COUNT(i.id) AS image_count
                FROM datasets d
                LEFT JOIN images i ON i.dataset_id = d.id
                WHERE d.id = ?
                GROUP BY d.id
                """,
                (dataset_id,),
            ).fetchone()
        return dict(row)

    def list_users(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT id, username, created_at
                FROM users
                ORDER BY LOWER(username), username
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(self, username: str) -> dict[str, Any]:
        with self.session() as conn:
            return self._ensure_user(conn, username)

    def update_user(self, user_id: int, username: str) -> dict[str, Any]:
        clean_user = username.strip()
        if not clean_user:
            raise ValueError("Username is required.")
        with self.session() as conn:
            existing = conn.execute(
                """
                SELECT id, username
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("User not found.")
            old_username = existing["username"]
            try:
                conn.execute(
                    "UPDATE users SET username = ? WHERE id = ?",
                    (clean_user, user_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'User "{clean_user}" already exists.') from exc
            conn.execute(
                "UPDATE annotations SET username = ? WHERE username = ?",
                (clean_user, old_username),
            )
            row = conn.execute(
                """
                SELECT id, username, created_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row)

    def delete_user(self, user_id: int) -> dict[str, int]:
        with self.session() as conn:
            existing = conn.execute(
                """
                SELECT username
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("User not found.")
            annotation_cursor = conn.execute(
                "DELETE FROM annotations WHERE username = ?",
                (existing["username"],),
            )
            user_cursor = conn.execute(
                "DELETE FROM users WHERE id = ?",
                (user_id,),
            )
        return {
            "deleted_users": user_cursor.rowcount,
            "deleted_annotations": annotation_cursor.rowcount,
        }

    def list_categories(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT id, name, color, created_at FROM categories ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_category(self, name: str, color: str) -> dict[str, Any]:
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Category name is required.")
        with self.session() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO categories (name, color, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (clean_name, color, utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Category "{clean_name}" already exists.') from exc
            row = conn.execute(
                "SELECT id, name, color, created_at FROM categories WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)

    def update_category(self, category_id: int, name: str, color: str) -> dict[str, Any]:
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Category name is required.")
        with self.session() as conn:
            if (
                conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
                is None
            ):
                raise ValueError("Category not found.")
            try:
                conn.execute(
                    """
                    UPDATE categories
                    SET name = ?, color = ?
                    WHERE id = ?
                    """,
                    (clean_name, color, category_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Category "{clean_name}" already exists.') from exc
            row = conn.execute(
                "SELECT id, name, color, created_at FROM categories WHERE id = ?",
                (category_id,),
            ).fetchone()
        return dict(row)

    def delete_category(self, category_id: int) -> dict[str, int]:
        with self.session() as conn:
            category_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if category_count <= 1:
                raise ValueError("At least one label is required.")
            if (
                conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
                is None
            ):
                raise ValueError("Category not found.")
            annotation_cursor = conn.execute(
                "DELETE FROM annotations WHERE category_id = ?",
                (category_id,),
            )
            category_cursor = conn.execute(
                "DELETE FROM categories WHERE id = ?",
                (category_id,),
            )
            deleted_annotations = annotation_cursor.rowcount
            deleted_categories = category_cursor.rowcount
        return {
            "deleted_categories": deleted_categories,
            "deleted_annotations": deleted_annotations,
        }

    def list_images(
        self,
        username: str = "",
        dataset_id: int | None = None,
    ) -> list[dict[str, Any]]:
        resolved_dataset_id = self.resolve_dataset_id(dataset_id)
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT
                    i.id,
                    i.dataset_id,
                    i.name,
                    i.filename,
                    i.width,
                    i.height,
                    i.created_at,
                    COUNT(DISTINCT p.id) AS pixel_count,
                    COUNT(DISTINCT a.pixel_id) AS annotated_count
                FROM images i
                LEFT JOIN pixels p ON p.image_id = i.id
                LEFT JOIN annotations a
                    ON a.pixel_id = p.id
                    AND a.username = ?
                WHERE i.dataset_id = ?
                GROUP BY i.id
                ORDER BY i.created_at DESC, i.id DESC
                """,
                (username, resolved_dataset_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_image(
        self,
        name: str,
        filename: str,
        width: int,
        height: int,
        dataset_id: int | None = None,
    ) -> ImageRecord:
        resolved_dataset_id = self.resolve_dataset_id(dataset_id)
        with self.session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO images (
                    dataset_id,
                    name,
                    filename,
                    width,
                    height,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_dataset_id,
                    name.strip() or filename,
                    filename,
                    width,
                    height,
                    utc_now(),
                ),
            )
            row = conn.execute(
                """
                SELECT id, name, filename, width, height, created_at
                FROM images
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return ImageRecord(**dict(row))

    def get_image(self, image_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT id, dataset_id, name, filename, width, height, created_at
                FROM images
                WHERE id = ?
                """,
                (image_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Image not found.")
        return dict(row)

    def delete_image(self, image_id: int) -> dict[str, Any]:
        with self.session() as conn:
            image = conn.execute(
                """
                SELECT id, filename
                FROM images
                WHERE id = ?
                """,
                (image_id,),
            ).fetchone()
            if image is None:
                raise ValueError("Image not found.")

            annotation_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM annotations a
                JOIN pixels p ON p.id = a.pixel_id
                WHERE p.image_id = ?
                """,
                (image_id,),
            ).fetchone()[0]
            pixel_count = conn.execute(
                "SELECT COUNT(*) FROM pixels WHERE image_id = ?",
                (image_id,),
            ).fetchone()[0]
            image_cursor = conn.execute(
                "DELETE FROM images WHERE id = ?",
                (image_id,),
            )

        return {
            "deleted_images": image_cursor.rowcount,
            "deleted_pixels": pixel_count,
            "deleted_annotations": annotation_count,
            "filename": image["filename"],
        }

    def add_pixel(self, image_id: int, x: int, y: int) -> dict[str, Any]:
        image = self.get_image(image_id)
        if x < 0 or y < 0 or x >= image["width"] or y >= image["height"]:
            raise ValueError("Pixel coordinate is outside the image.")

        with self.session() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO pixels (image_id, x, y, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (image_id, x, y, utc_now()),
            )
            row = conn.execute(
                """
                SELECT id, image_id, x, y, created_at
                FROM pixels
                WHERE image_id = ? AND x = ? AND y = ?
                """,
                (image_id, x, y),
            ).fetchone()
        return dict(row)

    def add_random_pixels(
        self,
        image_id: int,
        count: int,
        seed: int | None = None,
    ) -> int:
        image = self.get_image(image_id)
        width = image["width"]
        height = image["height"]
        requested = max(0, int(count))
        if requested == 0:
            return 0

        with self.session() as conn:
            rows = conn.execute(
                "SELECT x, y FROM pixels WHERE image_id = ?",
                (image_id,),
            ).fetchall()
            existing = {(row["x"], row["y"]) for row in rows}
            available = max(0, width * height - len(existing))
            target = min(requested, available)
            rng = random.Random(seed) if seed is not None else random.SystemRandom()
            inserted = 0
            attempts = 0
            max_attempts = max(target * 40, 100)

            while inserted < target and attempts < max_attempts:
                attempts += 1
                x = rng.randrange(width)
                y = rng.randrange(height)
                if (x, y) in existing:
                    continue
                existing.add((x, y))
                conn.execute(
                    """
                    INSERT INTO pixels (image_id, x, y, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (image_id, x, y, utc_now()),
                )
                inserted += 1

            if inserted < target:
                for y in range(height):
                    if inserted >= target:
                        break
                    for x in range(width):
                        if inserted >= target:
                            break
                        if (x, y) in existing:
                            continue
                        existing.add((x, y))
                        conn.execute(
                            """
                            INSERT INTO pixels (image_id, x, y, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (image_id, x, y, utc_now()),
                        )
                        inserted += 1

        return inserted

    def move_pixel(self, pixel_id: int, x: int, y: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id,
                    p.image_id,
                    p.x,
                    p.y,
                    p.created_at,
                    i.width,
                    i.height
                FROM pixels p
                JOIN images i ON i.id = p.image_id
                WHERE p.id = ?
                """,
                (pixel_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Pixel not found.")
            if x < 0 or y < 0 or x >= row["width"] or y >= row["height"]:
                raise ValueError("Pixel coordinate is outside the image.")

            try:
                conn.execute(
                    """
                    UPDATE pixels
                    SET x = ?, y = ?
                    WHERE id = ?
                    """,
                    (x, y, pixel_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Another target pixel already exists at that coordinate.") from exc

            annotation_cursor = conn.execute(
                "DELETE FROM annotations WHERE pixel_id = ?",
                (pixel_id,),
            )
            deleted_annotations = annotation_cursor.rowcount
            moved = conn.execute(
                """
                SELECT id, image_id, x, y, created_at
                FROM pixels
                WHERE id = ?
                """,
                (pixel_id,),
            ).fetchone()

        result = dict(moved)
        result["deleted_annotations"] = deleted_annotations
        return result

    def reset_image_annotations(self, image_id: int) -> int:
        self.get_image(image_id)
        with self.session() as conn:
            cursor = conn.execute(
                """
                DELETE FROM annotations
                WHERE pixel_id IN (
                    SELECT id
                    FROM pixels
                    WHERE image_id = ?
                )
                """,
                (image_id,),
            )
            deleted = cursor.rowcount
        return deleted

    def reset_image_pixels(self, image_id: int) -> dict[str, int]:
        self.get_image(image_id)
        with self.session() as conn:
            annotation_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM annotations a
                JOIN pixels p ON p.id = a.pixel_id
                WHERE p.image_id = ?
                """,
                (image_id,),
            ).fetchone()[0]
            pixel_cursor = conn.execute(
                "DELETE FROM pixels WHERE image_id = ?",
                (image_id,),
            )
        return {
            "deleted_pixels": pixel_cursor.rowcount,
            "deleted_annotations": annotation_count,
        }

    def set_annotation(
        self,
        pixel_id: int,
        username: str,
        category_id: int,
    ) -> None:
        clean_user = username.strip()
        if not clean_user:
            raise ValueError("Username is required.")

        now = utc_now()
        with self.session() as conn:
            if conn.execute("SELECT 1 FROM pixels WHERE id = ?", (pixel_id,)).fetchone() is None:
                raise ValueError("Pixel not found.")
            if (
                conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
                is None
            ):
                raise ValueError("Category not found.")
            self._ensure_user(conn, clean_user)
            conn.execute(
                """
                INSERT INTO annotations (
                    pixel_id,
                    username,
                    category_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pixel_id, username) DO UPDATE SET
                    category_id = excluded.category_id,
                    updated_at = excluded.updated_at
                """,
                (pixel_id, clean_user, category_id, now, now),
            )

    def image_detail(self, image_id: int, username: str = "") -> dict[str, Any]:
        image = self.get_image(image_id)
        categories = self.list_categories()
        category_by_id = {category["id"]: category for category in categories}

        with self.session() as conn:
            pixel_rows = conn.execute(
                """
                SELECT id, image_id, x, y, created_at
                FROM pixels
                WHERE image_id = ?
                ORDER BY id
                """,
                (image_id,),
            ).fetchall()
            user_rows = conn.execute(
                """
                SELECT a.pixel_id, a.category_id
                FROM annotations a
                JOIN pixels p ON p.id = a.pixel_id
                WHERE p.image_id = ? AND a.username = ?
                """,
                (image_id, username),
            ).fetchall()
            vote_rows = conn.execute(
                """
                SELECT
                    a.pixel_id,
                    a.category_id,
                    COUNT(*) AS votes
                FROM annotations a
                JOIN pixels p ON p.id = a.pixel_id
                WHERE p.image_id = ?
                GROUP BY a.pixel_id, a.category_id
                """,
                (image_id,),
            ).fetchall()

        user_annotations = {row["pixel_id"]: row["category_id"] for row in user_rows}
        votes_by_pixel: dict[int, dict[int, int]] = {}
        for row in vote_rows:
            votes_by_pixel.setdefault(row["pixel_id"], {})[row["category_id"]] = row["votes"]

        pixels = []
        for row in pixel_rows:
            raw_votes = votes_by_pixel.get(row["id"], {})
            total_votes = sum(raw_votes.values())
            distribution = []
            for category in categories:
                votes = raw_votes.get(category["id"], 0)
                distribution.append(
                    {
                        "category_id": category["id"],
                        "name": category["name"],
                        "color": category["color"],
                        "votes": votes,
                        "probability": votes / total_votes if total_votes else 0,
                    }
                )
            consensus = None
            if total_votes:
                consensus_category_id = max(
                    raw_votes,
                    key=lambda category_id: (
                        raw_votes[category_id],
                        -category_by_id[category_id]["id"],
                    ),
                )
                consensus = category_by_id[consensus_category_id]

            pixels.append(
                {
                    "id": row["id"],
                    "image_id": row["image_id"],
                    "x": row["x"],
                    "y": row["y"],
                    "created_at": row["created_at"],
                    "user_category_id": user_annotations.get(row["id"]),
                    "total_votes": total_votes,
                    "distribution": distribution,
                    "consensus": consensus,
                }
            )

        done = sum(1 for pixel in pixels if pixel["user_category_id"] is not None)
        return {
            "image": image,
            "categories": categories,
            "pixels": pixels,
            "progress": {
                "done": done,
                "total": len(pixels),
            },
        }

    def export_distribution(self, image_id: int) -> dict[str, Any]:
        detail = self.image_detail(image_id)
        export_pixels = []
        for pixel in detail["pixels"]:
            votes = {
                item["name"]: item["votes"]
                for item in pixel["distribution"]
            }
            probabilities = {
                item["name"]: item["probability"]
                for item in pixel["distribution"]
            }
            export_pixels.append(
                {
                    "pixel_id": pixel["id"],
                    "x": pixel["x"],
                    "y": pixel["y"],
                    "total_votes": pixel["total_votes"],
                    "votes": votes,
                    "probabilities": probabilities,
                    "consensus": pixel["consensus"]["name"] if pixel["consensus"] else None,
                }
            )
        return {
            "image": detail["image"],
            "categories": detail["categories"],
            "pixels": export_pixels,
        }
