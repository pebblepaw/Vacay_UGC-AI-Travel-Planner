from unittest.mock import Mock

import pytest

from backend.services.video_downloader import VideoDownloaderService


def test_ydl_opts_cap_preview_quality_for_faster_demo_downloads():
    service = VideoDownloaderService()

    opts = service._get_ydl_opts("/tmp/demo.%(ext)s")

    assert "height<=540" in opts["format"]
    assert opts["format_sort"][0] == "res:540"


def test_detect_platform_treats_xhslink_as_rednote():
    service = VideoDownloaderService()

    platform = service._detect_platform("https://xhslink.com/a/demo123")

    assert platform == "rednote"


@pytest.mark.asyncio
async def test_download_video_uses_tiktok_photo_fallback(monkeypatch: pytest.MonkeyPatch):
    service = VideoDownloaderService()
    photo_url = "https://www.tiktok.com/@demo/photo/7606527006515203350"
    fallback_result = {
        "success": True,
        "url": photo_url,
        "file_path": "/tmp/photo.jpg",
        "preview_url": "http://127.0.0.1:8000/media/photo.jpg",
        "title": "Sydney photo post",
        "platform": "tiktok",
        "thumbnail": "http://example.com/photo.jpg",
        "description": "Sydney highlights",
    }

    monkeypatch.setattr(
        service,
        "_download_sync",
        Mock(
            return_value={
                "success": False,
                "url": photo_url,
                "error": f"Download failed: ERROR: Unsupported URL: {photo_url}",
                "title": "Unknown",
                "platform": "tiktok",
            }
        ),
    )
    fallback_mock = Mock(return_value=fallback_result)
    monkeypatch.setattr(service, "_download_tiktok_photo_post", fallback_mock)

    result = await service.download_video(photo_url)

    fallback_mock.assert_called_once_with(photo_url)
    assert result == fallback_result


@pytest.mark.asyncio
async def test_download_video_short_circuits_tiktok_photo_posts(monkeypatch: pytest.MonkeyPatch):
    service = VideoDownloaderService()
    photo_url = "https://www.tiktok.com/@demo/photo/7606527006515203350"
    fallback_result = {
        "success": True,
        "url": photo_url,
        "file_path": "/tmp/photo.jpg",
        "preview_url": "http://127.0.0.1:8000/media/photo.jpg",
        "title": "Sydney photo post",
        "platform": "tiktok",
        "thumbnail": "http://example.com/photo.jpg",
        "description": "Sydney highlights",
    }

    download_sync_mock = Mock(side_effect=AssertionError("yt-dlp should not run for photo posts"))
    monkeypatch.setattr(service, "_download_sync", download_sync_mock)
    fallback_mock = Mock(return_value=fallback_result)
    monkeypatch.setattr(service, "_download_tiktok_photo_post", fallback_mock)

    result = await service.download_video(photo_url)

    download_sync_mock.assert_not_called()
    fallback_mock.assert_called_once_with(photo_url)
    assert result == fallback_result


@pytest.mark.asyncio
async def test_download_video_uses_tiktok_html_fallback_for_video_pages(monkeypatch: pytest.MonkeyPatch):
    service = VideoDownloaderService()
    video_url = "https://www.tiktok.com/@demo/video/7508677073490185494"
    fallback_result = {
        "success": True,
        "url": video_url,
        "file_path": "/tmp/video.mp4",
        "preview_url": "http://127.0.0.1:8000/media/video.mp4",
        "title": "Sydney skyline reel",
        "platform": "tiktok",
        "thumbnail": "http://example.com/thumb.jpg",
        "description": "Sydney skyline reel",
    }

    monkeypatch.setattr(
        service,
        "_download_sync",
        Mock(
            return_value={
                "success": False,
                "url": video_url,
                "error": "Download failed: ERROR: [TikTok] Unable to extract universal data for rehydration",
                "title": "Unknown",
                "platform": "tiktok",
            }
        ),
    )
    fallback_mock = Mock(return_value=fallback_result)
    monkeypatch.setattr(service, "_download_tiktok_video_page", fallback_mock)

    result = await service.download_video(video_url)

    fallback_mock.assert_called_once_with(video_url)
    assert result == fallback_result


@pytest.mark.asyncio
async def test_download_video_uses_douyin_metadata_card_fallback_when_cookies_are_required(
    monkeypatch: pytest.MonkeyPatch,
):
    service = VideoDownloaderService()
    video_url = "https://www.douyin.com/video/7561228825859886371?source=Googlebot-sdc"
    fallback_result = {
        "success": True,
        "url": video_url,
        "file_path": "/tmp/douyin-card.png",
        "preview_url": "http://127.0.0.1:8000/media/douyin-card.png",
        "title": "One day #observatorypark #sydney - 抖音",
        "platform": "douyin",
        "thumbnail": None,
        "description": "Sydney observatory park day out",
    }

    monkeypatch.setattr(
        service,
        "_download_sync",
        Mock(
            return_value={
                "success": False,
                "url": video_url,
                "error": "Download failed: ERROR: Fresh cookies (not necessarily logged in) are needed",
                "title": "Unknown",
                "platform": "douyin",
            }
        ),
    )
    fallback_mock = Mock(return_value=fallback_result)
    monkeypatch.setattr(service, "_download_platform_metadata_card", fallback_mock)

    result = await service.download_video(video_url)

    fallback_mock.assert_called_once()
    assert fallback_mock.call_args.args == (
        video_url,
        "douyin",
        "Download failed: ERROR: Fresh cookies (not necessarily logged in) are needed",
    )
    assert result == fallback_result


@pytest.mark.asyncio
async def test_download_video_uses_rednote_metadata_card_fallback_when_formats_are_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    service = VideoDownloaderService()
    note_url = "https://www.xiaohongshu.com/discovery/item/69a3ccd4000000001a031563"
    fallback_result = {
        "success": True,
        "url": note_url,
        "file_path": "/tmp/rednote-card.png",
        "preview_url": "http://127.0.0.1:8000/media/rednote-card.png",
        "title": "Sydney hidden gems - 小红书",
        "platform": "rednote",
        "thumbnail": None,
        "description": "Sydney hidden gems weekend guide",
    }

    monkeypatch.setattr(
        service,
        "_download_sync",
        Mock(
            return_value={
                "success": False,
                "url": note_url,
                "error": "Download failed: ERROR: [generic] No video formats found!",
                "title": "Unknown",
                "platform": "rednote",
            }
        ),
    )
    fallback_mock = Mock(return_value=fallback_result)
    monkeypatch.setattr(service, "_download_platform_metadata_card", fallback_mock)

    result = await service.download_video(note_url)

    fallback_mock.assert_called_once()
    assert fallback_mock.call_args.args == (
        note_url,
        "rednote",
        "Download failed: ERROR: [generic] No video formats found!",
    )
    assert result == fallback_result
