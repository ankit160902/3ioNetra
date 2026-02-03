"""
Ingest all spiritual text datasets and create embeddings for RAG pipeline
Handles multiple data formats: CSV, JSON with various structures
"""
import os
import sys
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from config import settings

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

    def find_dataset_files(self) -> List[Path]:
        """Find all dataset files in raw data directory"""
        files = []

        if not self.raw_data_dir.exists():
            logger.error(f"Raw data directory not found: {self.raw_data_dir}")
            return files

        # Look for CSV and JSON files
        csv_files = list(self.raw_data_dir.glob("*.csv"))
        json_files = list(self.raw_data_dir.glob("*.json"))

        files.extend(csv_files)
        files.extend(json_files)

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

            # Handle different JSON structures
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    if idx > 10000:  # Limit for performance
                        break
                    verse = self._extract_verse_from_dict(item, file_path.stem)
                    if verse:
                        verses.append(verse)
            elif isinstance(data, dict):
                # Could be nested structure
                for key, value in data.items():
                    if isinstance(value, list):
                        for idx, item in enumerate(value):
                            if idx > 10000:  # Limit for performance
                                break
                            verse = self._extract_verse_from_dict(item, file_path.stem)
                            if verse:
                                verses.append(verse)
                    elif isinstance(value, dict):
                        verse = self._extract_verse_from_dict(value, file_path.stem)
                        if verse:
                            verses.append(verse)

            if verses:
                logger.info(f"✓ Parsed {len(verses)} verses from {file_path.name}")
            else:
                logger.warning(f"⚠ No verses extracted from {file_path.name}")

        except Exception as e:
            logger.error(f"✗ Error parsing JSON {file_path.name}: {e}")

        return verses

    def parse_temples_file(self, file_path: Path) -> List[Dict]:
        """Parse Hindu Temples JSON file"""
        verses = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return []

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
        
        # Combine all info fields for searchable text - making it VERY rich
        text_parts = []
        
        # Core Info
        if name: text_parts.append(f"Temple Name: {name}")
        if state: text_parts.append(f"State: {state}")
        if temple.get('Location'): text_parts.append(f"Location: {temple['Location']}")
        if temple.get('Main deity'): text_parts.append(f"Main Deity: {temple['Main deity']}")
        if temple.get('Other deities'): text_parts.append(f"Other Deities: {temple['Other deities']}")
        
        # Summaries
        if temple.get('info'): text_parts.append(f"Summary: {temple['info']}")
        if temple.get('Significance'): text_parts.append(f"Significance: {temple['Significance']}")
        
        # Detailed sections
        if temple.get('History'): text_parts.append(f"History: {temple['History']}")
        if temple.get('Detailed History'): text_parts.append(f"Detailed History: {temple['Detailed History']}")
        if temple.get('story'): text_parts.append(f"Spiritual Story: {temple['story']}")
        
        if temple.get('Architecture'): text_parts.append(f"Architecture: {temple['Architecture']}")
        if temple.get('Detailed Architecture'): text_parts.append(f"Detailed Architecture: {temple['Detailed Architecture']}")
        if temple.get('Key features of the architecture'): text_parts.append(f"Architectural Features: {temple['Key features of the architecture']}")
        
        # Scriptural
        if temple.get('mention_in_scripture'): text_parts.append(f"Scriptural Mention: {temple['mention_in_scripture']}")
        if temple.get('Scriptural References'): text_parts.append(f"Scriptural References: {temple['Scriptural References']}")
        
        # Visiting Guide
        if temple.get('visiting_guide'): text_parts.append(f"Visiting Guide: {temple['visiting_guide']}")
        if temple.get('1. Getting There'): text_parts.append(f"Getting There: {temple['1. Getting There']}")
        if temple.get('2. Accommodation'): text_parts.append(f"Accommodation: {temple['2. Accommodation']}")
        if temple.get('3. Things to Do'): text_parts.append(f"Things to Do: {temple['3. Things to Do']}")
        if temple.get('4. Other things'): text_parts.append(f"Other Things: {temple['4. Other things']}")
        if temple.get('5. Tips'): text_parts.append(f"Travel Tips: {temple['5. Tips']}")
        
        # Logistics
        if temple.get('Timings'): text_parts.append(f"Timings: {temple['Timings']}")
        if temple.get('Entry Fee'): text_parts.append(f"Entry Fee: {temple['Entry Fee']}")
        if temple.get('Contact Information'): text_parts.append(f"Contact Information: {temple['Contact Information']}")
        
        combined_text = "\n\n".join(text_parts)
        
        if not combined_text:
            combined_text = f"Information about {name} temple in {state}."

        # Create a verse-like object
        verse = {
            'chapter': state,
            'verse': name,
            'text': combined_text,
            'scripture': 'Hindu Temples',
            'source': 'hindu_temples',
            'reference': f"Temple: {name} ({state})",
            'language': 'en',
            'topic': 'Temples and Pilgrimage',
            'metadata': {
                'state': state,
                'name': name,
                'visiting_guide': temple.get('visiting_guide'),
                'location': temple.get('Location'),
                'main_deity': temple.get('Main deity')
            }
        }
        return verse

    def _extract_verse_from_csv_row(self, row: Dict, source: str) -> Dict:
        """Extract verse from CSV row"""
        verse = {}

        # Map common column names (case-insensitive)
        row_lower = {k.lower(): v for k, v in row.items() if v}

        # Extract fields
        verse['chapter'] = row_lower.get('chapter') or row_lower.get('adhyaya') or row_lower.get('id', '').split('.')[0] if '.' in row_lower.get('id', '') else None
        verse['verse'] = row_lower.get('verse') or row_lower.get('shloka') or row_lower.get('shloka_number')
        
        # Priority for English content
        verse['text'] = row_lower.get('engmeaning') or row_lower.get('translation') or row_lower.get('english') or row_lower.get('text')
        
        # Original Sanskrit/Hindi
        verse['sanskrit'] = row_lower.get('shloka') or row_lower.get('original') or row_lower.get('sanskrit')
        
        verse['transliteration'] = row_lower.get('transliteration') or row_lower.get('iast')
        
        # Add meaning/explanation
        verse['meaning'] = row_lower.get('meaning') or row_lower.get('explanation') or row_lower.get('wordmeaning') or row_lower.get('hinmeaning')
        verse['hindi'] = row_lower.get('hinmeaning') or row_lower.get('hindi')

        # Only return if we have essential fields
        if verse.get('chapter') and verse.get('verse') and verse.get('text'):
            verse['scripture'] = self._infer_scripture(source)
            verse['source'] = source
            verse['reference'] = f"{verse['scripture']} {verse['chapter']}.{verse['verse']}"
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

        verse['chapter'] = safe_get(['chapter', 'adhyaya', 'book', 'mandala', 'kaanda'])
        verse['verse'] = safe_get(['verse', 'shloka', 'shloka_number', 'verse_number'])
        verse['text'] = safe_get(['text', 'translation', 'english', 'meaning', 'content'])
        verse['sanskrit'] = safe_get(['shloka', 'sanskrit', 'original', 'devanagari'])
        verse['transliteration'] = safe_get(['transliteration', 'iast', 'romanized', 'transliteraion'])

        # Only return if we have essential fields
        if verse.get('chapter') and verse.get('verse') and verse.get('text'):
            verse['scripture'] = self._infer_scripture(source)
            verse['source'] = source
            verse['reference'] = f"{verse['scripture']} {verse['chapter']}.{verse['verse']}"
            verse['language'] = 'en'
            verse['topic'] = self._infer_topic(verse)

            return {k: v for k, v in verse.items() if v}  # Remove None values

        return None

    def _infer_scripture(self, source: str) -> str:
        """Infer scripture name from filename"""
        source_lower = source.lower()

        if 'bhagavad' in source_lower or 'bhagwad' in source_lower or 'gita' in source_lower:
            return 'Bhagavad Gita'
        elif 'mahabharata' in source_lower:
            return 'Mahabharata'
        elif 'ramayana' in source_lower or 'balakanda' in source_lower or 'ayodhya' in source_lower:
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
        else:
            return 'Sanatan Scriptures'

    def _infer_topic(self, verse: Dict) -> str:
        """Infer topic from verse content"""
        text = (verse.get('text', '') + ' ' + verse.get('meaning', '') + ' ' + verse.get('sanskrit', '')).lower()

        topics = {
            'Karma Yoga': ['action', 'duty', 'work', 'karma', 'perform', 'karm'],
            'Bhakti Yoga': ['devotion', 'love', 'surrender', 'worship', 'bhakti', 'prem'],
            'Jnana Yoga': ['knowledge', 'wisdom', 'understand', 'jnana', 'learning', 'gyan'],
            'Mind Control': ['mind', 'control', 'meditation', 'focus', 'discipline', 'mana'],
            'Soul': ['soul', 'atman', 'self', 'eternal', 'immortal', 'aatma'],
            'Equanimity': ['equal', 'balance', 'neutral', 'steady', 'sama', 'equanimity'],
            'Fear': ['fear', 'afraid', 'courage', 'fearless', 'bhaya'],
            'Death': ['death', 'mortality', 'rebirth', 'reincarnation', 'mrutyu'],
            'Liberation': ['liberation', 'moksha', 'freedom', 'enlightenment', 'mukt'],
            'Dharma': ['dharma', 'righteousness', 'duty', 'moral', 'dharm'],
            'Truth': ['truth', 'satya', 'honest', 'real'],
            'Wealth': ['wealth', 'money', 'prosperity', 'success'],
            'Love': ['love', 'affection', 'compassion', 'prem', 'sneh'],
            'War': ['war', 'battle', 'fight', 'yuddh', 'yudh'],
        }

        for topic, keywords in topics.items():
            if any(keyword in text for keyword in keywords):
                return topic

        return 'Spiritual Wisdom'

    def generate_embeddings(self, verses: List[Dict]) -> np.ndarray:
        """Generate embeddings for all verses"""
        if not self.embedding_model:
            logger.warning("⚠ No embedding model available - using dummy embeddings")
            return np.zeros((len(verses), 768))

        texts = []
        for verse in verses:
            # Combine fields for better semantic representation
            text_parts = [
                verse.get('text', ''),
                verse.get('sanskrit', ''),
                verse.get('meaning', ''),
            ]
            combined_text = ' '.join([p for p in text_parts if p])
            texts.append(combined_text[:1000])  # Limit length

        logger.info(f"Generating embeddings for {len(texts)} verses...")
        embeddings = self.embedding_model.encode(texts, convert_to_tensor=False, show_progress_bar=True)

        logger.info(f"✓ Generated embeddings shape: {embeddings.shape}")
        return embeddings

    def save_processed_data(self, verses: List[Dict], embeddings: np.ndarray):
        """Save processed verses and embeddings"""
        output_file = self.processed_data_dir / "processed_data.json"

        # Convert embeddings to list for JSON serialization
        for i, verse in enumerate(verses):
            verse['embedding'] = embeddings[i].tolist()

        # Save as JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'verses': verses,
                'metadata': {
                    'total_verses': len(verses),
                    'embedding_dim': len(embeddings[0]) if len(embeddings) > 0 else 0,
                    'embedding_model': settings.EMBEDDING_MODEL,
                    'scriptures': sorted(list(set(v.get('scripture', 'Unknown') for v in verses)))
                }
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ Saved consolidated processed data to {output_file}")

    def ingest_all(self):
        """Main ingestion pipeline"""
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
        logger.info(f"📄 Files created:")
        logger.info(f"   • processed_data.json (with embeddings)")
        logger.info("\n🎯 Data is ready for RAG pipeline!")


def main():
    """Run ingestion"""
    ingester = UniversalScriptureIngester()
    ingester.ingest_all()


if __name__ == "__main__":
    main()
