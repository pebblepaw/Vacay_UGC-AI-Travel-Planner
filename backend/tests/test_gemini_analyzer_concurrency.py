import asyncio

import pytest

from backend.models.schemas import GeminiAnalysisResult
from backend.services.gemini_analyzer import GeminiAnalyzerService


@pytest.mark.asyncio
async def test_analyze_multiple_videos_runs_with_bounded_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GeminiAnalyzerService()
    active = 0
    max_active = 0

    async def fake_analyze(video_path: str, video_title: str = "", caption_text: str = "") -> GeminiAnalysisResult:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01 if video_path.endswith("1.mp4") else 0.02)
        active -= 1
        return GeminiAnalysisResult(
            locations=[{"name": video_title or video_path}],
            activities=[],
            vibes=[],
            metadata={"video_path": video_path},
        )

    monkeypatch.setattr(service, "analyze_video", fake_analyze)

    results = await service.analyze_multiple_videos(
        [
            {"file_path": "video1.mp4", "title": "one", "caption": ""},
            {"file_path": "video2.mp4", "title": "two", "caption": ""},
            {"file_path": "video3.mp4", "title": "three", "caption": ""},
        ]
    )

    assert [result.metadata["video_path"] for result in results] == [
        "video1.mp4",
        "video2.mp4",
        "video3.mp4",
    ]
    assert max_active == 2
