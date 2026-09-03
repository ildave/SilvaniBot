from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path

from mastodon import Mastodon
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class BotConfig:
    professions_file: Path = Path("professioni.txt")
    used_words_file: Path = Path("usati.txt")
    base_image: Path = Path("silvani.jpg")
    output_dir: Path = Path("output")
    mastodon_api_base_url_env: str = "MASTODON_API_BASE_URL"
    mastodon_access_token_env: str = "MASTODON_ACCESS_TOKEN"


def choose_random_profession(professions_file: Path) -> str:
    if not professions_file.exists():
        raise FileNotFoundError(f"File non trovato: {professions_file}")

    words = [line.strip() for line in professions_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not words:
        raise ValueError("Il file professioni.txt è vuoto")

    return random.choice(words)


def choose_random_unused_profession(professions_file: Path, used_words_file: Path) -> str:
    if not professions_file.exists():
        raise FileNotFoundError(f"File non trovato: {professions_file}")

    all_words = [line.strip() for line in professions_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all_words:
        raise ValueError("Il file professioni.txt è vuoto")

    if used_words_file.exists():
        used_words = {line.strip() for line in used_words_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    else:
        used_words = set()

    available_words = [word for word in all_words if word not in used_words]
    if not available_words:
        raise ValueError("Non ci sono più professioni disponibili: tutte le parole sono già in usati.txt")

    # Pick only from unused words so already-used entries are implicitly discarded.
    chosen_word = random.choice(available_words)

    with used_words_file.open("a", encoding="utf-8") as f:
        if used_words_file.stat().st_size > 0:
            f.write("\n")
        f.write(chosen_word)

    return chosen_word


def build_toot_text(word: str) -> str:
    return f"Ah, anche {word}!"


def get_required_env_var(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value:
        raise ValueError(f"Variabile d'ambiente mancante o vuota: {env_name}")
    return value


def build_output_path(word: str, output_dir: Path) -> Path:
    # Minimal filename normalization for Windows compatibility.
    sanitized = "".join(ch for ch in word if ch not in '<>:"/\\|?*').strip()
    if not sanitized:
        raise ValueError("La parola scelta non puo essere usata come nome file")
    return output_dir / f"{sanitized}.jpg"


def _load_helvetica_font(font_size: int) -> ImageFont.FreeTypeFont:
    candidate_paths = [
        "Helvetica.ttf",
        "helvetica.ttf",
        "C:/Windows/Fonts/helvetica.ttf",
        "C:/Windows/Fonts/Helvetica.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for font_path in candidate_paths:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue

    raise FileNotFoundError(
        "Impossibile caricare Helvetica. Installa Helvetica.ttf o metti il file font nella cartella del progetto."
    )


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def render_image_with_text(base_image: Path, text: str, output_image: Path) -> None:
    if not base_image.exists():
        raise FileNotFoundError(f"Immagine base non trovata: {base_image}")

    with Image.open(base_image).convert("RGB") as img:
        draw = ImageDraw.Draw(img)
        img_width, img_height = img.size

        target_width = int(img_width * 0.8)
        min_size = 10
        max_size = max(10, img_height)
        best_font = _load_helvetica_font(min_size)

        # Binary search for the largest size that keeps text close to 80% width.
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            font = _load_helvetica_font(mid)
            width = _text_width(draw, text, font)

            if width <= target_width:
                best_font = font
                min_size = mid + 1
            else:
                max_size = mid - 1

        left, top, right, bottom = draw.textbbox((0, 0), text, font=best_font)
        text_width = right - left
        text_height = bottom - top

        x = (img_width - text_width) // 2
        bottom_margin = max(10, int(img_height * 0.05))
        y = img_height - text_height - bottom_margin

        draw.text((x, y), text, font=best_font, fill="white")

        output_image.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_image, format="JPEG", quality=95)


def post_toot_with_media(status_text: str, image_path: Path, api_base_url: str, access_token: str) -> None:
    if not status_text.strip():
        raise ValueError("Il testo del toot non puo essere vuoto")
    if not api_base_url.strip():
        raise ValueError("api_base_url non puo essere vuoto")
    if not access_token.strip():
        raise ValueError("access_token non puo essere vuoto")
    if not image_path.exists():
        raise FileNotFoundError(f"Immagine da pubblicare non trovata: {image_path}")

    client = Mastodon(access_token=access_token, api_base_url=api_base_url)
    media = client.media_post(str(image_path))
    media_id = media.get("id")
    if media_id is None:
        raise ValueError("Upload media fallito: risposta senza media id")

    client.status_post(status=status_text, media_ids=[media_id])


def run(config: BotConfig) -> None:
    word = choose_random_unused_profession(config.professions_file, config.used_words_file)
    toot_text = build_toot_text(word)
    output_image = build_output_path(word, config.output_dir)

    print(f"Professione scelta: {word}")
    print(f"Toot: {toot_text}")
    print(f"Output previsto: {output_image}")

    api_base_url = get_required_env_var(config.mastodon_api_base_url_env)
    access_token = get_required_env_var(config.mastodon_access_token_env)

    render_image_with_text(config.base_image, toot_text, output_image)
    post_toot_with_media(toot_text, output_image, api_base_url, access_token)


def main() -> None:
    config = BotConfig()
    run(config)


if __name__ == "__main__":
    main()
