"""Gemini Analyzer Service using the google.genai SDK.

Analyzes video content to extract locations, activities, and vibes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import re
from typing import Any

from google import genai
from google.genai import types as genai_types

from backend.config import settings
from backend.llm import resolve_role_model
from backend.models.schemas import GeminiAnalysisResult

logger = logging.getLogger(__name__)


class GeminiAnalyzerService:
    """Service for analyzing videos with Google Gemini."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = resolve_role_model("video_analyzer", provider="gemini")
        self.generation_config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
        )

        self.analysis_prompt = """
Analyze this video and extract travel-related information. Focus on:

1. **Locations**: Extract specific places mentioned or shown (restaurants, landmarks, neighborhoods, etc.)
   For each location provide:
   - name: The name of the place
   - type: category (Food, Art, Nature, Culture, Shopping, Nightlife)
   - description: Why it's cool/worth visiting based on what's shown
   - mentioned_time: approximate timestamp if mentioned
   - priority: 'high' (must visit), 'normal' or 'low' (if skipped it's fine)
   - intensity: 'high' (active/hiking), 'normal' (walking), 'low' (relaxing)
   - visit_duration: estimated minutes (60, 90, 120) based on activity type

2. **Activities**: What activities are shown or suggested? (eating, sightseeing, shopping, etc.)

3. **Vibes**: What's the mood/vibe? (cozy, energetic, hidden gem, trendy, authentic, etc.)

4. **Place scope**: What city, region, and country is this video about?

Return your analysis as JSON with this structure:
{
  "city": "City Name",
  "country": "Country Name",
  "scope_type": "city|region|country",
  "locations": [
    {
      "name": "Location Name",
      "type": "Food|Art|Nature|Culture|Shopping|Nightlife",
      "description": "Why it's cool",
      "mentioned_time": "0:15" or null,
      "priority": "high",
      "intensity": "normal",
      "visit_duration": 60
    }
  ],
  "activities": ["activity1", "activity2"],
  "vibes": ["vibe1", "vibe2"],
  "confidence": "high|medium|low",
  "scope_confidence": "high|medium|low"
}

If the video is not travel-related, return: {"city": null, "country": null, "scope_type": "city", "locations": [], "activities": [], "vibes": [], "confidence": "low", "scope_confidence": "low"}
"""

    @staticmethod
    def _file_state_name(file_obj: Any) -> str:
        state = getattr(file_obj, "state", None)
        if state is None:
            return ""
        return getattr(state, "name", str(state))

    async def _wait_for_uploaded_file(self, file_obj: Any) -> Any:
        state_name = self._file_state_name(file_obj)
        while state_name == "PROCESSING":
            logger.debug("Waiting for Gemini video processing...")
            await asyncio.sleep(2)
            file_name = getattr(file_obj, "name", None)
            if not file_name:
                return file_obj
            file_obj = self.client.files.get(name=file_name)
            state_name = self._file_state_name(file_obj)

        if state_name == "FAILED":
            error = getattr(file_obj, "error", None)
            raise ValueError(f"Gemini failed to process video: {error or state_name}")

        return file_obj

    @staticmethod
    def _extract_json_data(result_text: str) -> dict[str, Any] | None:
        data = None

        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            pass

        if data is None:
            fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", result_text, re.DOTALL)
            if fence_match:
                try:
                    data = json.loads(fence_match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if data is None:
            brace_start = result_text.find("{")
            brace_end = result_text.rfind("}")
            if brace_start != -1 and brace_end > brace_start:
                try:
                    data = json.loads(result_text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass

        return data

    async def analyze_video(self, video_path: str, video_title: str = "") -> GeminiAnalysisResult:
        """Analyze one downloaded video file with Gemini."""

        uploaded_file: Any = None
        try:
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            logger.info("Uploading video to Gemini: %s", video_path)
            uploaded_file = self.client.files.upload(file=video_path)
            uploaded_file = await self._wait_for_uploaded_file(uploaded_file)

            full_prompt = self.analysis_prompt
            if video_title:
                full_prompt = f"Video title: '{video_title}'\n\n{full_prompt}"

            logger.info("Analyzing video with Gemini...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[full_prompt, uploaded_file],
                config=self.generation_config,
            )

            result_text = (getattr(response, "text", "") or "").strip()
            data = self._extract_json_data(result_text)

            if data is None:
                logger.warning("Failed to parse Gemini response as JSON: %s", result_text[:200])
                data = {
                    "city": None,
                    "locations": [],
                    "activities": [],
                    "vibes": [],
                    "confidence": "low",
                }

            return GeminiAnalysisResult(
                locations=data.get("locations", []),
                activities=data.get("activities", []),
                vibes=data.get("vibes", []),
                metadata={
                    "city": data.get("city"),
                    "country": data.get("country"),
                    "scope_type": data.get("scope_type", "city"),
                    "confidence": data.get("confidence", "low"),
                    "scope_confidence": data.get("scope_confidence", data.get("confidence", "low")),
                    "video_title": video_title,
                },
            )

        except Exception as e:
            logger.error(f"Error analyzing video {video_path}: {e}")
            return GeminiAnalysisResult(
                locations=[],
                activities=[],
                vibes=[],
                metadata={"error": str(e), "video_title": video_title},
            )
        finally:
            file_name = getattr(uploaded_file, "name", None)
            if file_name:
                try:
                    self.client.files.delete(name=file_name)
                except Exception:
                    logger.debug("Failed to delete Gemini upload %s", file_name, exc_info=True)

    async def analyze_multiple_videos(
        self,
        video_data: list[dict],
    ) -> list[GeminiAnalysisResult]:
        """Analyze multiple downloaded videos serially."""

        results = []
        for data in video_data:
            result = await self.analyze_video(
                data.get("file_path"),
                data.get("title", ""),
            )
            results.append(result)

        return results


gemini_analyzer = GeminiAnalyzerService()
