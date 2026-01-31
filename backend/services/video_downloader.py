"""
Video Downloader Service using yt-dlp.
Downloads videos from TikTok, YouTube, Douyin, RedNote and saves locally.
"""
import yt_dlp
from pathlib import Path
import uuid
import asyncio
from typing import Optional
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
            'format': 'best[ext=mp4]/best',  # Prefer mp4
            'outtmpl': output_path,
            'quiet': not settings.DEBUG,
            'no_warnings': not settings.DEBUG,
            # File size limit
            'max_filesize': self.max_size_bytes,
            # Timeout settings
            'socket_timeout': self.timeout,
            # TikTok-specific: sometimes needs cookies
            'cookiefile': None,  # Can add cookies later if needed
            # Extract video metadata
            'writeinfojson': False,
            'writethumbnail': False,
        }
    
    async def download_video(self, url: str) -> dict:
        """
        Download a video from URL and return metadata.
        
        Args:
            url: Video URL (TikTok, YouTube, Douyin, RedNote)
            
        Returns:
            dict with keys:
                - success: bool
                - file_path: str (if success)
                - title: str (video title)
                - platform: str (tiktok, youtube, etc.)
                - error: str (if failed)
        """
        try:
            # Generate unique filename
            video_id = str(uuid.uuid4())[:8]
            output_template = str(self.download_dir / f"{video_id}.%(ext)s")
            
            ydl_opts = self._get_ydl_opts(output_template)
            
            # Run yt-dlp in thread pool (blocking call)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._download_sync,
                url,
                ydl_opts
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading video from {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'title': 'Unknown',
                'platform': self._detect_platform(url)
            }
    
    def _download_sync(self, url: str, ydl_opts: dict) -> dict:
        """Synchronous download using yt-dlp."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extract info first (doesn't download yet)
                info = ydl.extract_info(url, download=False)
                
                title = info.get('title', 'Untitled')
                platform = self._detect_platform(url)
                
                # Check file size before downloading
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                if filesize > self.max_size_bytes:
                    return {
                        'success': False,
                        'error': f'Video too large ({filesize / 1024 / 1024:.1f}MB > {settings.MAX_VIDEO_SIZE_MB}MB)',
                        'title': title,
                        'platform': platform
                    }
                
                # Download the video
                info_dict = ydl.extract_info(url, download=True)
                
                # Get the actual downloaded filename from yt-dlp
                file_path = ydl.prepare_filename(info_dict)
                
                if not Path(file_path).exists():
                    return {
                        'success': False,
                        'error': 'Download completed but file not found',
                        'title': title,
                        'platform': platform
                    }
                
                logger.info(f"Downloaded video: {title} -> {file_path}")
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'title': title,
                    'platform': platform,
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail')
                }
                
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"yt-dlp download error for {url}: {e}")
                return {
                    'success': False,
                    'error': f'Download failed: {str(e)}',
                    'title': 'Unknown',
                    'platform': self._detect_platform(url)
                }
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower:
            return 'douyin'
        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'xiaohongshu.com' in url_lower or 'rednote' in url_lower:
            return 'rednote'
        else:
            return 'unknown'
    
    def cleanup_video(self, file_path: str) -> bool:
        """Delete a downloaded video file."""
        try:
            Path(file_path).unlink(missing_ok=True)
            logger.info(f"Deleted video: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting {file_path}: {e}")
            return False
    
    async def download_multiple(self, urls: list[str]) -> list[dict]:
        """Download multiple videos concurrently."""
        tasks = [self.download_video(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)


# Singleton instance
video_downloader = VideoDownloaderService()
