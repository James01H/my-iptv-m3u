#!/usr/bin/env python3
"""Download, merge, deduplicate, and write IPTV M3U playlists."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging
import os
import re
import time
from pathlib import Path
from typing import Iterable, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCES_FILE = Path("sources.txt")
MANUAL_CHANNELS_FILE = Path("manual_channels.m3u")
OUTPUT_FILE = Path("output/index.m3u")
TIMEOUT_SECONDS = 15
STREAM_TEST_TIMEOUT_SECONDS = 8
MAX_TEST_WORKERS = 24
ENABLE_STREAM_TEST = os.getenv("CHECK_STREAMS") == "1"
INCLUDE_ALL_SOURCES = {
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Migu.m3u",
    str(MANUAL_CHANNELS_FILE),
}

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
NON_STREAM_SUFFIXES = (".txt", ".md", ".html", ".htm", ".xml", ".json", ".gz")


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass(frozen=True)
class Channel:
    extinf: str
    stream_url: str
    source_url: str
    source_order: int
    entry_order: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class TestedChannel:
    channel: Channel
    latency_ms: int


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


def iter_channels(m3u_text: str) -> Iterable[tuple[str, str, tuple[str, ...]]]:
    """Yield (#EXTINF line, stream URL, full entry lines) from an M3U playlist."""
    pending_extinf: Optional[str] = None
    entry_lines: list[str] = []

    for raw_line in m3u_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF"):
            pending_extinf = line
            entry_lines = [line]
            continue

        if line.startswith("#") and pending_extinf:
            entry_lines.append(line)
            continue

        if line.startswith("#"):
            continue

        if pending_extinf:
            yield pending_extinf, line, tuple(entry_lines + [line])
            pending_extinf = None
            entry_lines = []


def channel_name(extinf: str) -> str:
    if "," not in extinf:
        return extinf
    return extinf.rsplit(",", 1)[-1].strip()


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("_", " ").split())


def is_probable_stream_url(stream_url: str) -> bool:
    lower_url = stream_url.strip().lower()
    clean_url = lower_url.split("?", 1)[0].rstrip("/")
    if not lower_url.startswith(("http://", "https://", "rtmp://", "rtsp://")):
        return False
    if "raw.githubusercontent.com" in lower_url or "github.com" in lower_url:
        return False
    if clean_url.endswith(NON_STREAM_SUFFIXES):
        return False
    return True


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


def should_include_all(source_url: str) -> bool:
    return source_url in INCLUDE_ALL_SOURCES


def merge_channels(playlists: Iterable[tuple[str, str]]) -> list[Channel]:
    seen_urls: set[str] = set()
    merged: list[Channel] = []

    for source_order, (source_url, playlist) in enumerate(playlists):
        include_all = should_include_all(source_url)
        for entry_order, (extinf, stream_url, entry_lines) in enumerate(
            iter_channels(playlist)
        ):
            if not is_probable_stream_url(stream_url):
                continue
            if not include_all and not is_wanted_channel(extinf, stream_url):
                continue
            if stream_url in seen_urls:
                continue
            seen_urls.add(stream_url)
            merged.append(
                Channel(
                    extinf,
                    stream_url,
                    source_url,
                    source_order,
                    entry_order,
                    entry_lines,
                )
            )

    return merged


def test_stream(channel: Channel) -> Optional[TestedChannel]:
    request = Request(
        channel.stream_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IPTV-M3U-Updater/1.0)",
            "Range": "bytes=0-4095",
        },
    )
    started_at = time.monotonic()

    try:
        with urlopen(request, timeout=STREAM_TEST_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                return None
            response.read(4096)
    except (HTTPError, URLError, TimeoutError, OSError):
        return None

    latency_ms = int((time.monotonic() - started_at) * 1000)
    return TestedChannel(channel, latency_ms)


def test_channels(channels: Sequence[Channel]) -> list[TestedChannel]:
    if not channels:
        return []

    working: list[TestedChannel] = []
    max_workers = min(MAX_TEST_WORKERS, len(channels))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_channel = {
            executor.submit(test_stream, channel): channel for channel in channels
        }
        for checked_count, future in enumerate(as_completed(future_to_channel), 1):
            tested = future.result()
            if tested is not None:
                working.append(tested)
            if checked_count % 100 == 0 or checked_count == len(channels):
                logging.info(
                    "已检测频道: %d/%d，可用: %d",
                    checked_count,
                    len(channels),
                    len(working),
                )

    return sorted(
        working,
        key=lambda item: (
            normalize_text(channel_name(item.channel.extinf)),
            item.latency_ms,
            item.channel.source_order,
        ),
    )


def write_output(path: Path, channels: Iterable[TestedChannel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["#EXTM3U"]
    for tested in channels:
        lines.extend(tested.channel.lines)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_channels_output(path: Path, channels: Iterable[Channel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["#EXTM3U"]
    for channel in channels:
        lines.extend(channel.lines)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        sources = read_sources(SOURCES_FILE)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    playlists: list[tuple[str, str]] = []
    if MANUAL_CHANNELS_FILE.exists():
        playlists.append(
            (str(MANUAL_CHANNELS_FILE), MANUAL_CHANNELS_FILE.read_text(encoding="utf-8"))
        )

    for source_url in sources:
        text = download_m3u(source_url)
        if text is not None:
            playlists.append((source_url, text))

    channels = merge_channels(playlists)
    downloaded_count = max(len(playlists) - int(MANUAL_CHANNELS_FILE.exists()), 0)
    if sources and downloaded_count == 0:
        logging.error("所有源都下载失败，保留现有输出文件不覆盖。")
        return 1
    if sources and not channels:
        logging.error("过滤后没有可用频道，保留现有输出文件不覆盖。")
        return 1

    if ENABLE_STREAM_TEST:
        tested_channels = test_channels(channels)
        if sources and not tested_channels:
            logging.error("检测后没有可用频道，保留现有输出文件不覆盖。")
            return 1
        write_output(OUTPUT_FILE, tested_channels)
        output_count = len(tested_channels)
    else:
        write_channels_output(OUTPUT_FILE, channels)
        output_count = len(channels)

    logging.info("本次成功下载源数量: %d/%d", downloaded_count, len(sources))
    logging.info("合并去重后候选频道数量: %d", len(channels))
    if ENABLE_STREAM_TEST:
        logging.info("检测可用频道数量: %d", output_count)
    else:
        logging.info("未启用测速检测，保留原始可播放参数。")
    logging.info("输出频道数量: %d", output_count)
    logging.info("已输出到: %s", OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
