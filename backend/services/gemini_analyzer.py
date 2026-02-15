"""
Gemini Analyzer Service using Google Gemini 1.5 Pro.
Analyzes video content to extract locations, activities, and vibes.
"""
import google.generativeai as genai
from pathlib import Path
import logging
from typing import Optional
import json

from backend.config import settings
from backend.models.schemas import GeminiAnalysisResult

logger = logging.getLogger(__name__)


class GeminiAnalyzerService:
    """Service for analyzing videos with Google Gemini."""
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Use Gemini 2.0 Flash (supports video)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
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

4. **City/Region**: What city or region is this video about?

Return your analysis as JSON with this structure:
{
  "city": "City Name",
  "locations": [
    {
      "name": "Location Name",
      "type": "Food|Art|Nature|Culture|Shopping|Nightlife",
      "description": "Why it's cool",
      "mentioned_time": "0:15" or null
    }
  ],
  "activities": ["activity1", "activity2"],
  "vibes": ["vibe1", "vibe2"],
  "confidence": "high|medium|low"
}

If the video is not travel-related, return: {"city": null, "locations": [], "activities": [], "vibes": [], "confidence": "low"}
"""
    
    async def analyze_video(self, video_path: str, video_title: str = "") -> GeminiAnalysisResult:
        """
        Analyze a video file using Gemini.
        
        Args:
            video_path: Path to downloaded video file
            video_title: Original video title (helps with context)
            
        Returns:
            GeminiAnalysisResult with extracted information
        """
        try:
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Upload video to Gemini
            logger.info(f"Uploading video to Gemini: {video_path}")
            video_file = genai.upload_file(path=video_path)
            
            # Wait for processing to complete
            import time
            while video_file.state.name == "PROCESSING":
                logger.debug("Waiting for video processing...")
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED":
                raise ValueError(f"Gemini failed to process video: {video_file.state}")
            
            # Create prompt with context
            full_prompt = self.analysis_prompt
            if video_title:
                full_prompt = f"Video title: '{video_title}'\n\n{full_prompt}"
            
            # Generate analysis
            logger.info(f"Analyzing video with Gemini...")
            response = self.model.generate_content([full_prompt, video_file])
            
            # Parse JSON response
            result_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()
            
            # Parse JSON
            try:
                data = json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Gemini response as JSON: {result_text[:200]}")
                # Return empty result
                data = {
                    "city": None,
                    "locations": [],
                    "activities": [],
                    "vibes": [],
                    "confidence": "low"
                }
            
            # Convert to GeminiAnalysisResult
            return GeminiAnalysisResult(
                locations=data.get("locations", []),
                activities=data.get("activities", []),
                vibes=data.get("vibes", []),
                metadata={
                    "city": data.get("city"),
                    "confidence": data.get("confidence", "low"),
                    "video_title": video_title
                }
            )
            
        except Exception as e:
            logger.error(f"Error analyzing video {video_path}: {e}")
            # Return empty result on error
            return GeminiAnalysisResult(
                locations=[],
                activities=[],
                vibes=[],
                metadata={"error": str(e), "video_title": video_title}
            )
    
    async def analyze_multiple_videos(
        self,
        video_data: list[dict]
    ) -> list[GeminiAnalysisResult]:
        """
        Analyze multiple videos.
        
        Args:
            video_data: List of dicts with 'file_path' and 'title' keys
            
        Returns:
            List of GeminiAnalysisResult objects
        """
        results = []
        for data in video_data:
            result = await self.analyze_video(
                data.get('file_path'),
                data.get('title', '')
            )
            results.append(result)
        
        return results


# Singleton instance
gemini_analyzer = GeminiAnalyzerService()
