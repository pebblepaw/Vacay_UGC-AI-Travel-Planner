"""
Video Downloader Service using yt-dlp.
Downloads videos from TikTok, YouTube, Douyin, RedNote, and Instagram.
"""
import html
from pathlib import Path
import uuid
import asyncio
import logging
import re
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw, ImageFont
import yt_dlp

from backend.config import settings

logger = logging.getLogger(__name__)


class VideoDownloaderService:
    """Service for downloading videos using yt-dlp."""

    _SOCIAL_FALLBACK_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    _METADATA_CARD_ERROR_MARKERS = {
        "douyin": (
            "fresh cookies",
            "not necessarily logged in",
            "login required",
            "unable to extract",
        ),
        "rednote": (
            "no video formats found",
            "fresh cookies",
            "not necessarily logged in",
            "login required",
            "unable to extract",
        ),
    }
    _METADATA_CARD_PLATFORM_LABELS = {
        "douyin": "Douyin",
        "rednote": "Rednote",
    }

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
            ):
                if "/photo/" in url.lower():
                    result = await loop.run_in_executor(None, self._download_tiktok_photo_post, url)
                else:
                    result = await loop.run_in_executor(None, self._download_tiktok_video_page, url)
            elif (
                not result.get("success")
                and self._should_try_metadata_card_fallback(platform, str(result.get("error") or ""))
            ):
                fallback_result = await loop.run_in_executor(
                    None,
                    self._download_platform_metadata_card,
                    url,
                    platform,
                    str(result.get("error") or ""),
                )
                if fallback_result.get("success"):
                    result = fallback_result
                else:
                    result["fallback_error"] = fallback_result.get("error")
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
        if "xiaohongshu.com" in url_lower or "rednote" in url_lower or "xhslink.com" in url_lower:
            return "rednote"
        if "instagram.com" in url_lower:
            return "instagram"
        return "unknown"

    def _should_try_metadata_card_fallback(self, platform: str, error: str) -> bool:
        markers = self._METADATA_CARD_ERROR_MARKERS.get(platform)
        if not markers:
            return False
        lowered = (error or "").lower()
        return any(marker in lowered for marker in markers)

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

    def _download_tiktok_video_page(self, url: str) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            )
        }

        with httpx.Client(headers=headers, follow_redirects=True, timeout=self.timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            page = response.text

            desc_match = re.search(r'"desc":"(.*?)"', page, re.S)
            desc = self._decode_embedded_text(desc_match.group(1)) if desc_match else ""

            video_match = re.search(r'"playAddr":"(.*?)"', page, re.S)
            if not video_match:
                video_match = re.search(r'"downloadAddr":"(.*?)"', page, re.S)
            if not video_match:
                return {
                    "success": False,
                    "url": url,
                    "error": "TikTok page did not expose a playable video URL",
                    "title": desc or "Unknown",
                    "platform": "tiktok",
                }

            video_url = self._decode_embedded_text(video_match.group(1))
            if not video_url:
                return {
                    "success": False,
                    "url": url,
                    "error": "TikTok video URL was empty after decoding",
                    "title": desc or "Unknown",
                    "platform": "tiktok",
                }

            thumbnail_match = re.search(r'"cover":"(.*?)"', page, re.S)
            thumbnail = self._decode_embedded_text(thumbnail_match.group(1)) if thumbnail_match else ""

            file_path = self.download_dir / f"{uuid.uuid4().hex[:8]}.mp4"
            total_bytes = 0
            with client.stream("GET", video_url) as video_response:
                video_response.raise_for_status()
                with file_path.open("wb") as output_file:
                    for chunk in video_response.iter_bytes():
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if total_bytes > self.max_size_bytes:
                            file_path.unlink(missing_ok=True)
                            return {
                                "success": False,
                                "url": url,
                                "error": (
                                    f"Video too large ({total_bytes / 1024 / 1024:.1f}MB > "
                                    f"{settings.MAX_VIDEO_SIZE_MB}MB)"
                                ),
                                "title": desc or "Unknown",
                                "platform": "tiktok",
                            }
                        output_file.write(chunk)

        title = (desc or "TikTok video").strip()
        return {
            "success": True,
            "url": url,
            "file_path": str(file_path),
            "preview_url": self.public_media_url(str(file_path)),
            "title": title[:120],
            "description": desc or title,
            "platform": "tiktok",
            "thumbnail": thumbnail,
        }

    def _download_platform_metadata_card(self, url: str, platform: str, download_error: str) -> dict:
        metadata = self._resolve_platform_metadata(url, platform)
        if not metadata:
            return {
                "success": False,
                "url": url,
                "error": f"Metadata fallback unavailable after extractor failure: {download_error}",
                "title": "Unknown",
                "platform": platform,
            }

        file_path = self._create_metadata_card(
            platform=platform,
            source_url=metadata.get("final_url") or url,
            title=metadata.get("title") or "Untitled post",
            description=metadata.get("description") or "",
        )
        title = metadata.get("title") or "Untitled post"
        description = metadata.get("description") or title
        logger.info("Built %s metadata fallback card for %s", platform, url)
        return {
            "success": True,
            "url": url,
            "file_path": file_path,
            "preview_url": self.public_media_url(file_path),
            "title": title,
            "description": description,
            "platform": platform,
            "thumbnail": metadata.get("thumbnail"),
            "source_url": metadata.get("final_url") or url,
        }

    def _resolve_platform_metadata(self, url: str, platform: str) -> dict | None:
        if platform == "rednote":
            html_metadata = self._fetch_page_metadata(url)
            if self._metadata_is_usable(html_metadata):
                return html_metadata
            return None

        if platform == "douyin":
            html_metadata = self._fetch_page_metadata(url)
            if self._metadata_is_usable(html_metadata):
                return html_metadata
            douyin_id = self._extract_douyin_video_id(url)
            if not douyin_id:
                return None
            return self._search_tavily_metadata(
                query=f"site:douyin.com/video {douyin_id}",
                preferred_url_fragment=f"/video/{douyin_id}",
            )

        return None

    def _fetch_page_metadata(self, url: str) -> dict | None:
        try:
            with httpx.Client(
                headers=self._SOCIAL_FALLBACK_HEADERS,
                follow_redirects=True,
                timeout=self.timeout,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Metadata page fetch failed for %s: %s", url, exc)
            return None

        page = response.text or ""
        title = self._extract_html_title(page)
        description = self._extract_html_meta_content(page, ("og:description", "description"))
        if not title:
            title = self._extract_html_meta_content(page, ("og:title", "twitter:title"))
        thumbnail = self._extract_html_meta_content(page, ("og:image", "twitter:image"))
        return {
            "title": title or "",
            "description": description or title or "",
            "thumbnail": thumbnail or None,
            "final_url": str(response.url),
        }

    def _search_tavily_metadata(self, query: str, preferred_url_fragment: str | None = None) -> dict | None:
        if not settings.TAVLY_API:
            return None

        payload = {
            "api_key": settings.TAVLY_API,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_images": False,
            "max_results": 5,
        }
        try:
            with httpx.Client(timeout=min(self.timeout, 15.0)) as client:
                response = client.post("https://api.tavily.com/search", json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Tavily metadata search failed for %s: %s", query, exc)
            return None

        results = data.get("results") or []
        selected: dict | None = None
        if preferred_url_fragment:
            selected = next(
                (
                    result
                    for result in results
                    if preferred_url_fragment in str(result.get("url") or "")
                ),
                None,
            )
        if selected is None and results:
            selected = results[0]
        if selected is None:
            return None

        title = self._normalize_metadata_text(str(selected.get("title") or ""))
        description = self._normalize_metadata_text(
            str(selected.get("content") or data.get("answer") or title)
        )
        final_url = str(selected.get("url") or "")
        metadata = {
            "title": title,
            "description": description,
            "thumbnail": None,
            "final_url": final_url,
        }
        return metadata if self._metadata_is_usable(metadata) else None

    def _extract_html_title(self, page: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        return self._normalize_metadata_text(match.group(1) if match else "")

    def _extract_html_meta_content(self, page: str, names: tuple[str, ...]) -> str:
        for name in names:
            patterns = (
                rf'<meta[^>]+property="{re.escape(name)}"[^>]+content="([^"]+)"',
                rf"<meta[^>]+property='{re.escape(name)}'[^>]+content='([^']+)'",
                rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]+)"',
                rf"<meta[^>]+name='{re.escape(name)}'[^>]+content='([^']+)'",
            )
            for pattern in patterns:
                match = re.search(pattern, page, re.I | re.S)
                if match:
                    return self._normalize_metadata_text(match.group(1))
        return ""

    def _normalize_metadata_text(self, value: str) -> str:
        cleaned = html.unescape(value or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _metadata_is_usable(self, metadata: dict | None) -> bool:
        if not metadata:
            return False

        title = self._normalize_metadata_text(str(metadata.get("title") or ""))
        description = self._normalize_metadata_text(str(metadata.get("description") or ""))
        combined = f"{title} {description}".lower()
        if not (title or description):
            return False
        return not any(
            marker in combined
            for marker in (
                "404",
                "not found",
                "page not found",
                "access denied",
                "verification",
                "captcha",
            )
        )

    def _extract_douyin_video_id(self, url: str) -> str | None:
        match = re.search(r"/video/(\d+)", url)
        return match.group(1) if match else None

    def _create_metadata_card(self, *, platform: str, source_url: str, title: str, description: str) -> str:
        image = Image.new("RGB", (1280, 720), color="#101826")
        draw = ImageDraw.Draw(image)
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

        panel_color = "#17263a"
        draw.rounded_rectangle((48, 48, 1232, 672), radius=28, fill=panel_color)
        accent = "#44c8f5" if platform == "douyin" else "#ff6b92"
        draw.rounded_rectangle((72, 72, 320, 128), radius=18, fill=accent)
        platform_label = self._METADATA_CARD_PLATFORM_LABELS.get(platform, platform.title())
        draw.text((96, 90), f"{platform_label} source", fill="#08111f", font=title_font)

        title_text = self._ascii_card_text(title, fallback=f"{platform_label} travel post")
        description_text = self._ascii_card_text(
            description,
            fallback="Media preview unavailable. This card preserves the source metadata for itinerary analysis.",
        )
        source_text = self._ascii_card_text(source_url, fallback="")

        draw.multiline_text(
            (96, 176),
            self._wrap_text(title_text, width=52),
            fill="#f3f7fb",
            font=title_font,
            spacing=10,
        )
        draw.multiline_text(
            (96, 288),
            self._wrap_text(description_text, width=72),
            fill="#d3dfeb",
            font=body_font,
            spacing=8,
        )
        if source_text:
            draw.multiline_text(
                (96, 560),
                self._wrap_text(f"Source: {source_text}", width=84),
                fill="#7ec4d5",
                font=body_font,
                spacing=6,
            )

        file_path = self.download_dir / f"{uuid.uuid4().hex[:8]}.png"
        image.save(file_path, format="PNG")
        return str(file_path)

    def _ascii_card_text(self, value: str, fallback: str) -> str:
        normalized = self._normalize_metadata_text(value)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").strip()
        return ascii_text or fallback

    def _wrap_text(self, value: str, width: int) -> str:
        words = value.split()
        if not words:
            return value

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) <= width:
                current = candidate
                continue
            lines.append(current)
            current = word
        lines.append(current)
        return "\n".join(lines)

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
