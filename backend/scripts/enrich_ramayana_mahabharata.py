"""
Enrich Ramayana & Mahabharata data for better RAG retrieval.

Phase A: Inject curated English narrative summaries (~25 episodes)
Phase B: Batch-translate ~1,500 key verses via Gemini Flash
Phase C: Regenerate all embeddings

Usage:
    cd backend && python3 scripts/enrich_ramayana_mahabharata.py
    # Phase A only (no API calls):
    cd backend && python3 scripts/enrich_ramayana_mahabharata.py --narratives-only
    # Phase B only (translation):
    cd backend && python3 scripts/enrich_ramayana_mahabharata.py --translate-only
    # Phase C only (regen embeddings):
    cd backend && python3 scripts/enrich_ramayana_mahabharata.py --embeddings-only
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
VERSES_PATH = PROCESSED_DIR / "verses.json"
EMBEDDINGS_PATH = PROCESSED_DIR / "embeddings.npy"
CHECKPOINT_PATH = PROCESSED_DIR / "enrichment_checkpoint.json"


# ---------------------------------------------------------------------------
# Phase A: Curated Narrative Summaries
# ---------------------------------------------------------------------------

CURATED_NARRATIVES: List[Dict] = [
    # --- Ramayana: Sundara Kanda (Hanuman's devotion — fixes IDs 23, 77) ---
    {
        "scripture": "Ramayana",
        "chapter": "SundaraKanda",
        "section": "1",
        "verse_number": "narrative_1",
        "reference": "Ramayana Sundara Kanda — Hanuman's Leap to Lanka",
        "text": "Hanuman, the mighty son of Vayu, leaps across the vast ocean to reach Lanka in search of Sita. "
                "His devotion to Lord Rama gives him the strength to overcome every obstacle — the demoness Surasa, "
                "the shadow-grasping Simhika, and the towering waves. This leap symbolizes the power of unwavering "
                "bhakti: when one is devoted to the divine, no ocean is too wide and no challenge too great.",
        "meaning": "Hanuman's leap across the ocean to Lanka demonstrates that supreme devotion (bhakti) to God "
                   "grants extraordinary strength. His love for Rama transforms an impossible journey into a triumph "
                   "of faith and courage.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "SundaraKanda",
        "section": "13",
        "verse_number": "narrative_2",
        "reference": "Ramayana Sundara Kanda — Hanuman Finds Sita in Ashoka Vatika",
        "text": "After searching all of Lanka, Hanuman finally discovers Sita in the Ashoka garden, "
                "surrounded by demonesses who torment her. Despite her suffering, Sita's faith in Rama "
                "never wavers. Hanuman reveals himself, shows Rama's ring as proof, and reassures her that "
                "Rama will come to rescue her. This scene is the emotional heart of the Ramayana — the meeting "
                "of pure devotion (Hanuman) with pure faith (Sita).",
        "meaning": "Hanuman's discovery of Sita in Lanka shows that a true devotee never gives up searching "
                   "for truth. Sita's unwavering faith in Rama despite imprisonment teaches that trust in the "
                   "divine sustains us through the darkest times.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "SundaraKanda",
        "section": "35",
        "verse_number": "narrative_3",
        "reference": "Ramayana Sundara Kanda — Hanuman's Devotion to Rama",
        "text": "Hanuman's devotion to Rama is the central theme of the Sundara Kanda. When asked about his "
                "strength, Hanuman says it comes entirely from Rama's grace. He carries Rama in his heart at "
                "every moment. This selfless, unconditional devotion is considered the highest form of bhakti "
                "in Sanatan Dharma. Hanuman is called Mahabhakta — the supreme devotee — because his love for "
                "Rama is without any desire for personal gain.",
        "meaning": "Hanuman embodies the ideal of selfless devotion (nishkama bhakti). His strength, courage, "
                   "and wisdom all flow from his love for Rama. The significance of Hanuman's devotion is that "
                   "it shows pure love for God is the greatest source of power.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Yuddha Kanda (Hanuman's power — fixes ID 77) ---
    {
        "scripture": "Ramayana",
        "chapter": "YuddhaKanda",
        "section": "30",
        "verse_number": "narrative_4",
        "reference": "Ramayana Yuddha Kanda — Hanuman Brings Sanjeevani",
        "text": "When Lakshmana falls in battle, mortally wounded by Indrajit's weapon, the physician Sushena "
                "says only the Sanjeevani herb from the Himalayas can save him. Hanuman flies to the Dronagiri "
                "mountain, and unable to identify the herb, lifts the entire mountain and brings it back to Lanka. "
                "This act demonstrates Hanuman's extraordinary power (shakti), his devotion to Rama's family, "
                "and his willingness to move mountains — literally — for those he loves.",
        "meaning": "Hanuman lifting the Sanjeevani mountain shows that devotion gives superhuman strength. "
                   "The secret of Hanuman's power (shakti ka raaz) is his complete surrender to Rama. "
                   "When love is the motivation, even the impossible becomes possible.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "YuddhaKanda",
        "section": "115",
        "verse_number": "narrative_5",
        "reference": "Ramayana Yuddha Kanda — Hanuman Burns Lanka",
        "text": "When Ravana's soldiers capture Hanuman and set his tail on fire, Hanuman uses his divine power "
                "to grow enormous and leaps across Lanka, setting the golden city ablaze. This episode shows "
                "Hanuman's fearlessness and his power born from Rama's blessing. Even in captivity, a true "
                "devotee cannot be defeated. The burning of Lanka is a symbol of how dharma ultimately "
                "triumphs over adharma.",
        "meaning": "Hanuman burning Lanka demonstrates that divine power protects the righteous. "
                   "Hanuman ji ki shakti (Hanuman's power) comes from his devotion to Rama and his "
                   "commitment to dharma. No enemy can overcome one who carries God in their heart.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Ayodhya Kanda (Rama's exile — fixes ID 49) ---
    {
        "scripture": "Ramayana",
        "chapter": "AyodhyaKanda",
        "section": "16",
        "verse_number": "narrative_6",
        "reference": "Ramayana Ayodhya Kanda — Kaikeyi's Boons and Rama's Exile",
        "text": "Queen Kaikeyi, influenced by her maid Manthara, asks King Dasharatha to honour two boons: "
                "that her son Bharata be crowned king, and that Rama be exiled to the forest for fourteen years. "
                "Dasharatha is heartbroken but bound by his word. This is the pivotal event that sets the "
                "entire Ramayana in motion — Rama's vanvas (exile to the forest). "
                "राम का वनवास इसलिए हुआ क्योंकि दशरथ अपने वचन से बंधे थे।",
        "meaning": "Rama's exile (vanvas) happened because King Dasharatha was bound by his promise to Kaikeyi. "
                   "This episode teaches the supreme importance of keeping one's word (satya) even when it causes "
                   "immense personal suffering. Rama accepted exile without complaint, demonstrating perfect "
                   "obedience to dharma and filial duty.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "AyodhyaKanda",
        "section": "19",
        "verse_number": "narrative_7",
        "reference": "Ramayana Ayodhya Kanda — Rama Accepts Exile with Grace",
        "text": "When Rama learns of his exile, he shows no anger, sorrow, or resentment. He calmly accepts "
                "his father's command, saying that a son's dharma is to obey his parents. Sita and Lakshmana "
                "refuse to let him go alone and insist on accompanying him. Rama's acceptance of vanvas is "
                "one of the most celebrated moments in Hindu dharma — it shows that true strength lies not in "
                "resistance but in graceful acceptance of one's duty.",
        "meaning": "Rama's calm acceptance of exile teaches that dharma sometimes demands sacrifice. "
                   "A person of true character faces adversity with equanimity. राम ने वनवास को सहज भाव "
                   "से स्वीकार किया क्योंकि वे धर्म के मार्ग पर चलने वाले थे।",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "AyodhyaKanda",
        "section": "24",
        "verse_number": "narrative_8",
        "reference": "Ramayana Ayodhya Kanda — Dasharatha's Death from Grief",
        "text": "King Dasharatha, unable to bear the separation from his beloved son Rama, dies of grief "
                "shortly after Rama departs for the forest. His last words call out Rama's name. This tragic "
                "episode illustrates the depth of a father's love and the devastating consequences of Kaikeyi's "
                "demand. It also shows how attachment (moha) can lead to suffering.",
        "meaning": "Dasharatha's death from grief over Rama's exile is a powerful lesson about the pain of "
                   "attachment and separation. Even a great king cannot escape the suffering caused by deep "
                   "attachment to loved ones.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    {
        "scripture": "Ramayana",
        "chapter": "AyodhyaKanda",
        "section": "109",
        "verse_number": "narrative_9",
        "reference": "Ramayana Ayodhya Kanda — Bharata's Devotion to Rama",
        "text": "When Bharata learns what his mother Kaikeyi has done, he is filled with anguish. He marches "
                "to the forest to bring Rama back, but Rama refuses to return until the fourteen years are "
                "complete. Bharata then takes Rama's sandals and places them on the throne of Ayodhya, ruling "
                "as Rama's regent from the village of Nandigram. This story of Bharata's devotion to his "
                "brother is a supreme example of selfless love and dharma.",
        "meaning": "Bharata's refusal to enjoy a kingdom obtained through injustice shows that true dharma "
                   "means choosing righteousness over personal gain. His devotion to Rama mirrors Hanuman's "
                   "bhakti in a different form.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Sita's suffering ---
    {
        "scripture": "Ramayana",
        "chapter": "SundaraKanda",
        "section": "28",
        "verse_number": "narrative_10",
        "reference": "Ramayana Sundara Kanda — Sita's Suffering and Steadfast Faith",
        "text": "In Lanka's Ashoka Vatika, Sita endures constant threats from Ravana and his demonesses. "
                "They try to break her spirit, offering her the luxury of being Ravana's queen. But Sita "
                "refuses, holding a blade of grass between herself and Ravana, saying she would rather die "
                "than betray Rama. Her suffering and steadfastness represent the power of pativrata dharma "
                "and unshakeable faith.",
        "meaning": "Sita's suffering in Lanka and her refusal to submit to Ravana teaches that inner strength "
                   "comes from moral conviction. Even in the darkest captivity, faith in dharma and love for "
                   "the divine sustains the soul.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Balakanda ---
    {
        "scripture": "Ramayana",
        "chapter": "BalaKanda",
        "section": "1",
        "verse_number": "narrative_11",
        "reference": "Ramayana Bala Kanda — The Story of Rama (Overview)",
        "text": "The Ramayana, composed by sage Valmiki, tells the story of Prince Rama of Ayodhya — the ideal "
                "man (Maryada Purushottam). Born as the eldest son of King Dasharatha, Rama embodies dharma, "
                "truth, and compassion. The epic follows his journey through exile, the abduction of his wife "
                "Sita by the demon king Ravana, and the great war to rescue her with the help of Hanuman and "
                "the vanara army. The Ramayana teaches the principles of duty, devotion, and righteousness.",
        "meaning": "The Ramayana is one of the two great epics of Sanatan Dharma. It teaches through the life "
                   "of Lord Rama that adherence to dharma, even at great personal cost, is the highest ideal "
                   "of human life.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Draupadi ---
    {
        "scripture": "Mahabharata",
        "chapter": "2",
        "section": "sabha_parva",
        "verse_number": "narrative_12",
        "reference": "Mahabharata Sabha Parva — Draupadi's Disrobing (Vastraharan)",
        "text": "In the game of dice, Yudhishthira loses everything — his kingdom, his brothers, himself, "
                "and finally Draupadi. Duryodhana orders Dushasana to drag Draupadi into the court and "
                "disrobe her. In her moment of ultimate helplessness, Draupadi calls out to Lord Krishna. "
                "Krishna miraculously provides an endless sari, protecting her honour. This episode is one of "
                "the most powerful moments in the Mahabharata — it shows that when all human help fails, "
                "surrender to God brings divine protection.",
        "meaning": "Draupadi's vastraharan teaches that complete surrender to God in moments of helplessness "
                   "invites divine grace. Krishna's intervention shows that God protects those who call upon "
                   "Him with genuine faith.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Bhishma ---
    {
        "scripture": "Mahabharata",
        "chapter": "6",
        "section": "bhishma_parva",
        "verse_number": "narrative_13",
        "reference": "Mahabharata Bhishma Parva — Bhishma's Teachings on Dharma",
        "text": "Bhishma, the grand patriarch, is renowned for his vow of lifelong celibacy (brahmacharya) "
                "and his unwavering commitment to his word. Lying on a bed of arrows after the war, he delivers "
                "extensive teachings on dharma, governance, and righteous conduct to Yudhishthira. Bhishma's "
                "life teaches that keeping one's vow, even at immense personal sacrifice, is the mark of a "
                "truly great soul.",
        "meaning": "Bhishma's teachings from his deathbed cover the full scope of dharma — duty, kingship, "
                   "justice, and spiritual wisdom. His life demonstrates that commitment to one's word and "
                   "dharma transcends personal happiness.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Kurukshetra ---
    {
        "scripture": "Mahabharata",
        "chapter": "6",
        "section": "bhishma_parva",
        "verse_number": "narrative_14",
        "reference": "Mahabharata Bhishma Parva — The Battle of Kurukshetra",
        "text": "The great war of Kurukshetra is fought between the Pandavas and Kauravas over the rightful "
                "claim to the throne of Hastinapura. Before the battle, Arjuna faces a moral crisis — he "
                "cannot bring himself to fight his own family. Lord Krishna delivers the Bhagavad Gita on "
                "the battlefield, teaching Arjuna about duty, the immortal soul, and the paths of yoga. "
                "The war lasts eighteen days and ends with the Pandavas' victory.",
        "meaning": "The Kurukshetra war represents the eternal battle between dharma and adharma. "
                   "Krishna's Gita teachings emerge from this crisis, showing that difficult situations "
                   "can become opportunities for the deepest spiritual wisdom.",
        "topic": "Karma Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Karna ---
    {
        "scripture": "Mahabharata",
        "chapter": "1",
        "section": "adi_parva",
        "verse_number": "narrative_15",
        "reference": "Mahabharata — The Tragedy of Karna",
        "text": "Karna, born to Kunti and the Sun god Surya, is abandoned at birth and raised by a charioteer. "
                "Despite being a Pandava by blood, he becomes Duryodhana's closest friend and fights on the "
                "Kaurava side. Karna's life is a tragedy of identity, loyalty, and unfulfilled potential. He is "
                "one of the greatest warriors but is denied recognition because of his perceived low birth. "
                "His story teaches about the injustice of caste discrimination and the complexity of dharma.",
        "meaning": "Karna's story shows that dharma is not always black and white. His loyalty to Duryodhana, "
                   "despite knowing the Pandavas' cause was just, illustrates how personal bonds can conflict "
                   "with universal righteousness.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Yudhishthira ---
    {
        "scripture": "Mahabharata",
        "chapter": "12",
        "section": "shanti_parva",
        "verse_number": "narrative_16",
        "reference": "Mahabharata Shanti Parva — Yudhishthira's Grief and Wisdom",
        "text": "After the great war, Yudhishthira is overcome with grief at the devastation he has caused. "
                "He wishes to renounce the kingdom and retire to the forest. Bhishma, Krishna, and the sages "
                "counsel him that a king's dharma is to serve his people, not to flee from responsibility. "
                "The Shanti Parva contains the longest discourse on governance, ethics, and dharma in all of "
                "Hindu literature.",
        "meaning": "Yudhishthira's post-war grief teaches that victory without peace brings no joy. "
                   "The Shanti Parva's teachings on raja-dharma (duty of a ruler) emphasize that leadership "
                   "is a form of selfless service.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Krishna's Vishwaroop ---
    {
        "scripture": "Mahabharata",
        "chapter": "6",
        "section": "bhishma_parva",
        "verse_number": "narrative_17",
        "reference": "Mahabharata — Krishna's Universal Form (Vishwaroop Darshan)",
        "text": "In the Bhagavad Gita (Chapter 11), Arjuna asks Krishna to reveal his true divine form. "
                "Krishna shows the Vishwaroop — a cosmic vision containing all of creation, destruction, "
                "past, present, and future. Arjuna is overwhelmed with awe and terror. This vision teaches "
                "that God encompasses everything — beauty and destruction, birth and death, joy and sorrow.",
        "meaning": "Krishna's Vishwaroop darshan reveals that the divine is beyond all human categories. "
                   "Seeing God's universal form teaches humility and the understanding that our individual "
                   "perspective is only a tiny fraction of reality.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Aranya Kanda ---
    {
        "scripture": "Ramayana",
        "chapter": "AranyaKanda",
        "section": "40",
        "verse_number": "narrative_18",
        "reference": "Ramayana Aranya Kanda — Sita's Abduction by Ravana",
        "text": "In the Dandaka forest, the demoness Surpanakha is attracted to Rama and is humiliated by "
                "Lakshmana. In revenge, Ravana devises a plan: he sends the golden deer Maricha to lure Rama "
                "away, then abducts Sita in Rama's absence. Jatayu, the noble vulture, fights Ravana to "
                "protect Sita but is mortally wounded. Sita's abduction sets the stage for the great war "
                "between Rama and Ravana.",
        "meaning": "Sita's abduction teaches that evil uses deception to attack the righteous. Jatayu's "
                   "sacrifice shows that even a seemingly small act of courage in defense of dharma is "
                   "honored by God — Rama performs Jatayu's last rites as he would for his own father.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Kishkindha Kanda ---
    {
        "scripture": "Ramayana",
        "chapter": "KishkindhaKanda",
        "section": "1",
        "verse_number": "narrative_19",
        "reference": "Ramayana Kishkindha Kanda — Rama's Alliance with Sugriva and Hanuman",
        "text": "In the Kishkindha region, Rama meets Hanuman for the first time. Hanuman, disguised as a "
                "Brahmin, is immediately captivated by Rama's divine presence. He facilitates the alliance "
                "between Rama and the vanara king Sugriva. Rama helps Sugriva defeat his brother Vali, and "
                "in return, Sugriva pledges his vanara army to search for Sita. This alliance is built on "
                "mutual trust and dharma.",
        "meaning": "The meeting of Rama and Hanuman is the beginning of one of the most celebrated "
                   "devotee-God relationships in Hinduism. It teaches that true friendship is born from "
                   "dharma and mutual respect.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Pandava Exile ---
    {
        "scripture": "Mahabharata",
        "chapter": "3",
        "section": "vana_parva",
        "verse_number": "narrative_20",
        "reference": "Mahabharata Vana Parva — The Pandavas' Exile",
        "text": "After losing the game of dice, the Pandavas are exiled to the forest for thirteen years. "
                "During this period, they encounter many sages and learn profound spiritual teachings. "
                "Yudhishthira learns patience, Bhima encounters Hanuman, Arjuna performs penance to obtain "
                "divine weapons, and Draupadi's faith is tested repeatedly. The exile period transforms the "
                "Pandavas from princes into spiritually mature warriors ready for their dharmic duty.",
        "meaning": "The Pandavas' exile teaches that periods of hardship and loss can be opportunities for "
                   "spiritual growth and self-discovery. Like tapas (austerity), suffering purifies and "
                   "strengthens the soul.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Vidura Neeti ---
    {
        "scripture": "Mahabharata",
        "chapter": "5",
        "section": "udyoga_parva",
        "verse_number": "narrative_21",
        "reference": "Mahabharata Udyoga Parva — Vidura's Counsel (Vidura Neeti)",
        "text": "Vidura, the wise minister born of a servant woman, is one of the most morally upright "
                "characters in the Mahabharata. His teachings to Dhritarashtra (Vidura Neeti) cover practical "
                "wisdom about governance, relationships, and righteous living. Vidura warns Dhritarashtra "
                "repeatedly about the consequences of indulging Duryodhana's adharma, but the blind king "
                "cannot bring himself to act against his son.",
        "meaning": "Vidura Neeti teaches that wisdom without action is futile. Dhritarashtra's inability "
                   "to act on Vidura's advice despite knowing it was right shows how attachment (moha) to "
                   "family can blind even intelligent people to dharma.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Ramayana: Uttara Kanda ---
    {
        "scripture": "Ramayana",
        "chapter": "UttaraKanda",
        "section": "1",
        "verse_number": "narrative_22",
        "reference": "Ramayana Uttara Kanda — Ram Rajya (Rama's Rule)",
        "text": "After defeating Ravana and returning to Ayodhya, Rama is crowned king. His rule — Ram Rajya — "
                "becomes the ideal of perfect governance: justice for all, prosperity, no poverty, no crime, "
                "and dharma upheld in every aspect of life. Ram Rajya represents what society can become when "
                "a ruler puts dharma above personal desire.",
        "meaning": "Ram Rajya is the Hindu ideal of a just and prosperous society governed by dharma. "
                   "Rama's rule teaches that a leader's primary duty is the welfare of all citizens, "
                   "regardless of status or background.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Mahabharata: Abhimanyu ---
    {
        "scripture": "Mahabharata",
        "chapter": "7",
        "section": "drona_parva",
        "verse_number": "narrative_23",
        "reference": "Mahabharata Drona Parva — The Valour of Abhimanyu",
        "text": "Abhimanyu, the young son of Arjuna, enters the Chakravyuha (spinning military formation) "
                "knowing only how to break in but not how to escape. He fights with extraordinary valor "
                "against multiple maharathis who attack him simultaneously in violation of the rules of war. "
                "Abhimanyu's death is one of the most tragic moments of the Mahabharata, showing both the "
                "glory of fearless courage and the horror of adharmic warfare.",
        "meaning": "Abhimanyu's story teaches that true heroism is fighting for dharma even when the odds "
                   "are impossible. His death also shows the consequences when warriors abandon the rules "
                   "of righteous warfare.",
        "topic": "War",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Hanuman's strength/power (additional for ID 77) ---
    {
        "scripture": "Ramayana",
        "chapter": "SundaraKanda",
        "section": "40",
        "verse_number": "narrative_24",
        "reference": "Ramayana — Hanuman's Divine Powers and Strength",
        "text": "Hanuman possesses eight siddhis (supernatural powers) granted by various gods. As the son of "
                "Vayu (the wind god), he can fly, change his size at will, and has immense physical strength. "
                "Yet the secret of Hanuman's shakti (power) is not merely divine birth — it is his complete "
                "devotion to Rama. When Hanuman forgot his powers as a child, the sages told him he would "
                "remember them when needed in service of dharma. This teaches that spiritual power awakens "
                "through selfless service and devotion.",
        "meaning": "Hanuman ji ki shakti ka raaz (the secret of Hanuman's power) is bhakti — pure devotion. "
                   "His eight siddhis, physical strength, and ability to overcome any obstacle all come from "
                   "his love for Lord Rama. Devotion is the source of all true power.",
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_narrative",
    },
    # --- Rama's vanvas (exile) — additional for ID 49 ---
    {
        "scripture": "Ramayana",
        "chapter": "AyodhyaKanda",
        "section": "20",
        "verse_number": "narrative_25",
        "reference": "Ramayana Ayodhya Kanda — Why Rama's Exile Happened",
        "text": "राम का वनवास — Ram ka vanvas kyon hua? King Dasharatha had once promised Queen Kaikeyi two boons "
                "for saving his life in battle. Years later, Manthara poisoned Kaikeyi's mind with jealousy, "
                "and Kaikeyi demanded that Rama be exiled for 14 years and Bharata be crowned king. Rama, "
                "the embodiment of dharma, accepted exile to honour his father's promise. He said: a son's "
                "duty is to fulfil his father's word. Sita and Lakshmana chose to accompany him out of love "
                "and devotion.",
        "meaning": "रामायण में राम का वनवास इसलिए हुआ क्योंकि कैकेयी ने दशरथ से दो वर मांगे। "
                   "Rama's exile happened because Kaikeyi exercised her two boons. Rama accepted exile to "
                   "uphold his father's truth (satya) and demonstrate that dharma requires sacrifice. "
                   "This teaches that honour and duty sometimes mean giving up everything.",
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_narrative",
    },
]


def inject_narratives(verses: List[Dict]) -> int:
    """Add curated narratives to verses list. Returns count of new narratives added."""
    existing_refs = {v.get("reference", "") for v in verses}
    added = 0
    for narrative in CURATED_NARRATIVES:
        if narrative["reference"] in existing_refs:
            logger.info(f"  Skipping (exists): {narrative['reference']}")
            continue
        entry = {
            "id": str(uuid.uuid4()),
            **narrative,
            "language": "en",
        }
        # Remove 'embedding' if present (will be generated in Phase C)
        entry.pop("embedding", None)
        verses.append(entry)
        added += 1
        logger.info(f"  + {narrative['reference']}")
    return added


# ---------------------------------------------------------------------------
# Phase B: Targeted Batch Translation
# ---------------------------------------------------------------------------

def _is_primarily_devanagari(text: str) -> bool:
    if not text:
        return False
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    devanagari = sum(1 for c in chars if '\u0900' <= c <= '\u097F')
    return devanagari / len(chars) > 0.5


def select_verses_for_translation(verses: List[Dict], max_total: int = 1500) -> List[Dict]:
    """Select priority verses for translation from Ramayana & Mahabharata."""
    candidates = []
    for v in verses:
        scripture = (v.get("scripture") or "").lower()
        if scripture not in ("ramayana", "mahabharata"):
            continue
        if v.get("source") == "curated_narrative":
            continue
        # Only translate if meaning is empty
        if v.get("meaning") and not _is_primarily_devanagari(v["meaning"]):
            continue
        candidates.append(v)

    if not candidates:
        return []

    # Priority buckets
    p1, p2, p3 = [], [], []

    # P1 (~500): Key kandas/books
    p1_ramayana_kandas = {"sundarakanda", "ayodhyakanda", "yudhhakanda"}
    p1_ramayana_sargas = {
        "sundarakanda": {"1", "11", "13", "15", "28", "34", "35", "40"},
        "ayodhyakanda": {"2", "4", "16", "19", "20", "24", "72", "109"},
        "yudhhakanda": {"30", "115"},
    }
    p1_mah_books = {"1", "6"}

    # P2 (~500): Opening sargas of each kanda + Mah books 3,5,12,13
    p2_opening_sargas = {"1", "2", "3", "4", "5"}
    p2_mah_books = {"3", "5", "12", "13"}

    for v in candidates:
        scripture = (v.get("scripture") or "").lower()
        chapter = str(v.get("chapter") or "").lower()
        section = str(v.get("section") or "")

        if scripture == "ramayana":
            for kanda, sargas in p1_ramayana_sargas.items():
                if kanda in chapter and section in sargas:
                    p1.append(v)
                    break
            else:
                if any(k in chapter for k in p1_ramayana_kandas):
                    if section in p2_opening_sargas:
                        p2.append(v)
                    else:
                        p3.append(v)
                elif section in p2_opening_sargas:
                    p2.append(v)
                else:
                    p3.append(v)
        elif scripture == "mahabharata":
            if chapter in p1_mah_books:
                p1.append(v)
            elif chapter in p2_mah_books:
                p2.append(v)
            else:
                p3.append(v)

    # Assemble up to max_total
    selected = []
    for bucket in [p1, p2, p3]:
        remaining = max_total - len(selected)
        if remaining <= 0:
            break
        selected.extend(bucket[:remaining])

    logger.info(f"Selected {len(selected)} verses for translation "
                f"(P1={len(p1)}, P2={len(p2)}, P3={len(p3)}, capped at {max_total})")
    return selected


async def batch_translate(verses_to_translate: List[Dict]) -> int:
    """Translate verses using Gemini Flash. Returns count translated."""
    try:
        from google import genai
    except ImportError:
        logger.error("google-genai not available. pip install google-genai")
        return 0

    if not verses_to_translate:
        logger.info("No verses to translate")
        return 0

    # Load checkpoint
    translated_refs = set()
    if CHECKPOINT_PATH.exists():
        try:
            with open(CHECKPOINT_PATH, "r") as f:
                ckpt = json.load(f)
            translated_refs = set(ckpt.get("translated_refs", []))
            logger.info(f"Resuming: {len(translated_refs)} already translated")
        except Exception:
            pass

    remaining = [v for v in verses_to_translate if v.get("reference") not in translated_refs]
    if not remaining:
        logger.info("All selected verses already translated (checkpoint)")
        return 0

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    batch_size = 50
    total_translated = 0
    backoff = 1

    logger.info(f"Translating {len(remaining)} verses in batches of {batch_size}...")

    for batch_start in range(0, len(remaining), batch_size):
        batch = remaining[batch_start:batch_start + batch_size]

        lines = [
            "Translate these Sanskrit/Hindi verses to brief English meaning (1-2 sentences each).",
            "Return ONLY a numbered list. Format: N. translation",
            "Example: 1. The sage asked Narada about the most virtuous person.",
            "",
        ]
        for idx, v in enumerate(batch):
            # Use text field (actual Devanagari), not sanskrit (which is just a digit)
            text = v.get("text") or ""
            if not text or (text.isdigit() and len(text) < 5):
                text = v.get("sanskrit") or ""
            lines.append(f"{idx + 1}. {text[:500]}")

        prompt = "\n".join(lines)

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_FAST_MODEL,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 8192},
            )

            if response.text:
                translations = {}
                for line in response.text.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Match various numbering: "1. text", "1: text", "1) text", "**1.** text"
                    m = re.match(r"^\*{0,2}(\d+)[:\.\)]\*{0,2}\s*(.*)", line)
                    if m:
                        num = int(m.group(1)) - 1
                        trans = m.group(2).strip().strip("*").strip()
                        if trans and len(trans) > 5:
                            translations[num] = trans

                batch_count = 0
                for idx, v in enumerate(batch):
                    if idx in translations and translations[idx]:
                        v["meaning"] = translations[idx]
                        translated_refs.add(v.get("reference", ""))
                        total_translated += 1
                        batch_count += 1

            logger.info(
                f"Batch {batch_start // batch_size + 1}/{(len(remaining) + batch_size - 1) // batch_size}: "
                f"+{batch_count} this batch, {total_translated}/{len(remaining)} total"
            )

            # Save checkpoint
            with open(CHECKPOINT_PATH, "w") as f:
                json.dump({"translated_refs": list(translated_refs), "total": total_translated}, f)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                backoff = min(backoff * 2, 60)
                logger.warning(f"Rate limited, backing off {backoff}s")
            else:
                logger.error(f"Translation batch failed: {e}")

        await asyncio.sleep(backoff)

    logger.info(f"Translation complete: {total_translated} verses translated")
    return total_translated


# ---------------------------------------------------------------------------
# Phase C: Regenerate Embeddings
# ---------------------------------------------------------------------------

def regenerate_embeddings(verses: List[Dict]) -> np.ndarray:
    """Regenerate embeddings for all verses using the same logic as ingest_all_data.py."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not available")
        return np.zeros((len(verses), settings.EMBEDDING_DIM), dtype="float32")

    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    # E5 models require "passage: " prefix for document encoding
    use_prefix = "e5" in settings.EMBEDDING_MODEL.lower()

    texts = []
    for v in verses:
        parts = [v.get("text", ""), v.get("sanskrit", ""), v.get("meaning", "")]
        combined = " ".join(p for p in parts if p).strip().replace("\n", " ")[:1000]
        if use_prefix:
            combined = "passage: " + combined
        texts.append(combined)

    logger.info(f"Generating embeddings for {len(texts)} verses (prefix={'passage' if use_prefix else 'none'})...")
    embeddings = model.encode(
        texts,
        convert_to_tensor=False,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    logger.info(f"Embeddings shape: {embeddings.shape}")
    return embeddings.astype("float32")


def save_data(verses: List[Dict], embeddings: np.ndarray):
    """Save verses.json and embeddings.npy."""
    # Remove any stale 'embedding' keys from verse dicts
    for v in verses:
        v.pop("embedding", None)

    logger.info(f"Saving {len(verses)} verses to {VERSES_PATH}")
    with open(VERSES_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "verses": verses,
                "metadata": {
                    "total_verses": len(verses),
                    "embedding_dim": int(embeddings.shape[1]) if len(embeddings) > 0 else 0,
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "scriptures": sorted(set(v.get("scripture", "Unknown") for v in verses)),
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    logger.info(f"Saving embeddings to {EMBEDDINGS_PATH}")
    np.save(EMBEDDINGS_PATH, embeddings)
    logger.info("Save complete")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Enrich Ramayana & Mahabharata data")
    parser.add_argument("--narratives-only", action="store_true", help="Only inject narratives (no API calls)")
    parser.add_argument("--translate-only", action="store_true", help="Only run translation phase")
    parser.add_argument("--embeddings-only", action="store_true", help="Only regenerate embeddings")
    parser.add_argument("--max-translate", type=int, default=1500, help="Max verses to translate")
    args = parser.parse_args()

    run_all = not (args.narratives_only or args.translate_only or args.embeddings_only)

    # Load existing data
    if not VERSES_PATH.exists():
        logger.error(f"verses.json not found at {VERSES_PATH}. Run ingest_all_data.py first.")
        sys.exit(1)

    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    logger.info(f"Loaded {len(verses)} existing verses")

    # Phase A: Inject narratives
    if run_all or args.narratives_only:
        logger.info("\n" + "=" * 60)
        logger.info("PHASE A: Injecting curated narrative summaries")
        logger.info("=" * 60)
        added = inject_narratives(verses)
        logger.info(f"Added {added} new narrative summaries (total verses: {len(verses)})")

    # Phase B: Translate key verses
    if run_all or args.translate_only:
        logger.info("\n" + "=" * 60)
        logger.info("PHASE B: Translating key Ramayana/Mahabharata verses")
        logger.info("=" * 60)
        to_translate = select_verses_for_translation(verses, max_total=args.max_translate)
        translated = await batch_translate(to_translate)
        logger.info(f"Translated {translated} verses")

    # Phase C: Regenerate embeddings
    if run_all or args.embeddings_only or args.narratives_only:
        logger.info("\n" + "=" * 60)
        logger.info("PHASE C: Regenerating all embeddings")
        logger.info("=" * 60)
        embeddings = regenerate_embeddings(verses)
        save_data(verses, embeddings)
    elif run_all or args.translate_only:
        # After translation, also regen embeddings
        logger.info("\n" + "=" * 60)
        logger.info("PHASE C: Regenerating all embeddings")
        logger.info("=" * 60)
        embeddings = regenerate_embeddings(verses)
        save_data(verses, embeddings)
    else:
        # Just save verse metadata (no embedding regen)
        logger.info("Saving updated verses.json (no embedding regen)...")
        for v in verses:
            v.pop("embedding", None)
        with open(VERSES_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "verses": verses,
                    "metadata": data.get("metadata", {}),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    logger.info("\nDone! Run `python3 tests/retrieval_accuracy_test.py` to verify.")


if __name__ == "__main__":
    asyncio.run(main())
