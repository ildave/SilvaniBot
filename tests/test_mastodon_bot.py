import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image, ImageFont

import mastodon_bot


class TestMastodonBot(unittest.TestCase):
    def test_build_toot_text(self) -> None:
        self.assertEqual(mastodon_bot.build_toot_text("ingegnere"), "Ah, anche ingegnere!")

    def test_build_output_path_sanitizes_invalid_chars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = mastodon_bot.build_output_path("dev/ops:*?", Path(tmpdir))
            self.assertEqual(output.name, "devops.jpg")

    def test_build_output_path_rejects_empty_after_sanitize(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                mastodon_bot.build_output_path("<>:\"/\\|?*", Path(tmpdir))

    def test_choose_random_profession_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            mastodon_bot.choose_random_profession(Path("non_esiste.txt"))

    def test_choose_random_profession_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            professions = Path(tmpdir) / "professioni.txt"
            professions.write_text("\n   \n", encoding="utf-8")

            with self.assertRaises(ValueError):
                mastodon_bot.choose_random_profession(professions)

    def test_choose_random_unused_profession_writes_in_usati(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            professions = Path(tmpdir) / "professioni.txt"
            used = Path(tmpdir) / "usati.txt"

            professions.write_text("idraulico\nfalegname\n", encoding="utf-8")
            used.write_text("idraulico", encoding="utf-8")

            with patch("mastodon_bot.random.choice", return_value="falegname"):
                chosen = mastodon_bot.choose_random_unused_profession(professions, used)

            self.assertEqual(chosen, "falegname")
            self.assertEqual(used.read_text(encoding="utf-8"), "idraulico\nfalegname")

    def test_choose_random_unused_profession_raises_when_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            professions = Path(tmpdir) / "professioni.txt"
            used = Path(tmpdir) / "usati.txt"

            professions.write_text("idraulico\nfalegname\n", encoding="utf-8")
            used.write_text("idraulico\nfalegname\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                mastodon_bot.choose_random_unused_profession(professions, used)

    def test_render_image_with_text_creates_output_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            base_image = tmp / "base.jpg"
            output_image = tmp / "out.jpg"

            Image.new("RGB", (800, 400), color="black").save(base_image, format="JPEG")

            with patch("mastodon_bot._load_helvetica_font", side_effect=lambda size: ImageFont.load_default()):
                mastodon_bot.render_image_with_text(base_image, "Ah, anche tester!", output_image)

            self.assertTrue(output_image.exists())
            self.assertGreater(output_image.stat().st_size, 0)

            with Image.open(output_image) as out:
                self.assertEqual(out.size, (800, 400))

    def test_render_image_with_text_missing_base_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out.jpg"
            with self.assertRaises(FileNotFoundError):
                mastodon_bot.render_image_with_text(Path(tmpdir) / "missing.jpg", "ciao", out)

    def test_post_toot_with_media_posts_media_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "image.jpg"
            image_path.write_bytes(b"fake")

            mock_client = MagicMock()
            mock_client.media_post.return_value = {"id": "12345"}

            with patch("mastodon_bot.Mastodon", return_value=mock_client) as mock_mastodon:
                mastodon_bot.post_toot_with_media(
                    status_text="Ah, anche tester!",
                    image_path=image_path,
                    api_base_url="https://mastodon.example",
                    access_token="token",
                )

            mock_mastodon.assert_called_once_with(
                access_token="token",
                api_base_url="https://mastodon.example",
            )
            mock_client.media_post.assert_called_once_with(str(image_path))
            mock_client.status_post.assert_called_once_with(
                status="Ah, anche tester!",
                media_ids=["12345"],
            )

    def test_post_toot_with_media_raises_if_image_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "image.jpg"

            with self.assertRaises(FileNotFoundError):
                mastodon_bot.post_toot_with_media(
                    status_text="Ah, anche tester!",
                    image_path=image_path,
                    api_base_url="https://mastodon.example",
                    access_token="token",
                )

    def test_post_toot_with_media_raises_if_media_response_has_no_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "image.jpg"
            image_path.write_bytes(b"fake")

            mock_client = MagicMock()
            mock_client.media_post.return_value = {}

            with patch("mastodon_bot.Mastodon", return_value=mock_client):
                with self.assertRaises(ValueError):
                    mastodon_bot.post_toot_with_media(
                        status_text="Ah, anche tester!",
                        image_path=image_path,
                        api_base_url="https://mastodon.example",
                        access_token="token",
                    )


if __name__ == "__main__":
    unittest.main()
