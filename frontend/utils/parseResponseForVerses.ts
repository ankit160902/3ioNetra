export type SegmentType = 'text' | 'verse' | 'mantra';

export interface ParsedSegment {
  type: SegmentType;
  content: string;
}

/**
 * Detect verse lines in a response.
 * Returns an array of segments: { type: 'text' | 'verse' | 'mantra', content: string }
 * A "verse" segment is any line that contains a scripture citation pattern.
 */
export function parseResponseForVerses(text: string): ParsedSegment[] {
  if (!text) return [{ type: 'text', content: '' }];

  if (text.includes('[VERSE]') || text.includes('[MANTRA]')) {
    const segments: ParsedSegment[] = [];
    const regex = /\[(VERSE|MANTRA)\]([\s\S]*?)\[\/\1\]/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const beforeText = text.substring(lastIndex, match.index);
      if (beforeText.trim()) {
        // Clean punctuation artifacts at tag boundaries
        let cleaned = beforeText;
        if (lastIndex > 0) {
          // This text follows a previous tag — strip leading punctuation
          cleaned = cleaned.replace(/^\s*[""''\u2018\u2019\u201c\u201d]*[.,;:]+\s*/, '');
        }
        // Strip trailing punctuation before upcoming tag
        cleaned = cleaned.replace(/[,;:]\s*$/, '');
        if (cleaned.trim()) {
          segments.push({ type: 'text', content: cleaned });
        }
      }
      const tagType = match[1].toLowerCase() as 'verse' | 'mantra';
      let tagContent = match[2].trim();
      if (tagContent) {
        // Robust cleaning of markdown artifacts from the beginning/end
        tagContent = tagContent.replace(/^[*_>`"„"' ]+/, '').replace(/[*_>`"„"' ]+$/, '');
        segments.push({ type: tagType, content: tagContent });
      }
      lastIndex = regex.lastIndex;
    }

    const remainingText = text.substring(lastIndex);
    if (remainingText.trim()) {
      // Clean leading punctuation orphaned by preceding tag card
      const cleaned = remainingText.replace(/^\s*[""''\u2018\u2019\u201c\u201d]*[.,;:]+\s*/, '');
      if (cleaned.trim()) {
        segments.push({ type: 'text', content: cleaned });
      }
    }

    return segments.length > 0 ? segments : [{ type: 'text', content: text }];
  }

  const lines = text.split('\n');
  const segments: ParsedSegment[] = [];

  const versePatterns = [
    /[\u0900-\u097F]{3,}/,
    /^\s*["'""].*["'""]\s*[-–—]\s*/,
    /^\s*["'""].*["'""]\s*$/,
    /^\s*\(\b(Bhagavad\s*Gita|Gita|Yoga\s*Sutra|Upanishad|Vedas?|Mahabharata|Ramayana)\b.*\d+.*\)\s*$/i,
    /^\s*(Chapter|Verse|Shloka|Sutra|Mantra)\s*\d/i,
  ];

  let currentText: string[] = [];

  for (const line of lines) {
    const isVerse = versePatterns.some(p => p.test(line));

    if (isVerse) {
      if (currentText.length > 0) {
        segments.push({ type: 'text', content: currentText.join('\n') });
        currentText = [];
      }
      segments.push({ type: 'verse', content: line });
    } else {
      currentText.push(line);
    }
  }

  if (currentText.length > 0) {
    segments.push({ type: 'text', content: currentText.join('\n') });
  }

  return segments;
}
