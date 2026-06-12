#!/usr/bin/env python3
"""Download, merge, deduplicate, and write IPTV M3U playlists."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCES_FILE = Path("sources.txt")
OUTPUT_FILE = Path("output/index.m3u")
TIMEOUT_SECONDS = 15

CCTV_KEYWORDS = ("cctv", "央视", "中央电视")
MIGU_KEYWORDS = ("咪咕", "migu", "miguvideo")
SATELLITE_KEYWORDS = (
    "卫视",
    "安徽 tv",
    "anhui tv",
    "北京 tv",
    "beijing tv",
    "重庆 tv",
    "chongqing tv",
    "东方 tv",
    "dragon tv",
    "福建 tv",
    "fujian tv",
    "甘肃 tv",
    "gansu tv",
    "广东 tv",
    "guangdong tv",
    "广西 tv",
    "guangxi tv",
    "贵州 tv",
    "guizhou tv",
    "海南 tv",
    "hainan tv",
    "河北 tv",
    "hebei tv",
    "黑龙江 tv",
    "heilongjiang tv",
    "河南 tv",
    "henan tv",
    "湖北 tv",
    "hubei tv",
    "湖南 tv",
    "hunan tv",
    "江苏 tv",
    "jiangsu tv",
    "江西 tv",
    "jiangxi tv",
    "吉林 tv",
    "jilin tv",
    "辽宁 tv",
    "liaoning tv",
    "内蒙古 tv",
    "inner mongolia tv",
    "宁夏 tv",
    "ningxia tv",
    "青海 tv",
    "qinghai tv",
    "山东 tv",
    "shandong tv",
    "山西 tv",
    "shanxi tv",
    "陕西 tv",
    "shaanxi tv",
    "深圳 tv",
    "shenzhen tv",
    "四川 tv",
    "sichuan tv",
    "天津 tv",
    "tianjin tv",
    "西藏 tv",
    "xizang tv",
    "tibet tv",
    "新疆 tv",
    "xinjiang tv",
    "云南 tv",
    "yunnan tv",
    "浙江 tv",
    "zhejiang tv",
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def read_sources(path: Path) -> list[str]:
    """Read source URLs, ignoring blank lines and comments."""
    if not path.exists():
        raise FileNotFoundError(f"找不到源列表文件: {path}")

    sources: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        sources.append(url)
    return sources


def download_m3u(url: str) -> Optional[str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IPTV-M3U-Updater/1.0)",
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            data = response.read()
        return data.decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logging.warning("下载失败: %s (%s)", url, exc)
        return None


def iter_channels(m3u_text: str) -> Iterable[tuple[str, str]]:
    """Yield (#EXTINF line, stream URL) pairs from an M3U playlist."""
    pending_extinf: Optional[str] = None

    for raw_line in m3u_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF"):
            pending_extinf = line
            continue

        if line.startswith("#"):
            continue

        if pending_extinf:
            yield pending_extinf, line
            pending_extinf = None


def channel_name(extinf: str) -> str:
    if "," not in extinf:
        return extinf
    return extinf.rsplit(",", 1)[-1].strip()


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("_", " ").split())


def is_cctv_channel(extinf: str) -> bool:
    name = normalize_text(channel_name(extinf))
    info = normalize_text(extinf)
    return (
        re.search(r"\bcctv\s*(?:\+|\d|4k|8k)", name) is not None
        or re.search(r"\bcctv\s*[- ]\s*(?:billiards|culture|golf|health|nostalgia|storm|the|weapon|women|world)", name) is not None
        or any(keyword in info for keyword in ("央视", "中央电视"))
        or ('tvg-id="cctv' in info and ".cn@" in info)
    )


def is_wanted_channel(extinf: str, stream_url: str) -> bool:
    info = normalize_text(f"{extinf} {channel_name(extinf)}")
    with_url = normalize_text(f"{info} {stream_url}")
    return (
        is_cctv_channel(extinf)
        or any(keyword in with_url for keyword in MIGU_KEYWORDS)
        or any(keyword in info for keyword in SATELLITE_KEYWORDS)
    )


def merge_channels(playlists: Iterable[str]) -> list[tuple[str, str]]:
    seen_urls: set[str] = set()
    merged: list[tuple[str, str]] = []

    for playlist in playlists:
        for extinf, stream_url in iter_channels(playlist):
            if not is_wanted_channel(extinf, stream_url):
                continue
            if stream_url in seen_urls:
                continue
            seen_urls.add(stream_url)
            merged.append((extinf, stream_url))

    return merged


def write_output(path: Path, channels: Iterable[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["#EXTM3U"]
    for extinf, stream_url in channels:
        lines.append(extinf)
        lines.append(stream_url)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        sources = read_sources(SOURCES_FILE)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    playlists: list[str] = []
    for source_url in sources:
        text = download_m3u(source_url)
        if text is not None:
            playlists.append(text)

    channels = merge_channels(playlists)
    write_output(OUTPUT_FILE, channels)

    logging.info("本次成功下载源数量: %d/%d", len(playlists), len(sources))
    logging.info("合并去重后频道数量: %d", len(channels))
    logging.info("已输出到: %s", OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
