import tempfile
import unittest
from pathlib import Path
from io import StringIO
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

    def test_choose_random_unused_profession_does_not_write_in_usati(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            professions = Path(tmpdir) / "professioni.txt"
            used = Path(tmpdir) / "usati.txt"

            professions.write_text("idraulico\nfalegname\n", encoding="utf-8")
            used.write_text("idraulico", encoding="utf-8")

            with patch("mastodon_bot.random.choice", return_value="falegname"):
                chosen = mastodon_bot.choose_random_unused_profession(professions, used)

            self.assertEqual(chosen, "falegname")
            self.assertEqual(used.read_text(encoding="utf-8"), "idraulico")

    def test_mark_profession_as_used_appends_with_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            used = Path(tmpdir) / "usati.txt"
            used.write_text("idraulico", encoding="utf-8")

            mastodon_bot.mark_profession_as_used(used, "falegname")

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

    def test_run_marks_word_as_used_only_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            professions = tmp / "professioni.txt"
            used = tmp / "usati.txt"
            base_image = tmp / "base.jpg"
            output_dir = tmp / "output"

            professions.write_text("idraulico\nfalegname\n", encoding="utf-8")
            used.write_text("idraulico", encoding="utf-8")
            base_image.write_bytes(b"fake")

            config = mastodon_bot.BotConfig(
                professions_file=professions,
                used_words_file=used,
                base_image=base_image,
                output_dir=output_dir,
                env_file=tmp / ".env",
            )

            with patch("mastodon_bot.load_dotenv"), patch(
                "mastodon_bot.get_required_env_var", side_effect=["https://mastodon.example", "token"]
            ), patch("mastodon_bot.render_image_with_text"), patch("mastodon_bot.post_toot_with_media"), patch(
                "mastodon_bot.random.choice", return_value="falegname"
            ):
                mastodon_bot.run(config)

            self.assertEqual(used.read_text(encoding="utf-8"), "idraulico\nfalegname")

    def test_run_does_not_mark_word_as_used_if_post_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            professions = tmp / "professioni.txt"
            used = tmp / "usati.txt"
            base_image = tmp / "base.jpg"
            output_dir = tmp / "output"

            professions.write_text("idraulico\nfalegname\n", encoding="utf-8")
            used.write_text("idraulico", encoding="utf-8")
            base_image.write_bytes(b"fake")

            config = mastodon_bot.BotConfig(
                professions_file=professions,
                used_words_file=used,
                base_image=base_image,
                output_dir=output_dir,
                env_file=tmp / ".env",
            )

            with patch("mastodon_bot.load_dotenv"), patch(
                "mastodon_bot.get_required_env_var", side_effect=["https://mastodon.example", "token"]
            ), patch("mastodon_bot.render_image_with_text"), patch(
                "mastodon_bot.post_toot_with_media", side_effect=RuntimeError("publish failed")
            ), patch("mastodon_bot.random.choice", return_value="falegname"):
                with self.assertRaises(RuntimeError):
                    mastodon_bot.run(config)

            self.assertEqual(used.read_text(encoding="utf-8"), "idraulico")

    def test_main_returns_zero_on_success(self) -> None:
        with patch("mastodon_bot.run"):
            exit_code = mastodon_bot.main()

        self.assertEqual(exit_code, 0)

    def test_main_handles_expected_error(self) -> None:
        stderr = StringIO()
        with patch("mastodon_bot.run", side_effect=ValueError("bad config")), patch("sys.stderr", stderr):
            exit_code = mastodon_bot.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("Errore: bad config", stderr.getvalue())

    def test_main_handles_unexpected_error_with_traceback(self) -> None:
        stderr = StringIO()
        with patch("mastodon_bot.run", side_effect=RuntimeError("boom")), patch("sys.stderr", stderr):
            exit_code = mastodon_bot.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("Errore inatteso: boom", stderr.getvalue())
        self.assertIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
