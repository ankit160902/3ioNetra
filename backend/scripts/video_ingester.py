import os
import logging
from pathlib import Path
from typing import List, Dict
import uuid

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from llm.service import get_llm_service

logger = logging.getLogger(__name__)

class VideoIngester:
    """Handles extraction of spiritual wisdom from video files using Gemini Multimodal."""

    def __init__(self):
        self.llm_service = get_llm_service()

    async def process_video(self, file_path: Path) -> List[Dict]:
        """
        Process a video file and return a list of extracted wisdom blocks.
        """
        logger.info(f"Processing Video: {file_path.name}")

        try:
            # Gemini can analyze videos up to ~1 hour depending on the model limits
            # For longer videos, we might need to chunk them, but for now we process as a whole
            analysis_text = await self.llm_service.analyze_video(str(file_path))
            
            if not analysis_text:
                logger.warning(f"Video analysis returned no content for {file_path.name}")
                return []

            # Structure the analysis into chunks for RAG
            # For simplicity, we create one large block per video, or split by paragraph if it's very long
            return self._structure_content(analysis_text, file_path.stem)

        except Exception as e:
            logger.error(f"Error processing video {file_path.name}: {e}")
            return []

    def _structure_content(self, raw_json: str, source_name: str) -> List[Dict]:
        """
        Convert raw JSON analysis into structured micro-chunks.
        """
        import json
        try:
            data = json.loads(raw_json)
        except Exception as e:
            logger.error(f"Failed to parse video analysis JSON: {e}")
            return []

        structured_chunks = []
        overall_summary = data.get('overall_summary', '')
        takeaways = ", ".join(data.get('practical_takeaways', []))

        # 1. Create chunks for each segment (Micro-chunking)
        for i, segment in enumerate(data.get('segments', []), 1):
            start = segment.get('start_time', '00:00')
            end = segment.get('end_time', '00:00')
            transcription = segment.get('transcription', '')
            visuals = segment.get('visual_description', '')
            context = segment.get('spiritual_context', '')
            
            # Extract Shlokas for specialized field
            shlokas = segment.get('shlokas', [])
            sanskrit_text = "\n".join([s.get('original', '') for s in shlokas])
            meaning_text = "\n".join([s.get('meaning', '') for s in shlokas])

            # Build a rich descriptive block for RAG
            combined_text = f"""
            [VIDEO SEGMENT {start} - {end}]
            ACTION/VISUALS: {visuals}
            TRANSCRIPTION: {transcription}
            SPIRITUAL SIGNIFICANCE: {context}
            """.strip()

            chunk = {
                'id': str(uuid.uuid4()),
                'type': 'video_wisdom',
                'scripture': 'Video Satsang',
                'source': source_name,
                'chapter': f"{source_name} - {start}",
                'section': f"Segment {i}",
                'verse_number': str(i),
                'text': combined_text,
                'sanskrit': sanskrit_text,
                'meaning': meaning_text,
                'transliteration': "",
                'language': 'en',
                'reference': f"Video: {source_name} [{start}-{end}]",
                'metadata': {
                    'source_type': 'video',
                    'start_time': start,
                    'end_time': end,
                    'visual_context': visuals,
                    'overall_summary': overall_summary,
                    'takeaways': takeaways
                }
            }
            structured_chunks.append(chunk)

        # 2. Add an overall summary chunk if segments are few
        if not structured_chunks and overall_summary:
            summary_chunk = {
                'id': str(uuid.uuid4()),
                'type': 'video_wisdom',
                'scripture': 'Video Satsang',
                'source': source_name,
                'chapter': source_name,
                'section': "Overall Summary",
                'verse_number': "0",
                'text': f"OVERALL SUMMARY: {overall_summary}\n\nTAKEAWAYS: {takeaways}",
                'sanskrit': "",
                'meaning': "",
                'transliteration': "",
                'language': 'en',
                'reference': f"Video: {source_name} (Summary)",
                'metadata': {'source_type': 'video'}
            }
            structured_chunks.append(summary_chunk)

        return structured_chunks

    def _infer_scripture(self, source: str) -> str:
        """Helper to name the video resource appropriately"""
        return "Video Satsang / Spiritual Discourse"
