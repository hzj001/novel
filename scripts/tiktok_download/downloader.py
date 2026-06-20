#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TikTok 视频自动下载脚本

基于 yt-dlp 实现，支持：
  - 下载单个视频链接
  - 从文本文件批量下载（每行一个链接）
  - 下载某个用户主页的全部视频（或最近 N 个）
  - 默认尝试下载无水印版本，自动保存元数据与缩略图

用法示例：
  python downloader.py "https://www.tiktok.com/@user/video/123456789"
  python downloader.py -f links.txt
  python downloader.py "https://www.tiktok.com/@user" --max 20
  python downloader.py "https://www.tiktok.com/@user/video/123" -o ./videos --cookies cookies.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("缺少依赖 yt-dlp，请先安装：pip install -U yt-dlp", file=sys.stderr)
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "downloads"


def read_links_from_file(path: Path) -> list[str]:
    """从文本文件读取链接，每行一个，忽略空行与 # 注释。"""
    links: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        links.append(line)
    return links


def build_ydl_opts(
    output_dir: Path,
    max_videos: int | None,
    cookies: Path | None,
    from_browser: str | None,
    audio_only: bool,
    quiet: bool,
) -> dict:
    """构造 yt-dlp 配置。"""
    # 按 上传者/创建时间_视频ID 组织文件，避免重名覆盖
    # timestamp 为视频创建时间（Unix 时间戳），格式化为 年月日_时分秒
    outtmpl = str(
        output_dir
        / "%(uploader|unknown)s"
        / "%(timestamp>%Y%m%d_%H%M%S|unknown)s_%(id)s.%(ext)s"
    )

    opts: dict = {
        "outtmpl": outtmpl,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "ignoreerrors": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "writethumbnail": True,
        "writeinfojson": True,
        "quiet": quiet,
        "no_warnings": quiet,
        # 跳过已下载过的链接（基于下面的 archive 文件）
        "download_archive": str(output_dir / ".download_archive.txt"),
    }

    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # TikTok 通常是单一 mp4，优先取最佳画质
        opts["format"] = "best"
        opts["merge_output_format"] = "mp4"

    if max_videos is not None:
        opts["playlistend"] = max_videos

    if cookies is not None:
        opts["cookiefile"] = str(cookies)

    # 直接读取本地浏览器中已登录的 Cookie（你在浏览器里登录 TikTok 即可）
    # 支持: chrome / edge / firefox / brave / chromium / opera / vivaldi / safari
    if from_browser is not None:
        opts["cookiesfrombrowser"] = (from_browser.lower(),)

    return opts


def download(
    urls: list[str],
    output_dir: Path,
    max_videos: int | None = None,
    cookies: Path | None = None,
    from_browser: str | None = None,
    audio_only: bool = False,
    quiet: bool = False,
) -> int:
    """执行下载，返回失败数量。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    opts = build_ydl_opts(output_dir, max_videos, cookies, from_browser, audio_only, quiet)

    with yt_dlp.YoutubeDL(opts) as ydl:
        ret = ydl.download(urls)
    return ret


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="基于 yt-dlp 的 TikTok 视频下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="一个或多个 TikTok 链接（视频/用户主页）",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="从文本文件批量读取链接（每行一个）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"下载保存目录（默认：{DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="下载用户主页时，最多下载多少个视频（默认全部）",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="cookies.txt 文件路径（下载私密/受限内容时使用）",
    )
    parser.add_argument(
        "--from-browser",
        type=str,
        default=None,
        metavar="BROWSER",
        help="直接读取本地浏览器登录态（你登录即可）："
        "chrome/edge/firefox/brave/chromium/opera/vivaldi/safari",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="仅提取音频并转为 mp3（需要 ffmpeg）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="安静模式，减少输出",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    urls: list[str] = list(args.urls)
    if args.file:
        if not args.file.exists():
            print(f"链接文件不存在: {args.file}", file=sys.stderr)
            return 2
        urls.extend(read_links_from_file(args.file))

    if not urls:
        print("未提供任何链接。请传入链接或使用 -f 指定链接文件。", file=sys.stderr)
        print("示例: python downloader.py \"https://www.tiktok.com/@user/video/123\"", file=sys.stderr)
        return 2

    print(f"准备下载 {len(urls)} 个链接，保存到: {args.output}")
    failed = download(
        urls,
        output_dir=args.output,
        max_videos=args.max,
        cookies=args.cookies,
        from_browser=args.from_browser,
        audio_only=args.audio_only,
        quiet=args.quiet,
    )

    if failed:
        print(f"完成，但有 {failed} 个链接下载失败。", file=sys.stderr)
        return 1
    print("全部下载完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
