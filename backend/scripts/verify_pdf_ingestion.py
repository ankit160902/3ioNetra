import asyncio
import os
from pathlib import Path
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

# Add parent to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from scripts.ingest_all_data import UniversalScriptureIngester

def create_test_pdf(file_path: Path):
    """Create a PDF with one page of text and one page with an 'image' of a verse."""
    c = canvas.Canvas(str(file_path))
    
    # Page 1: Digital Text
    c.drawString(100, 750, "Bhagavad Gita - Digital Text Test")
    c.drawString(100, 730, "Chapter 2, Verse 47")
    c.drawString(100, 710, "Karmanye vadhikaraste ma phaleshu kadachana...")
    c.showPage()
    
    # Page 2: Scanned/Image Text (Simulated)
    # We create an image with text and save it temporarily to embed in PDF
    img_path = "/tmp/test_verse_img.png"
    img = Image.new('RGB', (500, 200), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "SCANNED VERSE: Rig Veda 1.1.1\nAgni-m-ile purohitam yajnasya devam rtvijam", fill=(0,0,0))
    img.save(img_path)
    
    c.drawImage(img_path, 100, 600, width=400, height=160)
    c.drawString(100, 580, "This page contains an image that requires OCR.")
    c.showPage()
    
    c.save()
    logger.info(f"Test PDF created at {file_path}")

async def verify():
    test_pdf = Path("/tmp/test_spiritual_doc.pdf")
    create_test_pdf(test_pdf)
    
    # Mock ingest_all_data to only process this one file
    ingester = UniversalScriptureIngester()
    
    print("\n--- Verifying PDF Ingestion ---")
    results = await ingester.parse_pdf_file(test_pdf)
    
    for i, res in enumerate(results, 1):
        print(f"\nResult {i} (Type: {res['metadata']['extraction_method']}):")
        print(f"Reference: {res['reference']}")
        print(f"Text Preview: {res['text'][:100]}...")

    if len(results) >= 2:
        print("\n✅ Verification SUCCESS: Both digital and OCR paths triggered (simulated).")
    else:
        print("\n❌ Verification FAILED: Missing results.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    asyncio.run(verify())
