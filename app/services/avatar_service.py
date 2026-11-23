"""Avatar pipeline: normalise uploads and (optionally) generate illustrations.

Uploaded avatars are always re-encoded by Pillow: this strips EXIF/metadata,
guarantees a square, bounds the file size and neutralises malformed images that
would otherwise be served straight from the app origin.
"""

from __future__ import annotations

import base64
import io
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.services.skill_runtime import UPLOADS_ROOT, attachment_public_url

logger = logging.getLogger(__name__)

AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_SIZE = 512
AVATAR_THUMB_SIZE = 96
AVATAR_ROOT = UPLOADS_ROOT / "avatars"


class AvatarImageError(ValueError):
    """The uploaded bytes are not a usable image."""


class AvatarGenerationUnavailable(RuntimeError):
    """No illustration provider configured, or the provider failed."""


def normalise_avatar_bytes(raw: bytes, size: int = AVATAR_SIZE) -> bytes:
    """Validate, square-crop and re-encode image bytes as WebP."""
    if not raw:
        raise AvatarImageError("文件为空")
    if len(raw) > AVATAR_MAX_BYTES:
        raise AvatarImageError("头像文件过大")

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise AvatarImageError("不是有效的图片文件") from exc

    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    if getattr(image, "is_animated", False):
        image.seek(0)

    if image.mode in {"RGBA", "LA", "P"}:
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image)
    image = image.convert("RGB")

    width, height = image.size
    if width <= 0 or height <= 0:
        raise AvatarImageError("图片尺寸无效")

    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((size, size), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=86, method=6)
    return buffer.getvalue()


def _avatar_dir(scope: str, owner_key: str | int) -> Path:
    safe_scope = "".join(ch for ch in str(scope) if ch.isalnum() or ch in "-_") or "misc"
    safe_owner = "".join(ch for ch in str(owner_key) if ch.isalnum() or ch in "-_") or "anon"
    directory = AVATAR_ROOT / safe_scope / safe_owner
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_avatar_bytes(raw: bytes, scope: str, owner_key: str | int) -> dict[str, str]:
    """Normalise and store a 512px avatar plus a 96px thumbnail."""
    if len(raw) > AVATAR_MAX_BYTES:
        raise AvatarImageError("头像文件不能超过 2MB")

    directory = _avatar_dir(scope, owner_key)
    token = uuid.uuid4().hex
    full_name = f"{token}.webp"
    thumb_name = f"{token}_96.webp"

    normalized = normalise_avatar_bytes(raw, AVATAR_SIZE)
    (directory / full_name).write_bytes(normalized)

    thumb_source = Image.open(io.BytesIO(normalized))
    thumb_source = thumb_source.resize((AVATAR_THUMB_SIZE, AVATAR_THUMB_SIZE), Image.LANCZOS)
    thumb_buffer = io.BytesIO()
    thumb_source.save(thumb_buffer, format="WEBP", quality=82, method=6)
    (directory / thumb_name).write_bytes(thumb_buffer.getvalue())

    full_url = attachment_public_url((directory / full_name).relative_to(UPLOADS_ROOT.parent))
    thumb_url = attachment_public_url((directory / thumb_name).relative_to(UPLOADS_ROOT.parent))
    return {"storage_url": full_url, "preview_url": full_url, "thumb_url": thumb_url}


def _avatar_path(url: str) -> Optional[Path]:
    value = str(url or "").strip()
    if "/uploads/avatars/" not in value:
        return None
    relative = value.split("/uploads/", 1)[-1]
    try:
        candidate = (UPLOADS_ROOT / relative).resolve()
        if candidate.is_relative_to(AVATAR_ROOT.resolve()) and candidate.exists():
            return candidate
    except OSError:
        return None
    return None


def delete_avatar_files(url: Optional[str]) -> None:
    """Best-effort cleanup; only ever touches files under uploads/avatars."""
    path = _avatar_path(url or "")
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
        stem = path.stem
        thumb = path.with_name(f"{stem}_96.webp")
        thumb.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove old avatar %s: %s", path, exc)


def build_illustration_prompt(persona: Any, style: str = "editorial") -> str:
    name = str(getattr(persona, "name", "") or "学者")
    title = str(getattr(persona, "title", "") or "专家")
    bio = str(getattr(persona, "bio", "") or "")[:220]
    stance = str(getattr(persona, "stance", "") or "")

    style_map = {
        "editorial": "半身编辑插画，扁平矢量风格，克制的高级灰配色，纯色背景",
        "clay": "半身黏土 3D 风格，柔和布光，纯色背景",
        "ink": "半身东方水墨插画，留白构图，纯色背景",
    }
    style_text = style_map.get(style, style_map["editorial"])

    return (
        f"为 AI 专家「{name}」绘制一张方形头像插画。身份：{title}。"
        f"人物气质与学术立场：{stance or '理性、审慎'}。背景线索：{bio or '学术研究'}。"
        f"风格：{style_text}。构图：人物居中，肩部以上半身，正面或四分之三侧脸，"
        "表情平和自信，服饰符合其学科身份。画面干净，无文字、无 logo、无水印、无边框。"
        "必须是虚构的原创人物形象，不得模仿任何真实人物、名人的相貌。"
    )


def generate_illustration_bytes(persona: Any, style: str = "editorial") -> bytes:
    """Ask the configured OpenAI-compatible image endpoint for one illustration."""
    api_key = (settings.IMAGE_GEN_API_KEY or "").strip()
    model = (settings.IMAGE_GEN_MODEL or "").strip()
    if not api_key or not model:
        raise AvatarGenerationUnavailable("未配置插画生成服务")

    base = (settings.IMAGE_GEN_BASE_URL or "").rstrip("/")
    endpoint = f"{base}/images/generations"
    payload = {
        "model": model,
        "prompt": build_illustration_prompt(persona, style),
        "size": "1024x1024",
        "response_format": "url",
        "n": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=max(10, settings.IMAGE_GEN_TIMEOUT_SECONDS),
        )
    except requests.RequestException as exc:
        logger.warning("Avatar illustration request failed: %s", exc)
        raise AvatarGenerationUnavailable("插画服务连接失败，请稍后重试") from exc

    if response.status_code >= 400:
        logger.warning("Avatar illustration rejected: %s %s", response.status_code, response.text[:300])
        raise AvatarGenerationUnavailable("插画服务暂时不可用，请稍后重试")

    try:
        data = response.json()
        item = (data.get("data") or [{}])[0]
    except (ValueError, AttributeError) as exc:
        raise AvatarGenerationUnavailable("插画服务返回格式异常") from exc

    if item.get("b64_json"):
        try:
            return base64.b64decode(item["b64_json"])
        except (ValueError, TypeError) as exc:
            raise AvatarGenerationUnavailable("插画数据解析失败") from exc

    url = item.get("url")
    if not url:
        raise AvatarGenerationUnavailable("插画服务未返回图片")

    try:
        download = requests.get(url, timeout=max(10, settings.IMAGE_GEN_TIMEOUT_SECONDS))
        download.raise_for_status()
    except requests.RequestException as exc:
        raise AvatarGenerationUnavailable("插画下载失败，请稍后重试") from exc

    return download.content
