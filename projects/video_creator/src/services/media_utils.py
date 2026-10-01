import os
import re
import subprocess

import imageio_ffmpeg


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_media(path: str) -> dict:
    """
    Inspect a media file with `ffmpeg -i` (imageio-ffmpeg ships no ffprobe).
    Returns {duration, width, height, has_audio, has_video, size_bytes}.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Media file not found: {path}")

    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    err = proc.stderr  # ffmpeg prints stream info on stderr and exits 1 (no output file)

    duration = 0.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    width = height = 0
    has_video = False
    for line in err.splitlines():
        if "Video:" in line and "Stream" in line:
            has_video = True
            dims = re.search(r"(\d{2,5})x(\d{2,5})", line.split("Video:", 1)[1])
            if dims:
                width, height = int(dims.group(1)), int(dims.group(2))
            break

    has_audio = any("Audio:" in l and "Stream" in l for l in err.splitlines())

    return {
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "has_video": has_video,
        "has_audio": has_audio,
        "size_bytes": os.path.getsize(path),
    }
