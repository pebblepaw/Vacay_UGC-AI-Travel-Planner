"""
Video Downloader Service using yt-dlp.
Downloads videos from TikTok, YouTube, Douyin, RedNote, and Instagram.
"""
import yt_dlp
from pathlib import Path
import uuid
import asyncio
import logging

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
            "format": "best[ext=mp4]/best",
            "outtmpl": output_path,
            "quiet": not settings.DEBUG,
            "no_warnings": not settings.DEBUG,
            "max_filesize": self.max_size_bytes,
            "socket_timeout": self.timeout,
            "cookiefile": None,
            "writeinfojson": False,
            "writethumbnail": False,
        }

    async def download_video(self, url: str) -> dict:
        """Download a video from URL and return metadata."""
        platform = self._detect_platform(url)
        try:
            video_id = str(uuid.uuid4())[:8]
            output_template = str(self.download_dir / f"{video_id}.%(ext)s")
            ydl_opts = self._get_ydl_opts(output_template)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._download_sync, url, ydl_opts)
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
                    "title": title,
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
