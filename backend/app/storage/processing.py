"""File type detection, photo thumbnails, and video posters. All functions are blocking;
call them through a thread pool."""

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.enums import MediaKind

pillow_heif.register_heif_opener()

THUMBNAIL_SIZE = (480, 480)
THUMBNAIL_QUALITY = 80
MAX_IMAGE_PIXELS = 120_000_000
FFMPEG_TIMEOUT_SECONDS = 60
SNIFF_BYTES = 32

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

_HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1"}
_MP4_BRANDS = {
    b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash", b"mmp4"
}  # fmt: skip
_QUICKTIME_BRANDS = {b"qt  "}


@dataclass(frozen=True)
class DetectedType:
    kind: MediaKind
    mime_type: str
    extension: str


JPEG = DetectedType(MediaKind.PHOTO, "image/jpeg", "jpg")
PNG = DetectedType(MediaKind.PHOTO, "image/png", "png")
WEBP = DetectedType(MediaKind.PHOTO, "image/webp", "webp")
HEIC = DetectedType(MediaKind.PHOTO, "image/heic", "heic")
MP4 = DetectedType(MediaKind.VIDEO, "video/mp4", "mp4")
QUICKTIME = DetectedType(MediaKind.VIDEO, "video/quicktime", "mov")


def detect_type(header: bytes) -> DetectedType | None:
    """Identify an allowed file type by its signature; the client content type is ignored."""
    if header.startswith(b"\xff\xd8\xff"):
        return JPEG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return WEBP
    if header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in _HEIC_BRANDS:
            return HEIC
        if brand in _QUICKTIME_BRANDS:
            return QUICKTIME
        if brand in _MP4_BRANDS:
            return MP4
    if header[4:8] in (b"moov", b"mdat", b"wide", b"free"):
        return QUICKTIME
    return None


class ThumbnailError(Exception):
    """The file claims to be an image but cannot be decoded."""


def make_photo_thumbnail(source: BinaryIO) -> bytes:
    source.seek(0)
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(THUMBNAIL_SIZE)
            return _encode_webp(image)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ThumbnailError(str(exc)) from exc


def _encode_webp(image: Image.Image) -> bytes:
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=THUMBNAIL_QUALITY)
    return buffer.getvalue()


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def make_video_poster(source: BinaryIO, extension: str) -> bytes | None:
    """Extract a poster frame with ffmpeg. Returns None if ffmpeg is missing or fails."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    with tempfile.TemporaryDirectory() as directory:
        video_path = Path(directory) / f"source.{extension}"
        source.seek(0)
        with video_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        for offset in ("1", "0"):
            frame = _grab_frame(ffmpeg, video_path, offset)
            if frame:
                try:
                    with Image.open(io.BytesIO(frame)) as image:
                        image.thumbnail(THUMBNAIL_SIZE)
                        return _encode_webp(image)
                except (UnidentifiedImageError, OSError):
                    return None
    return None


def _grab_frame(ffmpeg: str, video_path: Path, offset: str) -> bytes | None:
    command = [
        ffmpeg, "-v", "error", "-ss", offset, "-i", str(video_path),
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]  # fmt: skip
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 and completed.stdout else None
