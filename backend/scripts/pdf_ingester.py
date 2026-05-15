import io
import logging
from pathlib import Path
from typing import List, Dict
import pdfplumber

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from llm.service import get_llm_service

logger = logging.getLogger(__name__)

class PDFIngester:
    """Handles extraction of spiritual text from PDF files, supporting both text and OCR."""

    def __init__(self):
        self.llm_service = get_llm_service()

    async def process_pdf(self, file_path: Path) -> List[Dict]:
        """
        Process a PDF file and return a list of extracted verses/text blocks.
        """
        all_content = []
        logger.info(f"Processing PDF: {file_path.name}")

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {page_num + 1}/{len(pdf.pages)} of {file_path.name}")
                    
                    # 1. Try to extract text directly (for digital PDFs)
                    text = page.extract_text()
                    
                    if text and len(text.strip()) > 50:
                        # Digital text found
                        logger.info(f"Page {page_num + 1}: Extracted digital text ({len(text)} chars)")
                        all_content.append({
                            "page": page_num + 1,
                            "text": text,
                            "type": "text"
                        })
                    else:
                        # No or little text found, likely a scanned page - use OCR
                        logger.info(f"Page {page_num + 1}: No digital text, attempting OCR...")
                        
                        # Convert page to image
                        img = page.to_image(resolution=300).original
                        
                        # Convert PIL Image to bytes
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG')
                        img_bytes = img_byte_arr.getvalue()
                        
                        ocr_text = await self.llm_service.extract_text_from_image(img_bytes)
                        
                        if ocr_text:
                            logger.info(f"Page {page_num + 1}: OCR successful ({len(ocr_text)} chars)")
                            all_content.append({
                                "page": page_num + 1,
                                "text": ocr_text,
                                "type": "ocr"
                            })
                        else:
                            logger.warning(f"Page {page_num + 1}: OCR returned no text")

            return self._structure_content(all_content, file_path.stem)

        except Exception as e:
            logger.error(f"Error processing PDF {file_path.name}: {e}")
            return []

    def _structure_content(self, raw_pages: List[Dict], source_name: str) -> List[Dict]:
        """
        Convert raw page text into structured verse objects.
        This is a basic implementation that treats each page as a 'chapter' or block.
        Real implementation would need to parse verse markers in the text.
        """
        structured_verses = []
        import uuid

        for page_data in raw_pages:
            verse = {
                'id': str(uuid.uuid4()),
                'type': 'scripture',
                'scripture': self._infer_scripture(source_name),
                'source': source_name,
                'chapter': f"Page {page_data['page']}",
                'section': "",
                'verse_number': "1",
                'text': page_data['text'],
                'sanskrit': "", # Would need smarter parsing to separate
                'meaning': "",
                'transliteration': "",
                'language': 'en',
                'reference': f"{source_name} Page {page_data['page']}",
                'metadata': {
                    'page': page_data['page'],
                    'extraction_method': page_data['type']
                }
            }
            structured_verses.append(verse)

        return structured_verses

    def _infer_scripture(self, source: str) -> str:
        """Infer scripture name from source name (same logic as ingest_all_data)"""
        # (Simplified version of the logic in ingest_all_data.py)
        source_lower = source.lower()
        if 'gita' in source_lower:
            return 'Bhagavad Gita'
        if 'ramayana' in source_lower:
            return 'Ramayana'
        if 'mahabharata' in source_lower:
            return 'Mahabharata'
        return 'Sanatan Scriptures'
