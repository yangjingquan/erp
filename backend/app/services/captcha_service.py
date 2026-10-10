import base64
import hashlib
import io
import random
import secrets
from datetime import timedelta

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.auth import AuthCaptchaChallenge


BOARD_WIDTH = 320
BOARD_HEIGHT = 144
PIECE_SIZE = 72
CHALLENGE_TTL = timedelta(minutes=2)
SLIDER_TOLERANCE = 6


def _data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _make_artwork(target_x: int, puzzle_top: int) -> tuple[str, str]:
    rng = random.Random(secrets.randbits(64))
    scale = 2
    width, height = BOARD_WIDTH * scale, BOARD_HEIGHT * scale

    color_top = (239, 247, 250)
    color_bottom = (207, 225, 235)
    artwork = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(artwork)
    for line_y in range(BOARD_HEIGHT):
        ratio = line_y / max(1, BOARD_HEIGHT - 1)
        color = tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(color_top, color_bottom))
        draw.line((0, line_y * scale, width, line_y * scale), fill=(*color, 255), width=scale)

    # Keep the background calm so the silhouette of the target is easy to spot.
    details = Image.new("RGBA", (width, height))
    detail_draw = ImageDraw.Draw(details)
    for index in range(5):
        cx = rng.randint(16, BOARD_WIDTH - 16)
        cy = rng.randint(12, BOARD_HEIGHT - 12)
        radius = rng.randint(12, 28)
        color = (94, 143, 165) if index % 2 == 0 else (255, 255, 255)
        detail_draw.ellipse(
            ((cx - radius) * scale, (cy - radius) * scale, (cx + radius) * scale, (cy + radius) * scale),
            fill=(*color, 22),
        )
    artwork.alpha_composite(details)

    # Leave a small clear margin around the silhouette for a crisp outline.
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    x, y = target_x * scale, puzzle_top * scale
    mask_draw.rounded_rectangle(
        (x + 12 * scale, y + 12 * scale, x + 60 * scale, y + 60 * scale),
        radius=6 * scale,
        fill=255,
    )
    # Each value describes an edge: 1 adds a tab, -1 cuts a notch, and 0
    # leaves it flat. The same mask builds both the cutout and movable piece.
    edge_patterns = (
        (1, 0, -1, 0),
        (1, -1, 1, -1),
        (-1, 1, 0, 1),
        (0, 1, -1, -1),
        (1, 1, 0, -1),
        (0, -1, 1, 1),
        (1, 0, 0, -1),
    )
    edge_pattern = rng.choice(edge_patterns)
    edge_specs = (
        (edge_pattern[0], 36 + rng.randint(-5, 5), 12),
        (edge_pattern[1], 60, 36 + rng.randint(-5, 5)),
        (edge_pattern[2], 36 + rng.randint(-5, 5), 60),
        (edge_pattern[3], 12, 36 + rng.randint(-5, 5)),
    )
    for edge_type, center_x, center_y in edge_specs:
        if edge_type == 0:
            continue
        radius = 9
        mask_draw.ellipse(
            (
                x + (center_x - radius) * scale,
                y + (center_y - radius) * scale,
                x + (center_x + radius) * scale,
                y + (center_y + radius) * scale,
            ),
            fill=255 if edge_type > 0 else 0,
        )

    background = artwork.copy()
    hole = Image.new("RGBA", (width, height), (27, 37, 52, 255))
    hole.putalpha(mask)
    background.alpha_composite(hole)

    # A white outer halo and cyan inner edge make the dark cutout stand out
    # from both the pale background and the yellow piece.
    outside_border = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(13)), mask)
    halo = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    halo.putalpha(outside_border)
    background.alpha_composite(halo)
    bright_edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(7)), mask)
    edge = Image.new("RGBA", (width, height), (0, 174, 214, 255))
    edge.putalpha(bright_edge)
    background.alpha_composite(edge)
    # Re-apply the opaque center above the colored outline's inner edge.
    hole.putalpha(mask)
    background.alpha_composite(hole)

    crop_box = (x, y, x + PIECE_SIZE * scale, y + PIECE_SIZE * scale)
    piece_mask = mask.crop(crop_box)
    piece = Image.new("RGBA", (PIECE_SIZE * scale, PIECE_SIZE * scale), (255, 207, 45, 255))
    piece.putalpha(piece_mask)
    outer_edge = piece_mask.filter(ImageFilter.MaxFilter(9))
    piece_border = Image.new("RGBA", piece.size, (22, 34, 48, 255))
    piece_border.putalpha(outer_edge)
    piece_border.alpha_composite(piece)

    inner_edge = ImageChops.subtract(piece_mask, piece_mask.filter(ImageFilter.MinFilter(5)))
    light_edge = Image.new("RGBA", piece.size, (255, 255, 242, 255))
    light_edge.putalpha(inner_edge)
    piece_border.alpha_composite(light_edge)

    grip = Image.new("RGBA", piece.size)
    grip_draw = ImageDraw.Draw(grip)
    for grip_x in (30, 36, 42):
        grip_draw.rounded_rectangle(
            ((grip_x - 1) * scale, 29 * scale, (grip_x + 1) * scale, 43 * scale),
            radius=1 * scale,
            fill=(89, 76, 20, 210),
        )
    grip.putalpha(ImageChops.multiply(grip.getchannel("A"), piece_mask))
    piece_border.alpha_composite(grip)

    resampling = Image.Resampling.LANCZOS
    background = background.resize((BOARD_WIDTH, BOARD_HEIGHT), resampling)
    piece = piece_border.resize((PIECE_SIZE, PIECE_SIZE), resampling)
    return _data_uri(background), _data_uri(piece)


