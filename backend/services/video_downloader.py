"""
Video Downloader Service using yt-dlp.
Downloads videos from TikTok, YouTube, Douyin, RedNote, and Instagram.
"""
import html
import yt_dlp
from pathlib import Path
import uuid
import asyncio
import logging
import re
from urllib.parse import quote

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class VideoDownloaderService:
    """Service for downloading videos using yt-dlp."""

    def __init__(self):
        self.download_dir = settings.DOWNLOADS_DIR
        self.max_size_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
        self.timeout = settings.DOWNLOAD_TIMEOUT_SECONDS

    def _get_ydl_opts(self, output_path: str) -> dict:
        """Get yt-dlp options for downloading."""
        return {
            "format": "best[ext=mp4][height<=540]/best[height<=540]/best[ext=mp4]/best",
            "format_sort": ["res:540", "+size", "+br", "codec:h264"],
            "outtmpl": output_path,
            "quiet": not settings.DEBUG,
            "no_warnings": not settings.DEBUG,
            "max_filesize": self.max_size_bytes,
            "socket_timeout": self.timeout,
            "cookiefile": None,
            "writeinfojson": False,
            "writethumbnail": False,
            "noplaylist": True,
            "merge_output_format": "mp4",
        }

    def public_media_url(self, file_path: str) -> str:
        """Expose downloaded media through the backend static mount."""
        filename = Path(file_path).name
        base = settings.PUBLIC_API_BASE_URL.rstrip("/")
        return f"{base}/media/{quote(filename)}"

    async def download_video(self, url: str) -> dict:
        """Download a video from URL and return metadata."""
        platform = self._detect_platform(url)
        try:
            if platform == "tiktok" and "/photo/" in url.lower():
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._download_tiktok_photo_post, url)
                result.setdefault("url", url)
                result.setdefault("platform", platform)
                return result

            video_id = str(uuid.uuid4())[:8]
            output_template = str(self.download_dir / f"{video_id}.%(ext)s")
            ydl_opts = self._get_ydl_opts(output_template)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._download_sync, url, ydl_opts)
            if (
                not result.get("success")
                and platform == "tiktok"
                and "/photo/" in url.lower()
            ):
                result = await loop.run_in_executor(None, self._download_tiktok_photo_post, url)
            result.setdefault("url", url)
            result.setdefault("platform", platform)
            return result

        except Exception as e:
            logger.error("Error downloading video from %s: %s", url, e)
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "title": "Unknown",
                "platform": platform,
            }

    def _download_sync(self, url: str, ydl_opts: dict) -> dict:
        """Synchronous download using yt-dlp."""
        platform = self._detect_platform(url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Untitled")

                filesize = info.get("filesize") or info.get("filesize_approx", 0)
                if filesize > self.max_size_bytes:
                    return {
                        "success": False,
                        "url": url,
                        "error": f"Video too large ({filesize / 1024 / 1024:.1f}MB > {settings.MAX_VIDEO_SIZE_MB}MB)",
                        "title": title,
                        "platform": platform,
                    }

                info_dict = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info_dict)

                if not Path(file_path).exists():
                    return {
                        "success": False,
                        "url": url,
                        "error": "Download completed but file not found",
                        "title": title,
                        "platform": platform,
                    }

                logger.info("Downloaded video: %s -> %s", title, file_path)
                return {
                    "success": True,
                    "url": url,
                    "file_path": file_path,
                    "preview_url": self.public_media_url(file_path),
                    "title": title,
                    "description": info.get("description") or title,
                    "platform": platform,
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                }

            except yt_dlp.utils.DownloadError as e:
                logger.error("yt-dlp download error for %s: %s", url, e)
                return {
                    "success": False,
                    "url": url,
                    "error": f"Download failed: {str(e)}",
                    "title": "Unknown",
                    "platform": platform,
                }

    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "douyin.com" in url_lower:
            return "douyin"
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "xiaohongshu.com" in url_lower or "rednote" in url_lower:
            return "rednote"
        if "instagram.com" in url_lower:
            return "instagram"
        return "unknown"

    def _decode_embedded_text(self, value: str) -> str:
        decoded = value.replace("\\u002F", "/").replace("\\/", "/")
        try:
            decoded = bytes(decoded, "utf-8").decode("unicode_escape")
        except Exception:
            pass
        return html.unescape(decoded).strip()

    def _download_tiktok_photo_post(self, url: str) -> dict:
        match = re.search(r"/photo/(\d+)", url)
        if not match:
            return {
                "success": False,
                "url": url,
                "error": f"Unsupported TikTok photo URL: {url}",
                "title": "Unknown",
                "platform": "tiktok",
            }

        post_id = match.group(1)
        mobile_url = f"https://www.tiktok.com/@/video/{post_id}?_r=1"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            )
        }

        with httpx.Client(headers=headers, follow_redirects=True, timeout=self.timeout) as client:
            response = client.get(mobile_url)
            response.raise_for_status()
            page = response.text

            desc_match = re.search(r'"desc":"(.*?)"', page, re.S)
            desc = self._decode_embedded_text(desc_match.group(1)) if desc_match else ""

            image_match = re.search(
                r'<link[^>]+rel="preload"[^>]+as="image"[^>]+href="([^"]+tplv-photomode-image\.jpeg[^"]*)"',
                page,
                re.I,
            )
            if not image_match:
                image_match = re.search(
                    r'(https://[^"\']+tplv-photomode-image\.jpeg[^"\']*)',
                    page,
                    re.I,
                )
            if not image_match:
                return {
                    "success": False,
                    "url": url,
                    "error": "TikTok photo post did not expose an image URL",
                    "title": desc or "Unknown",
                    "platform": "tiktok",
                }

            image_url = self._decode_embedded_text(image_match.group(1))
            image_bytes = client.get(image_url).content
            if not image_bytes:
                return {
                    "success": False,
                    "url": url,
                    "error": "TikTok photo image download returned no bytes",
                    "title": desc or "Unknown",
                    "platform": "tiktok",
                }

        file_path = self.download_dir / f"{uuid.uuid4().hex[:8]}.jpg"
        file_path.write_bytes(image_bytes)

        title = desc or "TikTok photo post"
        return {
            "success": True,
            "url": url,
            "file_path": str(file_path),
            "preview_url": self.public_media_url(str(file_path)),
            "title": title[:120],
            "description": desc or title,
            "platform": "tiktok",
            "thumbnail": image_url,
        }

    def cleanup_video(self, file_path: str) -> bool:
        """Delete a downloaded video file."""
        try:
            Path(file_path).unlink(missing_ok=True)
            logger.info("Deleted video: %s", file_path)
            return True
        except Exception as e:
            logger.error("Error deleting %s: %s", file_path, e)
            return False

    async def download_multiple(self, urls: list[str]) -> list[dict]:
        """Download multiple videos concurrently."""
        tasks = [self.download_video(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)


video_downloader = VideoDownloaderService()
