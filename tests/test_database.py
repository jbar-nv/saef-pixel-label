import sqlite3
import tempfile
import unittest
from pathlib import Path

from pixel_annotator.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "annotations.sqlite3")
        self.db.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_multiple_users_build_distribution_for_same_pixel(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 3, 4)
        categories = self.db.list_categories()
        background = categories[0]
        target = categories[1]

        self.db.set_annotation(pixel["id"], "ada", target["id"])
        self.db.set_annotation(pixel["id"], "grace", target["id"])
        self.db.set_annotation(pixel["id"], "linus", background["id"])

        detail = self.db.image_detail(image.id, "ada")
        annotated_pixel = detail["pixels"][0]
        votes = {item["name"]: item["votes"] for item in annotated_pixel["distribution"]}
        probabilities = {
            item["name"]: round(item["probability"], 4)
            for item in annotated_pixel["distribution"]
        }

        self.assertEqual(annotated_pixel["total_votes"], 3)
        self.assertEqual(votes["target"], 2)
        self.assertEqual(votes["background"], 1)
        self.assertEqual(probabilities["target"], 0.6667)
        self.assertEqual(annotated_pixel["user_category_id"], target["id"])

    def test_user_can_change_their_annotation_without_adding_vote(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 1, 2)
        categories = self.db.list_categories()

        self.db.set_annotation(pixel["id"], "ada", categories[0]["id"])
        self.db.set_annotation(pixel["id"], "ada", categories[1]["id"])

        export = self.db.export_distribution(image.id)
        exported_pixel = export["pixels"][0]
        self.assertEqual(exported_pixel["total_votes"], 1)
        self.assertEqual(exported_pixel["votes"][categories[1]["name"]], 1)
        self.assertEqual(exported_pixel["votes"][categories[0]["name"]], 0)

    def test_category_can_be_renamed(self):
        category = self.db.create_category("leaf", "#118833")
        updated = self.db.update_category(category["id"], "healthy_leaf", "#22aa44")

        self.assertEqual(updated["name"], "healthy_leaf")
        self.assertEqual(updated["color"], "#22aa44")
        self.assertIn(updated, self.db.list_categories())

    def test_deleting_category_removes_its_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 3, 4)
        category = self.db.create_category("remove_me", "#112233")
        self.db.set_annotation(pixel["id"], "ada", category["id"])

        result = self.db.delete_category(category["id"])
        detail = self.db.image_detail(image.id, "ada")

        self.assertEqual(result["deleted_categories"], 1)
        self.assertEqual(result["deleted_annotations"], 1)
        self.assertEqual(detail["pixels"][0]["total_votes"], 0)
        self.assertIsNone(detail["pixels"][0]["user_category_id"])

    def test_moving_pixel_clears_its_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 3, 4)
        category = self.db.list_categories()[1]
        self.db.set_annotation(pixel["id"], "ada", category["id"])
        self.db.set_annotation(pixel["id"], "grace", category["id"])

        moved = self.db.move_pixel(pixel["id"], 6, 1)
        detail = self.db.image_detail(image.id, "ada")

        self.assertEqual(moved["x"], 6)
        self.assertEqual(moved["y"], 1)
        self.assertEqual(moved["deleted_annotations"], 2)
        self.assertEqual(detail["pixels"][0]["x"], 6)
        self.assertEqual(detail["pixels"][0]["y"], 1)
        self.assertEqual(detail["pixels"][0]["total_votes"], 0)
        self.assertIsNone(detail["pixels"][0]["user_category_id"])

    def test_reset_image_annotations_clears_every_pixel_on_image(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        other_image = self.db.create_image("other", "other.png", 8, 8)
        first = self.db.add_pixel(image.id, 1, 1)
        second = self.db.add_pixel(image.id, 2, 2)
        other = self.db.add_pixel(other_image.id, 3, 3)
        categories = self.db.list_categories()
        self.db.set_annotation(first["id"], "ada", categories[0]["id"])
        self.db.set_annotation(second["id"], "grace", categories[1]["id"])
        self.db.set_annotation(other["id"], "linus", categories[1]["id"])

        deleted = self.db.reset_image_annotations(image.id)
        detail = self.db.image_detail(image.id, "ada")
        other_detail = self.db.image_detail(other_image.id, "linus")

        self.assertEqual(deleted, 2)
        self.assertTrue(all(pixel["total_votes"] == 0 for pixel in detail["pixels"]))
        self.assertTrue(
            all(pixel["user_category_id"] is None for pixel in detail["pixels"])
        )
        self.assertEqual(other_detail["pixels"][0]["total_votes"], 1)

    def test_reset_image_pixels_removes_pixels_and_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        other_image = self.db.create_image("other", "other.png", 8, 8)
        first = self.db.add_pixel(image.id, 1, 1)
        second = self.db.add_pixel(image.id, 2, 2)
        other = self.db.add_pixel(other_image.id, 3, 3)
        categories = self.db.list_categories()
        self.db.set_annotation(first["id"], "ada", categories[0]["id"])
        self.db.set_annotation(second["id"], "grace", categories[1]["id"])
        self.db.set_annotation(other["id"], "linus", categories[1]["id"])

        result = self.db.reset_image_pixels(image.id)
        detail = self.db.image_detail(image.id, "ada")
        other_detail = self.db.image_detail(other_image.id, "linus")

        self.assertEqual(result["deleted_pixels"], 2)
        self.assertEqual(result["deleted_annotations"], 2)
        self.assertEqual(detail["pixels"], [])
        self.assertEqual(other_detail["pixels"][0]["total_votes"], 1)

    def test_delete_image_removes_pixels_and_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        other_image = self.db.create_image("other", "other.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 1, 1)
        other_pixel = self.db.add_pixel(other_image.id, 2, 2)
        category = self.db.list_categories()[0]
        self.db.set_annotation(pixel["id"], "ada", category["id"])
        self.db.set_annotation(other_pixel["id"], "grace", category["id"])

        result = self.db.delete_image(image.id)
        other_detail = self.db.image_detail(other_image.id, "grace")

        self.assertEqual(result["deleted_images"], 1)
        self.assertEqual(result["deleted_pixels"], 1)
        self.assertEqual(result["deleted_annotations"], 1)
        self.assertEqual(result["filename"], "sample.png")
        self.assertEqual(other_detail["pixels"][0]["total_votes"], 1)
        with self.assertRaises(ValueError):
            self.db.get_image(image.id)

    def test_images_are_filtered_by_dataset(self):
        default_dataset_id = self.db.resolve_dataset_id()
        second_dataset = self.db.create_dataset("second")
        default_image = self.db.create_image("default", "default.png", 8, 8)
        second_image = self.db.create_image(
            "second",
            "second.png",
            8,
            8,
            second_dataset["id"],
        )

        default_images = self.db.list_images(dataset_id=default_dataset_id)
        second_images = self.db.list_images(dataset_id=second_dataset["id"])

        self.assertEqual([image["id"] for image in default_images], [default_image.id])
        self.assertEqual([image["id"] for image in second_images], [second_image.id])

    def test_dataset_can_be_renamed(self):
        dataset = self.db.create_dataset("raw")
        updated = self.db.update_dataset(dataset["id"], "curated")

        self.assertEqual(updated["name"], "curated")
        self.assertEqual(updated["id"], dataset["id"])
        self.assertIn(updated, self.db.list_datasets())

    def test_user_can_be_created_and_listed(self):
        created = self.db.create_user("ada")
        repeated = self.db.create_user("ada")
        users = self.db.list_users()

        self.assertEqual(created["username"], "ada")
        self.assertEqual(repeated["id"], created["id"])
        self.assertEqual([user["username"] for user in users], ["ada"])

    def test_annotation_registers_user(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 1, 2)
        category = self.db.list_categories()[0]

        self.db.set_annotation(pixel["id"], "grace", category["id"])
        users = self.db.list_users()

        self.assertEqual([user["username"] for user in users], ["grace"])

    def test_user_can_be_renamed_with_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 1, 2)
        category = self.db.list_categories()[0]
        user = self.db.create_user("ada")
        self.db.set_annotation(pixel["id"], "ada", category["id"])

        updated = self.db.update_user(user["id"], "grace")
        detail = self.db.image_detail(image.id, "grace")

        self.assertEqual(updated["username"], "grace")
        self.assertEqual([item["username"] for item in self.db.list_users()], ["grace"])
        self.assertEqual(detail["pixels"][0]["user_category_id"], category["id"])

    def test_deleting_user_removes_their_annotations(self):
        image = self.db.create_image("sample", "sample.png", 8, 8)
        pixel = self.db.add_pixel(image.id, 1, 2)
        category = self.db.list_categories()[0]
        user = self.db.create_user("ada")
        self.db.set_annotation(pixel["id"], "ada", category["id"])

        result = self.db.delete_user(user["id"])
        detail = self.db.image_detail(image.id, "ada")

        self.assertEqual(result["deleted_users"], 1)
        self.assertEqual(result["deleted_annotations"], 1)
        self.assertEqual(self.db.list_users(), [])
        self.assertEqual(detail["pixels"][0]["total_votes"], 0)

    def test_existing_database_images_migrate_to_default_dataset(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "old.sqlite3"
            conn = sqlite3.connect(path)
            try:
                conn.execute(
                    """
                    CREATE TABLE images (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        filename TEXT NOT NULL UNIQUE,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO images (
                        name,
                        filename,
                        width,
                        height,
                        created_at
                    )
                    VALUES ('old', 'old.png', 8, 8, '2026-05-22T00:00:00+00:00')
                    """
                )
                conn.commit()
            finally:
                conn.close()

            db = Database(path)
            db.initialize()
            default_dataset_id = db.resolve_dataset_id()
            images = db.list_images(dataset_id=default_dataset_id)

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["name"], "old")
        self.assertEqual(images[0]["dataset_id"], default_dataset_id)

    def test_existing_annotation_usernames_migrate_to_users(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "old-users.sqlite3"
            conn = sqlite3.connect(path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE datasets (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE images (
                        id INTEGER PRIMARY KEY,
                        dataset_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        filename TEXT NOT NULL UNIQUE,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE categories (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        color TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE pixels (
                        id INTEGER PRIMARY KEY,
                        image_id INTEGER NOT NULL,
                        x INTEGER NOT NULL,
                        y INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE annotations (
                        id INTEGER PRIMARY KEY,
                        pixel_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        category_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    INSERT INTO datasets VALUES (1, 'Default dataset', '2026-05-22T00:00:00+00:00');
                    INSERT INTO images VALUES (1, 1, 'sample', 'sample.png', 8, 8, '2026-05-22T00:00:00+00:00');
                    INSERT INTO categories VALUES (1, 'target', '#0f8f7a', '2026-05-22T00:00:00+00:00');
                    INSERT INTO pixels VALUES (1, 1, 2, 3, '2026-05-22T00:00:00+00:00');
                    INSERT INTO annotations VALUES (1, 1, 'ada', 1, '2026-05-22T00:00:00+00:00', '2026-05-22T00:00:00+00:00');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            db = Database(path)
            db.initialize()
            users = db.list_users()

        self.assertEqual([user["username"] for user in users], ["ada"])

    def test_random_sampling_stays_inside_image(self):
        image = self.db.create_image("sample", "sample.png", 4, 4)
        inserted = self.db.add_random_pixels(image.id, 100, seed=10)
        detail = self.db.image_detail(image.id)

        self.assertEqual(inserted, 16)
        self.assertEqual(len(detail["pixels"]), 16)
        self.assertTrue(all(0 <= pixel["x"] < 4 for pixel in detail["pixels"]))
        self.assertTrue(all(0 <= pixel["y"] < 4 for pixel in detail["pixels"]))


if __name__ == "__main__":
    unittest.main()