def create_captcha_challenge(db: Session) -> dict:
    now = local_now()
    db.execute(delete(AuthCaptchaChallenge).where(AuthCaptchaChallenge.expires_at <= now))
    target_x = random.SystemRandom().randint(132, BOARD_WIDTH - PIECE_SIZE - 8)
    puzzle_top = random.SystemRandom().randint(35, BOARD_HEIGHT - PIECE_SIZE - 12)
    background_image, piece_image = _make_artwork(target_x, puzzle_top)
    challenge = AuthCaptchaChallenge(
        target_x=target_x,
        expires_at=now + CHALLENGE_TTL,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return {
        "challenge_id": challenge.id,
        "background_image": background_image,
        "piece_image": piece_image,
        "piece_top": puzzle_top,
        "board_width": BOARD_WIDTH,
        "board_height": BOARD_HEIGHT,
        "piece_size": PIECE_SIZE,
    }


def verify_captcha_challenge(db: Session, challenge_id: str, offset_x: float) -> str:
    challenge = db.get(AuthCaptchaChallenge, challenge_id)
    now = local_now()
    if challenge is None or challenge.expires_at <= now or challenge.verified_at is not None:
        raise AppError("滑块验证已过期，请刷新后重试", code=400)
    if abs(offset_x - challenge.target_x) > SLIDER_TOLERANCE:
        db.delete(challenge)
        db.commit()
        raise AppError("滑块位置不正确，请重新验证", code=400)

    captcha_token = secrets.token_urlsafe(32)
    challenge.verified_token_hash = hashlib.sha256(captcha_token.encode("utf-8")).hexdigest()
    challenge.verified_at = now
    db.commit()
    return captcha_token


def consume_captcha_token(db: Session, captcha_token: str) -> bool:
    now = local_now()
    token_hash = hashlib.sha256(captcha_token.encode("utf-8")).hexdigest()
    result = db.execute(
        update(AuthCaptchaChallenge)
        .where(
            AuthCaptchaChallenge.verified_token_hash == token_hash,
            AuthCaptchaChallenge.verified_at.is_not(None),
            AuthCaptchaChallenge.consumed_at.is_(None),
            AuthCaptchaChallenge.expires_at > now,
        )
        .values(consumed_at=now)
    )
    db.commit()
    return result.rowcount == 1
