import sys
import json
import csv
import logging
import re
import uuid
from pathlib import Path
from typing import List, Dict
import numpy as np
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from config import settings  # noqa: E402

# Try to import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")


class UniversalScriptureIngester:
    """Ingest and process all spiritual text datasets"""

    def __init__(self):
        self.raw_data_dir = Path(__file__).parent.parent / "data" / "raw"
        self.processed_data_dir = Path(__file__).parent.parent / "data" / "processed"
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize embedding model if available
        self.embedding_model = None
        if EMBEDDING_AVAILABLE:
            try:
                logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
                self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")

        # PDF Ingester
        try:
            from scripts.pdf_ingester import PDFIngester
            self.pdf_ingester = PDFIngester()
            logger.info("PDF Ingester initialized")
        except ImportError:
            self.pdf_ingester = None
            logger.warning("PDF Ingester or its dependencies not available")

        # Video Ingester
        try:
            from scripts.video_ingester import VideoIngester
            self.video_ingester = VideoIngester()
            logger.info("Video Ingester initialized")
        except ImportError:
            self.video_ingester = None
            logger.warning("Video Ingester or its dependencies not available")

    def find_dataset_files(self) -> List[Path]:
        """Find all dataset files in raw data directory"""
        files = []

        if not self.raw_data_dir.exists():
            logger.error(f"Raw data directory not found: {self.raw_data_dir}")
            return files

        # Look for CSV, JSON, and PDF files
        csv_files = list(self.raw_data_dir.glob("*.csv"))
        json_files = list(self.raw_data_dir.glob("*.json"))
        pdf_files = list(self.raw_data_dir.glob("*.pdf"))
        video_files = []
        for ext in ['*.mp4', '*.mkv', '*.mov', '*.avi', '*.webm']:
            video_files.extend(list(self.raw_data_dir.glob(ext)))

        files.extend(csv_files)
        files.extend(json_files)
        files.extend(pdf_files)
        files.extend(video_files)

        logger.info(f"Found {len(files)} data files")
        return files

    def parse_csv_file(self, file_path: Path) -> List[Dict]:
        """Parse CSV file and extract verses"""
        verses = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                limit = 10000
                if "gita" in file_path.name.lower():
                    limit = 50000 # Ensure all Gita verses are included

                for idx, row in enumerate(reader):
                    if idx > limit:
                        break

                    verse = self._extract_verse_from_csv_row(row, file_path.stem)
                    if verse:
                        verses.append(verse)

            logger.info(f"✓ Parsed {len(verses)} verses from {file_path.name}")

        except Exception as e:
            logger.error(f"✗ Error parsing CSV {file_path.name}: {e}")

        return verses

    def parse_json_file(self, file_path: Path) -> List[Dict]:
        """Parse JSON file and extract verses"""
        # Handle temple data separately
        if "temple" in file_path.name.lower():
            return self.parse_temples_file(file_path)

        verses = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Detect Yoga Sutras pattern: list of lists of dicts with 'shloka' key
            if (isinstance(data, list) and len(data) > 0 and
                    isinstance(data[0], list) and len(data[0]) > 0 and
                    isinstance(data[0][0], dict) and 'shloka' in data[0][0]):
                verses = self._parse_yoga_sutras(data, file_path.stem)
            else:
                def extract_from_any(obj):
                    extracted = []
                    if isinstance(obj, list):
                        for item in obj:
                            extracted.extend(extract_from_any(item))
                    elif isinstance(obj, dict):
                        verse = self._extract_verse_from_dict(obj, file_path.stem)
                        if verse:
                            extracted.append(verse)
                        else:
                            # Check nested lists in dict values
                            for val in obj.values():
                                if isinstance(val, (list, dict)):
                                    extracted.extend(extract_from_any(val))
                    return extracted

                verses = extract_from_any(data)
            
            # Limit for performance
            if len(verses) > 10000 and "gita" not in file_path.name.lower():
                verses = verses[:10000]

            if verses:
                logger.info(f"✓ Parsed {len(verses)} verses from {file_path.name}")
            else:
                logger.warning(f"⚠ No verses extracted from {file_path.name}")

        except Exception as e:
            logger.error(f"✗ Error parsing JSON {file_path.name}: {e}")

        return verses

    async def parse_pdf_file(self, file_path: Path) -> List[Dict]:
        """Parse PDF file using PDFIngester"""
        if not self.pdf_ingester:
            logger.error(f"Cannot parse PDF {file_path.name}: Ingester not available")
            return []
            
        try:
            return await self.pdf_ingester.process_pdf(file_path)
        except Exception as e:
            logger.error(f"✗ Error parsing PDF {file_path.name}: {e}")
            return []

    async def parse_video_file(self, file_path: Path) -> List[Dict]:
        """Parse Video file using VideoIngester"""
        if not self.video_ingester:
            logger.error(f"Cannot parse Video {file_path.name}: Ingester not available")
            return []
            
        try:
            return await self.video_ingester.process_video(file_path)
        except Exception as e:
            logger.error(f"✗ Error parsing Video {file_path.name}: {e}")
            return []

    def strip_markdown(self, text: str) -> str:
        """Simple markdown stripper"""
        if not text:
            return ""
        # Remove bold/italic
        text = re.sub(r'\*\*?(.*?)\*\*?', r'\1', text)
        # Remove headers
        text = re.sub(r'#+\s*(.*?)\s*#*', r'\1', text)
        # Remove list markers
        text = re.sub(r'^\s*[\-\*\+]\s+', '', text, flags=re.MULTILINE)
        # Remove numbered list markers
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # Remove links [text](url) -> text
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        # Remove images ![]()
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # Remove backticks
        text = text.replace('`', '')
        # Clean extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def parse_temples_file(self, file_path: Path) -> List[Dict]:
        """Parse Hindu Temples JSON file (handles various formats)"""
        verses = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Case 1: phpMyAdmin export format (list of objects)
            if isinstance(data, list):
                # Check if it's a flat list of temples (New Schema)
                if len(data) > 0 and isinstance(data[0], dict) and 'name' in data[0] and 'type' not in data[0]:
                     for temple in data:
                        verse = self._extract_temple_as_verse(temple, temple.get('state', 'Unknown'))
                        if verse:
                            verses.append(verse)
                else:
                    # Legacy PHPMyAdmin format
                    for obj in data:
                        if isinstance(obj, dict) and obj.get('type') == 'table' and obj.get('name') == 'temples':
                            temple_list = obj.get('data', [])
                            for temple in temple_list:
                                verse = self._extract_temple_as_verse(temple, temple.get('state', 'Unknown'))
                                if verse:
                                    verses.append(verse)
                
            # Case 2: Dictionary format (state -> list of temples)
            elif isinstance(data, dict):
                for state, temples in data.items():
                    if not isinstance(temples, list):
                        continue
                    for temple in temples:
                        verse = self._extract_temple_as_verse(temple, state)
                        if verse:
                            verses.append(verse)
            
            logger.info(f"✓ Parsed {len(verses)} temples from {file_path.name}")
        except Exception as e:
            logger.error(f"✗ Error parsing Temples JSON {file_path.name}: {e}")
        return verses

    def _extract_temple_as_verse(self, temple: Dict, state: str) -> Dict:
        """Convert temple info to a verse-like structure for RAG with rich profiling"""
        name = temple.get('name')
        if not name:
            return None
        
        # Combine all info fields for searchable text - support both old and new formats
        text_parts = []
        
        # Core Info
        if name:
            text_parts.append(f"Temple Name: {name}")
        if state:
            text_parts.append(f"State: {state}")
        
        # Merge fields from both formats
        location = temple.get('Location') or temple.get('full_address') or temple.get('city')
        if location:
            text_parts.append(f"Location: {location}")
        
        deity = temple.get('Main deity')
        if deity:
            text_parts.append(f"Main Deity: {deity}")
        
        other_deities = temple.get('Other deities')
        if other_deities:
            text_parts.append(f"Other Deities: {other_deities}")
        
        # Descriptions & History
        # Format 1 keys: info, Significance, History, Detailed History, story, Architecture, ...
        # Format 2 keys: history, significance, description, editorial_summary, ...
        
        summary = temple.get('info') or temple.get('description') or temple.get('editorial_summary')
        if summary:
            text_parts.append(f"Summary: {summary}")
        
        significance = temple.get('Significance') or temple.get('significance')
        if significance:
            text_parts.append(f"Significance: {significance}")
        
        history = temple.get('History') or temple.get('Detailed History') or temple.get('detailed_history') or temple.get('history')
        if history:
            text_parts.append(f"History: {history}")
        
        story = temple.get('story')
        if story:
            text_parts.append(f"Spiritual Story: {story}")
        
        architecture = temple.get('Architecture') or temple.get('Detailed Architecture') or temple.get('Key features of the architecture')
        if architecture:
            text_parts.append(f"Architecture: {architecture}")
        
        # Scriptural
        scriptural = temple.get('mention_in_scripture') or temple.get('Scriptural References')
        if scriptural:
            text_parts.append(f"Scriptural References: {scriptural}")
        
        # Visiting & Logistics
        guide = temple.get('visiting_guide') or temple.get('transport_info')
        if guide:
            text_parts.append(f"Visiting Info: {guide}")
        
        timings = temple.get('Timings') or f"{temple.get('opening_time', '')} to {temple.get('closing_time', '')}".strip()
        if timings and timings != "to":
            text_parts.append(f"Timings: {timings}")

        # Combine and CLEAN markdown
        raw_combined = "\n\n".join(text_parts)
        combined_text = self.strip_markdown(raw_combined)
        
        if not combined_text:
            combined_text = f"Information about {name} temple in {state}."

        # Create a standardized verse-like object
        verse = {
            'id': str(uuid.uuid4()),
            'type': 'temple',
            'scripture': 'Hindu Temples',
            'source': 'hindu_temples',
            'chapter': state,
            'verse': name,
            'text': combined_text,
            'reference': f"Temple: {name} ({state})",
            'language': 'en',
            'topic': 'Temples and Pilgrimage',
            'metadata': temple  # Store the FULL rich temple object
        }
        return verse

    def _extract_verse_from_csv_row(self, row: Dict, source: str) -> Dict:
        """Extract verse from CSV row"""
        verse = {}

        # Map common column names (case-insensitive)
        row_lower = {k.lower(): v for k, v in row.items() if v}

        # Extract fields
        verse['chapter'] = row_lower.get('book') or row_lower.get('mandala') or row_lower.get('kaanda') or row_lower.get('chapter') or row_lower.get('adhyaya')
        verse['section'] = row_lower.get('section') or row_lower.get('sarg') or row_lower.get('sarga') or (row_lower.get('chapter') if 'kaanda' in row_lower or 'book' in row_lower else None)
        verse['verse_number'] = row_lower.get('verse') or row_lower.get('shloka_number') or row_lower.get('sukta')
        verse['verse'] = row_lower.get('shloka')  # Keep shloka for sanskrit field
        
        # Priority for English content
        verse['text'] = row_lower.get('engmeaning') or row_lower.get('translation') or row_lower.get('english') or row_lower.get('text')
        
        # Original Sanskrit/Hindi
        verse['sanskrit'] = row_lower.get('shloka_text') or row_lower.get('original') or row_lower.get('sanskrit') or row_lower.get('shloka')
        
        verse['transliteration'] = row_lower.get('transliteration') or row_lower.get('iast')
        
        # Add meaning/explanation
        verse['meaning'] = row_lower.get('meaning') or row_lower.get('explanation') or row_lower.get('wordmeaning') or row_lower.get('hinmeaning') or row_lower.get('meditation_guidance')
        verse['hindi'] = row_lower.get('hinmeaning') or row_lower.get('hindi')

        # Handle Meditation Miniset specially if its columns are present
        if 'meditation_guidance' in row_lower:
            verse['text'] = f"Context: {row_lower.get('context', 'N/A')}\nGuidance: {row_lower.get('meditation_guidance')}\nTechniques: {row_lower.get('suggested_techniques', 'N/A')}"
            verse['chapter'] = row_lower.get('meditation_style', 'General')
            verse['verse'] = row_lower.get('user_experience_level', 'All levels')
            verse['verse_number'] = row_lower.get('user_experience_level', 'All levels')
            verse['topic'] = 'Meditation'
            verse['type'] = 'procedural'

        # Only return if we have essential fields
        if (verse.get('chapter') and (verse.get('verse_number') or verse.get('verse')) and verse.get('text')) or 'meditation_guidance' in row_lower:
            verse['scripture'] = self._infer_scripture(source)
            verse['source'] = source

            # Construct more granular reference using verse_number (not shloka text)
            ref = f"{verse['scripture']} {verse['chapter']}"
            if verse.get('section') and str(verse['section']) != str(verse['chapter']):
                ref += f" {verse['section']}"
            ref += f".{verse.get('verse_number', verse.get('verse', ''))}"
            verse['reference'] = ref
            
            verse['language'] = 'en'
            verse['topic'] = self._infer_topic(verse)

            return {k: v for k, v in verse.items() if v}  # Remove None values

        return None

    def _extract_verse_from_dict(self, item: Dict, source: str) -> Dict:
        """Extract verse from dictionary"""
        if not isinstance(item, dict):
            return None

        verse = {}
        item_lower = {k.lower(): v for k, v in item.items() if v is not None}

        # Extract fields with type checking
        def safe_get(key_list):
            for key in key_list:
                if key in item_lower:
                    val = item_lower[key]
                    if isinstance(val, (str, int)):
                        return str(val).strip() if isinstance(val, str) else str(val)
            return None

        # Try to get chapter/section/verse with more candidates
        verse['chapter'] = safe_get(['book', 'mandala', 'kaanda', 'chapter', 'adhyaya', 'theme', 'veda', 'samhita']) or source
        verse['section'] = safe_get(['section', 'sarg', 'sarga', 'chapter', 'adhyaya'])
        verse['verse'] = safe_get(['shloka', 'verse', 'sukta', 'shloka_number', 'verse_number', 'verse_id', 'id', 'text']) or '1'
        verse['text'] = safe_get(['text', 'translation', 'english', 'meaning', 'content', 'meditation'])
        verse['sanskrit'] = safe_get(['shloka_text', 'sanskrit', 'original', 'devanagari', 'shloka'])
        verse['transliteration'] = safe_get(['transliteration', 'iast', 'romanized', 'transliteraion'])

        # Fix section if it's the same as chapter
        if verse.get('section') == verse.get('chapter'):
            # Only if we have another candidate
            if 'adhyaya' in item_lower and verse['chapter'] != item_lower['adhyaya']:
                verse['section'] = item_lower['adhyaya']
            elif 'chapter' in item_lower and verse['chapter'] != item_lower['chapter']:
                verse['section'] = item_lower['chapter']
            else:
                 # Check if we should null it out to avoid redundancy in reference
                 pass

        # Essential field check - ensure at least some text and an identifier
        if (verse.get('chapter') or source) and verse.get('text'):
            # Standardized Verse Output
            final_verse = {
                'id': str(uuid.uuid4()),
                'type': item.get('type', 'procedural' if 'meditation' in source.lower() else 'scripture'),
                'scripture': self._infer_scripture(source),
                'source': source,
                'chapter': verse.get('chapter'),
                'section': verse.get('section', ''),
                'verse_number': verse.get('verse'),
                'text': verse.get('text'),
                'sanskrit': verse.get('sanskrit', ''),
                'meaning': verse.get('meaning', ''),
                'transliteration': verse.get('transliteration', ''),
                'language': 'en',
                'embedding': [] # Placeholder
            }
            
            # Construct more granular reference
            ref = f"{final_verse['scripture']} {final_verse['chapter']}"
            if final_verse['section'] and str(final_verse['section']) != str(final_verse['chapter']):
                ref += f" {final_verse['section']}"
            ref += f".{final_verse['verse_number']}"
            final_verse['reference'] = ref
            
            final_verse['topic'] = self._infer_topic(final_verse)

            return final_verse

        return None

    def _parse_yoga_sutras(self, data: list, source: str) -> List[Dict]:
        """Parse Yoga Sutras JSON: list of 4 padas, each a list of sutra dicts."""
        verses = []
        for pada_idx, pada in enumerate(data):
            if not isinstance(pada, list):
                continue
            pada_num = pada_idx + 1
            for sutra_idx, sutra in enumerate(pada):
                if not isinstance(sutra, dict):
                    continue
                sutra_num = sutra_idx + 1
                reference = f"Patanjali Yoga Sutras {pada_num}.{sutra_num}"

                # meaning field has English, shloka has Sanskrit, words has word-by-word
                text = sutra.get('meaning') or sutra.get('words') or ''
                sanskrit = sutra.get('shloka') or ''
                meaning = sutra.get('words') or ''

                verse = {
                    'id': str(uuid.uuid4()),
                    'type': 'scripture',
                    'scripture': 'Patanjali Yoga Sutras',
                    'source': source,
                    'chapter': str(pada_num),
                    'section': '',
                    'verse_number': str(sutra_num),
                    'text': text,
                    'sanskrit': sanskrit,
                    'meaning': meaning,
                    'transliteration': '',
                    'language': 'en',
                    'reference': reference,
                    'embedding': [],
                }
                verse['topic'] = self._infer_topic(verse)
                verses.append(verse)

        logger.info(f"Parsed {len(verses)} sutras from Yoga Sutras ({len(data)} padas)")
        return verses

    def _infer_scripture(self, source: str) -> str:
        """Infer scripture name from filename"""
        source_lower = source.lower()

        if 'bhagavad' in source_lower or 'bhagwad' in source_lower or 'gita' in source_lower:
            return 'Bhagavad Gita'
        elif 'mahabharata' in source_lower:
            return 'Mahabharata'
        elif any(k in source_lower for k in ['ramayana', 'balakanda', 'ayodhya', 'aranya', 'kishkindha', 'sundara', 'yudhha', 'uttara']):
            return 'Ramayana'
        elif 'rigveda' in source_lower:
            return 'Rig Veda'
        elif 'atharvaveda' in source_lower:
            return 'Atharva Veda'
        elif 'yajurveda' in source_lower or 'vajasneyi' in source_lower:
            return 'Yajur Veda'
        elif 'vedas' in source_lower:
            return 'Vedas'
        elif 'temples' in source_lower:
            return 'Hindu Temples'
        elif 'yoga_sutras' in source_lower or 'yoga' in source_lower:
            return 'Patanjali Yoga Sutras'
        elif 'charaka_samhita' in source_lower:
            return 'Charaka Samhita (Ayurveda)'
        elif 'meditation' in source_lower:
            return 'Meditation and Mindfulness'
        elif 'panchanga' in source_lower or 'panchang' in source_lower:
            return 'Panchang'
        else:
            return 'Sanatan Scriptures'

    # Scripture+chapter fallback mapping for topic inference
    _SCRIPTURE_CHAPTER_DEFAULTS = {
        ('Ramayana', 'balakanda'): 'Dharma',
        ('Ramayana', 'ayodhyakanda'): 'Dharma',
        ('Ramayana', 'aranyakanda'): 'Dharma',
        ('Ramayana', 'kishkindhakanda'): 'Bhakti Yoga',
        ('Ramayana', 'sundarakanda'): 'Bhakti Yoga',
        ('Ramayana', 'yudhhakanda'): 'War',
        ('Ramayana', 'uttarakanda'): 'Dharma',
        ('Mahabharata', '1'): 'Dharma',
        ('Mahabharata', '2'): 'Dharma',
        ('Mahabharata', '3'): 'Dharma',
        ('Mahabharata', '5'): 'Dharma',
        ('Mahabharata', '6'): 'War',
        ('Mahabharata', '12'): 'Dharma',
        ('Mahabharata', '13'): 'Dharma',
    }

    def _infer_topic(self, verse: Dict) -> str:
        """Infer topic from verse content using regex for word boundaries, with Sanskrit keyword support"""
        # If topic was already set (e.g., meditation), preserve it
        if verse.get('topic') and verse['topic'] != 'Spiritual Wisdom':
            return verse['topic']

        text = ' '.join([str(verse.get(f, '')) for f in ['text', 'meaning', 'sanskrit'] if verse.get(f)]).lower()

        topics = {
            'Karma Yoga': ['action', 'duty', 'work', 'karma', 'perform', 'karm', 'कर्म', 'कर्तव्य', 'कर्मण'],
            'Bhakti Yoga': ['devotion', 'love', 'surrender', 'worship', 'bhakti', 'prem', 'भक्ति', 'प्रेम', 'पूजा', 'भगवान'],
            'Jnana Yoga': ['knowledge', 'wisdom', 'understand', 'jnana', 'learning', 'gyan', 'ज्ञान', 'विद्या', 'बुद्धि'],
            'Mind Control': ['mind', 'control', 'meditation', 'focus', 'discipline', 'mana', 'मन', 'चित्त', 'ध्यान', 'एकाग्र'],
            'Soul': ['soul', 'atman', 'self', 'eternal', 'immortal', 'aatma', 'आत्मा', 'आत्मन'],
            'Equanimity': ['equal', 'balance', 'neutral', 'steady', 'sama', 'equanimity', 'सम', 'समत्व'],
            'Fear': ['fear', 'afraid', 'courage', 'fearless', 'bhaya', 'भय', 'निर्भय'],
            'Death': ['death', 'mortality', 'rebirth', 'reincarnation', 'mrutyu', 'मृत्यु', 'मरण', 'पुनर्जन्म'],
            'Liberation': ['liberation', 'moksha', 'freedom', 'enlightenment', 'mukt', 'मोक्ष', 'मुक्ति', 'निर्वाण'],
            'Dharma': ['dharma', 'righteousness', 'duty', 'moral', 'dharm', 'धर्म', 'न्याय', 'सत्य'],
            'Truth': ['truth', 'satya', 'honest', 'real', 'सत्य'],
            'Wealth': ['wealth', 'money', 'prosperity', 'success', 'धन', 'सम्पत्ति'],
            'Love': ['love', 'affection', 'compassion', 'prem', 'sneh', 'प्रेम', 'स्नेह', 'करुणा'],
            'War': ['war', 'battle', 'fight', 'yuddh', 'yudh', 'युद्ध', 'संग्राम', 'रण'],
            'Health & Ayurveda': ['health', 'disease', 'medicine', 'ayurveda', 'dosha', 'vata', 'pitta', 'kapha', 'herb', 'cure', 'healing', 'आयुर्वेद', 'रोग', 'औषधि'],
            'Yoga & Meditation': ['yoga', 'asana', 'meditation', 'breath', 'pranayama', 'dhyana', 'mindfulness', 'concentration', 'योग', 'आसन', 'प्राणायाम'],
        }

        for topic, keywords in topics.items():
            pattern = r'(' + '|'.join(map(re.escape, keywords)) + r')'
            if re.search(pattern, text):
                return topic

        # Scripture+chapter fallback when keyword matching fails
        scripture = verse.get('scripture', '')
        chapter = str(verse.get('chapter', '')).lower()
        for (scr, ch), topic in self._SCRIPTURE_CHAPTER_DEFAULTS.items():
            if scr in scripture and ch in chapter:
                return topic

        return 'Spiritual Wisdom'

    def _needs_translation(self, verse: Dict) -> bool:
        """Check if a verse needs translation (Sanskrit-only, no English content)."""
        # Already has English content
        if verse.get('text') and not self._is_primarily_devanagari(verse['text']):
            return False
        if verse.get('meaning') and not self._is_primarily_devanagari(verse['meaning']):
            return False
        # Has Sanskrit content that could be translated
        sanskrit = verse.get('sanskrit') or verse.get('text') or ''
        return bool(sanskrit.strip()) and self._is_primarily_devanagari(sanskrit)

    def _is_primarily_devanagari(self, text: str) -> bool:
        """Check if >50% of non-whitespace chars are Devanagari (Unicode 0900-097F)."""
        if not text:
            return False
        chars = [c for c in text if not c.isspace()]
        if not chars:
            return False
        devanagari = sum(1 for c in chars if '\u0900' <= c <= '\u097F')
        return devanagari / len(chars) > 0.5

    async def _batch_translate_verses(self, verses: List[Dict]):
        """Translate Sanskrit-only verses to English using Gemini Flash in batches."""
        try:
            from google import genai
        except ImportError:
            logger.warning("google-genai not available, skipping translation")
            return

        checkpoint_path = self.processed_data_dir / "translation_checkpoint.json"

        # Load checkpoint if exists
        translated_refs = set()
        if checkpoint_path.exists():
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                translated_refs = set(checkpoint.get('translated_refs', []))
                logger.info(f"Resuming translation: {len(translated_refs)} already done")
            except Exception:
                pass

        # Filter out already-translated
        remaining = [v for v in verses if v.get('reference') not in translated_refs]
        if not remaining:
            logger.info("All verses already translated (checkpoint)")
            return

        # Priority tiers
        def get_tier(v):
            scripture = (v.get('scripture') or '').lower()
            chapter = str(v.get('chapter') or '').lower()
            if 'atharva veda' in scripture:
                return 1
            if 'rig veda' in scripture and any(m in chapter for m in ['7', '10']):
                return 1
            if 'ramayana' in scripture and any(k in chapter for k in ['balakanda', 'sundarakanda', 'yudhhakanda']):
                return 1
            if 'mahabharata' in scripture and chapter in ('1', '6'):
                return 1
            if 'ramayana' in scripture:
                return 2
            if 'rig veda' in scripture:
                return 2
            if 'mahabharata' in scripture and chapter in ('3', '5', '12', '13'):
                return 2
            return 3

        remaining.sort(key=get_tier)

        # Initialize Gemini client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        batch_size = 50
        total_translated = 0
        backoff = 4  # seconds between batches

        logger.info(f"Translating {len(remaining)} verses in batches of {batch_size}...")

        for batch_start in range(0, len(remaining), batch_size):
            batch = remaining[batch_start:batch_start + batch_size]

            # Build prompt
            lines = ["Translate these Sanskrit/Hindi verses to brief English (1-2 sentences each).",
                      "Return ONLY translations, one per line, numbered to match input.", ""]
            for idx, v in enumerate(batch):
                sanskrit = v.get('sanskrit') or v.get('text') or ''
                lines.append(f"{idx + 1}: {sanskrit[:500]}")

            prompt = "\n".join(lines)

            try:
                response = client.models.generate_content(
                    model=settings.GEMINI_FAST_MODEL,
                    contents=prompt,
                    config={"temperature": 0.2, "max_output_tokens": 4096}
                )

                if response.text:
                    # Parse numbered responses
                    translations = {}
                    for line in response.text.strip().split('\n'):
                        line = line.strip()
                        m = re.match(r'^(\d+)[:\.\)]\s*(.*)', line)
                        if m:
                            idx = int(m.group(1)) - 1
                            translations[idx] = m.group(2).strip()

                    # Apply translations
                    for idx, v in enumerate(batch):
                        if idx in translations and translations[idx]:
                            v['meaning'] = translations[idx]
                            # Also update text if it was Sanskrit-only
                            if self._is_primarily_devanagari(v.get('text', '')):
                                v['text'] = translations[idx]
                            translated_refs.add(v.get('reference', ''))
                            total_translated += 1

                logger.info(f"Translated batch {batch_start // batch_size + 1}: "
                           f"{total_translated}/{len(remaining)} done")

                # Save checkpoint
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump({'translated_refs': list(translated_refs),
                              'total': total_translated}, f)

            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate' in error_str.lower():
                    # Rate limited - exponential backoff
                    backoff = min(backoff * 2, 60)
                    logger.warning(f"Rate limited, backing off {backoff}s")
                else:
                    logger.error(f"Translation batch failed: {e}")

            # Rate limit sleep
            await asyncio.sleep(backoff)

        logger.info(f"Translation complete: {total_translated} verses translated")

    def _needs_instruction_prefix(self) -> bool:
        """Check if the embedding model requires query/passage prefixes (e.g., E5 models)."""
        return "e5" in settings.EMBEDDING_MODEL.lower()

    def generate_embeddings(self, verses: List[Dict]) -> np.ndarray:
        """Generate embeddings for all verses"""
        if not self.embedding_model:
            logger.warning("No embedding model available - using dummy embeddings")
            return np.zeros((len(verses), settings.EMBEDDING_DIM))

        use_prefix = self._needs_instruction_prefix()

        texts = []
        for verse in verses:
            # Combine fields for better semantic representation
            text_parts = [
                verse.get('text', ''),
                verse.get('sanskrit', ''),
                verse.get('meaning', ''),
            ]
            combined_text = ' '.join([p for p in text_parts if p])

            # Normalize text: strip whitespace, replace newlines (matches RAGPipeline)
            clean_text = combined_text.strip().replace("\n", " ")[:1000]

            # E5 models require "passage: " prefix for document encoding
            if use_prefix:
                clean_text = "passage: " + clean_text

            texts.append(clean_text)

        logger.info(f"Generating embeddings for {len(texts)} verses (prefix={'passage' if use_prefix else 'none'})...")
        embeddings = self.embedding_model.encode(
            texts,
            convert_to_tensor=False,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        logger.info(f"Generated embeddings shape: {embeddings.shape}")
        return embeddings

    def save_processed_data(self, verses: List[Dict], embeddings: np.ndarray):
        """Save processed verses (metadata) and embeddings separately for memory efficiency"""
        metadata_file = self.processed_data_dir / "verses.json"
        embeddings_file = self.processed_data_dir / "embeddings.npy"
        
        # 1. Save embeddings as binary NumPy file
        logger.info(f"Saving embeddings to {embeddings_file}...")
        np.save(embeddings_file, embeddings.astype('float32'))
        
        # 2. Save verses as JSON (REMOVING embeddings from the objects)
        logger.info(f"Saving verse metadata to {metadata_file}...")
        for verse in verses:
            if 'embedding' in verse:
                verse.pop('embedding')
                
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump({
                'verses': verses,
                'metadata': {
                    'total_verses': len(verses),
                    'embedding_dim': embeddings.shape[1] if len(embeddings) > 0 else 0,
                    'embedding_model': settings.EMBEDDING_MODEL,
                    'scriptures': sorted(list(set(v.get('scripture', 'Unknown') for v in verses)))
                }
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ Saved RAG data efficiently: {metadata_file} and {embeddings_file}")

        logger.info("\n🎯 Data is ready for RAG pipeline!")

    async def ingest_all_async(self):
        """Main async ingestion pipeline"""
        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING UNIVERSAL SCRIPTURE DATASET INGESTION")
        logger.info("=" * 80)

        # Find dataset files
        files = self.find_dataset_files()

        if not files:
            logger.error("\n❌ No dataset files found!")
            logger.error(f"📁 Expected location: {self.raw_data_dir}")
            return

        # Parse all files
        all_verses = []
        scripture_counts = {}

        logger.info(f"\n📂 Processing {len(files)} files...\n")

        for file_path in sorted(files):
            if file_path.suffix == '.csv':
                verses = self.parse_csv_file(file_path)
            elif file_path.suffix == '.json':
                verses = self.parse_json_file(file_path)
            elif file_path.suffix == '.pdf':
                verses = await self.parse_pdf_file(file_path)
            elif file_path.suffix.lower() in ['.mp4', '.mkv', '.mov', '.avi', '.webm']:
                verses = await self.parse_video_file(file_path)
            else:
                logger.warning(f"⚠ Unsupported file type: {file_path.name}")
                continue

            if verses:
                all_verses.extend(verses)
                scripture = self._infer_scripture(file_path.stem)
                scripture_counts[scripture] = scripture_counts.get(scripture, 0) + len(verses)

        if not all_verses:
            logger.error("\n❌ No verses extracted from dataset!")
            return

        logger.info(f"\n✅ Successfully parsed {len(all_verses)} total verses")
        logger.info("\nBreakdown by scripture:")
        for scripture, count in sorted(scripture_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  • {scripture}: {count} verses")

        # Remove duplicates based on reference
        unique_verses = {}
        for verse in all_verses:
            ref = verse.get('reference')
            if ref not in unique_verses:
                unique_verses[ref] = verse

        all_verses = list(unique_verses.values())
        logger.info(f"\n✅ {len(all_verses)} unique verses after deduplication")

        # Translate Sanskrit-only verses to English
        # NOTE: Uncomment for Phase 2 (translation via Gemini Flash, ~2h for full corpus)
        verses_needing_translation = [v for v in all_verses if self._needs_translation(v)]
        if verses_needing_translation:
            logger.info(f"\n🌐 {len(verses_needing_translation)} verses need translation")
            await self._batch_translate_verses(verses_needing_translation)
        else:
            logger.info("\n✅ All verses already have English content")

        # Generate embeddings
        logger.info("\n🔄 Generating embeddings...")
        embeddings = self.generate_embeddings(all_verses)

        # Save processed data
        logger.info("\n💾 Saving processed data...")
        self.save_processed_data(all_verses, embeddings)

        logger.info("\n" + "=" * 80)
        logger.info("✅ INGESTION COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"📊 Total verses processed: {len(all_verses)}")
        logger.info(f"📁 Output directory: {self.processed_data_dir}")
        logger.info("📄 Files created:")
        logger.info("   • processed_data.json (with embeddings)")
        logger.info("\n🎯 Data is ready for RAG pipeline!")


def main():
    """Run ingestion"""
    ingester = UniversalScriptureIngester()
    asyncio.run(ingester.ingest_all_async())


if __name__ == "__main__":
    main()
