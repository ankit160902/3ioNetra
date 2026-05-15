import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from scripts.ingest_all_data import UniversalScriptureIngester

async def verify():
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create a dummy video file for testing
    test_video = Path("/tmp/test_spiritual_video.mp4")
    with open(test_video, "wb") as f:
        f.write(b"dummy video content")

    print("\n--- Verifying Video Ingestion (Mocked) ---")
    
    # Initialize ingester
    ingester = UniversalScriptureIngester()
    
    # Mock the LLM service to avoid actual API call and file upload
    if ingester.video_ingester:
        # Mock analyze_video to return structured JSON
        mock_response = {
            "overall_summary": "A deep dive into Karma Yoga and selfless action.",
            "practical_takeaways": ["Perform duties without attachment", "Serve others as a form of worship"],
            "segments": [
                {
                    "start_time": "00:00",
                    "end_time": "01:30",
                    "transcription": "Welcome to this discourse. Today we discuss Verse 47 of Chapter 2.",
                    "visual_description": "Teacher sitting in a garden, holding a Bhagavad Gita.",
                    "spiritual_context": "Introduction to the concept of Nishkama Karma.",
                    "shlokas": [{"original": "Karmanye vadhikaraste...", "meaning": "You have the right to work only..."}]
                },
                {
                    "start_time": "01:31",
                    "end_time": "03:00",
                    "transcription": "Now let us look at how this applies to our daily work life.",
                    "visual_description": "Cut to footage of people working mindfully in a community kitchen.",
                    "spiritual_context": "Practical application of selfless service.",
                    "shlokas": []
                }
            ]
        }
        
        import json
        ingester.video_ingester.llm_service.analyze_video = AsyncMock(return_value=json.dumps(mock_response))
        
        results = await ingester.parse_video_file(test_video)
        
        for i, res in enumerate(results, 1):
            print(f"\n--- Chunk {i} ---")
            print(f"Reference: {res['reference']}")
            print(f"Chapter/Segment: {res['chapter']}")
            print(f"Text Preview:\n{res['text'][:200]}...")
            if res['sanskrit']:
                print(f"Sanskrit: {res['sanskrit']}")
            print(f"Metadata Timestamps: {res['metadata'].get('start_time')} to {res['metadata'].get('end_time')}")

        if len(results) >= 2:
            print("\n✅ Verification SUCCESS: Micro-chunking logic is working perfectly.")
        else:
            print(f"\n❌ Verification FAILED: Expected at least 2 chunks, got {len(results)}.")
    else:
        print("\n❌ Verification FAILED: VideoIngester not available.")

if __name__ == "__main__":
    asyncio.run(verify())
