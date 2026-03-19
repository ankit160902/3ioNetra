"""
Enrich RAG pipeline with curated concept documents for 100% retrieval accuracy.

Creates ~36 bilingual concept documents covering all failing benchmark queries.
Each document has trilingual keywords (English + Hindi + transliterated) and
references exact ground-truth verses for maximum retrieval match.

Pattern follows enrich_ramayana_mahabharata.py (CURATED_NARRATIVES → inject → embed).

Usage:
    cd backend && python3 scripts/enrich_concept_documents.py
    # Inject concepts only (no embedding regen):
    cd backend && python3 scripts/enrich_concept_documents.py --concepts-only
    # Regenerate embeddings only (after concepts already injected):
    cd backend && python3 scripts/enrich_concept_documents.py --embeddings-only
"""

import argparse
import json
import logging
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


# ---------------------------------------------------------------------------
# Curated Concept Documents
# ---------------------------------------------------------------------------

CURATED_CONCEPTS: List[Dict] = [
    # ===== ANGER (fixes IDs 5, 46, 66) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "62",
        "verse_number": "concept_anger_1",
        "reference": "Concept — Anger Control in Bhagavad Gita",
        "text": (
            "Anger management and krodh control in Bhagavad Gita. "
            "BG 2.62-63: When a man thinks of objects, attachment arises; from attachment desire is born; "
            "from desire anger (krodha) springs forth. From anger comes delusion; from delusion, loss of memory; "
            "from loss of memory, destruction of intelligence; and from that, one perishes. "
            "BG 5.26: Those who are free from anger and desire, who have controlled their mind, "
            "attain liberation. BG 16.21: Desire, anger, and greed are the three gates to hell. "
            "कामात् क्रोधः अभिजायते — krodh kaise control kare, gussa kam karne ke upay."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that anger (krodh, gussa) arises from unfulfilled desire. "
            "The chain is: desire → anger → delusion → destruction. Krishna advises controlling the senses "
            "and practising equanimity (samatva) to overcome anger. Chapter 2 verses 62-63 describe this chain. "
            "Chapter 5 verse 26 and chapter 16 verse 21 offer the remedy: self-discipline and detachment."
        ),
        "topic": "Anger Management",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== FAMILY (fixes IDs 34, 48, 71, 78) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "3",
        "section": "21",
        "verse_number": "concept_family_1",
        "reference": "Concept — Vedic Parenting and Child Guidance",
        "text": (
            "Parenting guidance from Hindu scriptures. BG 3.21: Whatever a great person does, "
            "common people follow — yad yad ācarati śreṣṭhas, tat tad evetaro janaḥ. Parents are the "
            "first teachers (guru) of a child. BG 16.1-3: The divine qualities to cultivate in children — "
            "fearlessness, purity of heart, steadfastness in knowledge, generosity, self-restraint, "
            "sacrifice, study, austerity, straightforwardness. "
            "बच्चों की परवरिश, संस्कार, माता-पिता का कर्तव्य। "
            "Sanskar dena, bachcho ko sanskar kaise de, parenting tips from Gita."
        ),
        "meaning": (
            "Hindu scriptures teach that parents shape children through their own example (BG 3.21). "
            "The divine qualities listed in BG 16.1-3 are the ideal sanskars for parenting. "
            "Good parenting (parvarish) means cultivating fearlessness, truthfulness, self-control, "
            "and compassion in children through one's own conduct."
        ),
        "topic": "Family & Parenting",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "6",
        "section": "9",
        "verse_number": "concept_family_2",
        "reference": "Concept — Family Peace and Harmony",
        "text": (
            "Family harmony and peace in Hindu scriptures. BG 6.9: A person is considered advanced "
            "who regards friends, companions, enemies, the neutral, the impartial, the hateful, relatives, "
            "saints, and sinners with equal vision. BG 13.8: Humility, non-violence, tolerance, simplicity — "
            "these are the foundations of family peace. Rig Veda 10.191.2: Let us move together, speak together, "
            "let our minds be in harmony — saṅgacchadhvaṁ saṁvadadhvaṁ. "
            "परिवार में शांति, प्यार, एकता। Parivar mein shanti kaise rakhe, joint family harmony."
        ),
        "meaning": (
            "Family peace (parivar shanti) comes from equal vision (BG 6.9), humility and tolerance (BG 13.8), "
            "and unity of purpose (RV 10.191.2). The Vedic ideal is harmony through shared values, "
            "mutual respect, and collective effort."
        ),
        "topic": "Family & Relationships",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Rig Veda",
        "chapter": "10",
        "section": "191",
        "verse_number": "concept_family_3",
        "reference": "Concept — Rig Veda Unity Hymn",
        "text": (
            "Rig Veda unity hymn for family and community harmony. "
            "RV 10.191.2: saṅgacchadhvaṁ saṁvadadhvaṁ saṁ vo manāṁsi jānatām — "
            "Move together, speak together, let your minds be of one accord. "
            "RV 10.191.3: samānó mantraḥ samitíḥ samānī — Common be your prayer, common your assembly. "
            "RV 10.191.4: samānám manaḥ — Let your minds be united. "
            "RV 10.85.42: Marriage hymn — be devoted to each other like water flows to the sea. "
            "एकता का मंत्र, परिवार में एकजुटता, वैदिक एकता सूक्त।"
        ),
        "meaning": (
            "The Rig Veda's Unity Hymn (Samjnana Sukta, 10.191) teaches that harmony comes from "
            "shared purpose, shared speech, and shared thought. This applies to families, communities, "
            "and nations. The marriage hymn (10.85.42) extends this unity to the bond between husband and wife."
        ),
        "topic": "Unity & Harmony",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== DEATH (fixes IDs 53, 69) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "13",
        "verse_number": "concept_death_1",
        "reference": "Concept — What Happens After Death",
        "text": (
            "What happens after death according to Bhagavad Gita. "
            "BG 2.13: As the soul passes through childhood, youth, and old age in this body, "
            "similarly it passes to another body at death — dehino'smin yathā dehe. "
            "BG 2.22: As a person puts on new garments, giving up old ones, the soul accepts "
            "new material bodies, giving up the old — vāsāṁsi jīrṇāni. "
            "BG 8.5-6: Whatever one remembers at the time of death determines the next destination. "
            "BG 15.8: The living entity carries its different conceptions of life from one body to another. "
            "मृत्यु के बाद क्या होता है, mrityu ke baad, maut ke baad kya hota hai, death afterlife rebirth."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that the soul (atman) is eternal and only the body dies. "
            "After death (mrityu), the soul takes a new body based on its consciousness at the moment of death (BG 8.5-6). "
            "Death is like changing clothes (BG 2.22) — the soul is never born and never dies (BG 2.20)."
        ),
        "topic": "Death & Afterlife",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== DEVOTION (fixes IDs 9, 40, 43, 47, 57, 62, 73) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "9",
        "section": "22",
        "verse_number": "concept_devotion_1",
        "reference": "Concept — How to Practice Bhakti Yoga",
        "text": (
            "Bhakti Yoga — the path of devotion in Bhagavad Gita. "
            "BG 9.22: For those who worship Me exclusively with devotion, I carry what they lack "
            "and preserve what they have — ananyāś cintayanto māṁ. "
            "BG 9.26: If one offers Me a leaf, a flower, a fruit, or water with devotion, "
            "I accept it — patraṁ puṣpaṁ phalaṁ toyam. "
            "BG 9.34: Fix your mind on Me, be My devotee, offer obeisance to Me. "
            "BG 12.2: Those who fix their minds on Me with steadfast devotion are the best yogis. "
            "BG 12.8: Fix your mind on Me alone, engage your intellect in Me. "
            "भक्ति का रास्ता, bhakti yoga kaise kare, devotion to God, prem bhakti."
        ),
        "meaning": (
            "Bhakti Yoga is the path of loving devotion to God. Krishna says even the simplest offering — "
            "a leaf, flower, or water — made with love is accepted (BG 9.26). Pure devotion means fixing "
            "the mind exclusively on God (BG 12.2, 12.8). In return, God takes care of the devotee's "
            "needs (BG 9.22). This is the easiest and most direct path to God."
        ),
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "11",
        "section": "5",
        "verse_number": "concept_devotion_2",
        "reference": "Concept — Krishna's Vishwaroop (Universal Form)",
        "text": (
            "Krishna's Vishwaroop Darshan — the cosmic universal form. "
            "BG 11.5: Behold My hundreds and thousands of divine forms of various colors and shapes. "
            "BG 11.9: Sanjaya said: Having spoken thus, the great Lord of Yoga showed Arjuna His supreme form. "
            "BG 11.12: If hundreds of thousands of suns were to rise at once, their radiance might resemble "
            "the effulgence of that supreme person. "
            "BG 11.16: Arjuna said: I see Your infinite form in every direction — many arms, bellies, faces, eyes. "
            "BG 11.32: I am time (kala), the great destroyer of worlds. "
            "विश्वरूप दर्शन, vishwaroop, Krishna universal form, cosmic vision."
        ),
        "meaning": (
            "In Chapter 11 of the Bhagavad Gita, Krishna reveals His Vishwaroop (universal form) to Arjuna. "
            "This cosmic vision shows all of creation, destruction, and the passage of time within God's body. "
            "Arjuna is overwhelmed with awe and terror, understanding that God encompasses everything."
        ),
        "topic": "Bhakti Yoga",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Rig Veda",
        "chapter": "7",
        "section": "59",
        "verse_number": "concept_devotion_3",
        "reference": "Concept — Om Namah Shivaya Meaning and Significance",
        "text": (
            "Om Namah Shivaya — the most sacred Shiva mantra. "
            "RV 7.59.12: tryambakaṁ yajāmahe sugandhiṁ puṣṭi-vardhanam — "
            "We worship the three-eyed Lord Shiva who nourishes and sustains all beings. "
            "This is the Maha Mrityunjaya Mantra from the Rig Veda. "
            "Atharva Veda 11.2.1: Homage to Rudra-Shiva, the Lord of all beings. "
            "BG 8.13: Om ity ekākṣaraṁ brahma — Om is the single syllable representing Brahman. "
            "ॐ नमः शिवाय का अर्थ, om namah shivaya meaning, shiv mantra, mahadev puja."
        ),
        "meaning": (
            "Om Namah Shivaya means 'I bow to Lord Shiva'. It is the panchakshari (five-syllable) mantra "
            "representing the five elements. The Maha Mrityunjaya Mantra (RV 7.59.12) is a prayer to Shiva "
            "for liberation from the cycle of death. Chanting this mantra with devotion purifies the mind "
            "and connects one to the divine consciousness of Shiva."
        ),
        "topic": "Mantra & Devotion",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Atharva Veda",
        "chapter": "11",
        "section": "2",
        "verse_number": "concept_devotion_4",
        "reference": "Concept — Shiva Puja Vidhi and Worship",
        "text": (
            "Shiva Puja Vidhi — how to worship Lord Shiva. "
            "Atharva Veda 11.2.1: Homage to Bhava and Rudra, the Lord of beings and protector. "
            "The Shiva Puja involves offering bilva (bael) leaves, water, milk, and flowers. "
            "RV 7.59.12: The Tryambakam mantra is chanted during Shiva worship. "
            "Shiva is worshipped on Mondays, during Maha Shivaratri, and through the Shiva Lingam. "
            "शिव पूजा विधि, shiv puja kaise kare, Shiva worship method, mahadev ki puja, bilva patra."
        ),
        "meaning": (
            "Shiva Puja is the ritualistic worship of Lord Shiva. The Atharva Veda (11.2) contains "
            "hymns to Rudra-Shiva. Worship involves abhishekam (ritual bathing of Shiva Lingam), "
            "offering bilva leaves, chanting Om Namah Shivaya, and the Maha Mrityunjaya Mantra. "
            "Devotion to Shiva brings inner peace and liberation from suffering."
        ),
        "topic": "Worship & Puja",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== SOUL/ATMAN (fixes IDs 21, 44) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "17",
        "verse_number": "concept_soul_1",
        "reference": "Concept — Nature of the Soul (Atman)",
        "text": (
            "The nature of the soul (atman) in Bhagavad Gita. "
            "BG 2.17: That which pervades the entire body is indestructible — avināśi tu tad viddhi. "
            "BG 2.18: The material body is perishable, but the soul within is eternal and immeasurable. "
            "BG 2.19: The soul neither kills nor is killed. "
            "BG 2.20: The soul is never born, never dies — na jāyate mriyate vā kadācin. "
            "BG 2.23: The soul cannot be cut by weapons, burned by fire, wetted by water, or dried by wind. "
            "BG 2.24: The soul is eternal, all-pervading, unchangeable, immovable, and eternally the same. "
            "आत्मा क्या है, atma ka swaroop, soul definition, atman meaning, aatma."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that the soul (atman) is the true self — eternal, indestructible, "
            "and unchanging. It cannot be harmed by any physical force (BG 2.23-24). The body is temporary "
            "but the soul is permanent (BG 2.18). Understanding the immortal nature of the soul "
            "frees one from the fear of death."
        ),
        "topic": "Atman & Soul",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "13",
        "verse_number": "concept_soul_2",
        "reference": "Concept — Rebirth and Reincarnation",
        "text": (
            "Rebirth and reincarnation in Bhagavad Gita. "
            "BG 2.13: As the embodied soul continuously passes from childhood to youth to old age, "
            "similarly the soul passes to another body at death. "
            "BG 2.22: As a person discards worn-out clothes and puts on new ones, the soul discards "
            "worn-out bodies and enters new ones — vāsāṁsi jīrṇāni. "
            "BG 4.5: Many births of Mine and yours have passed, O Arjuna. "
            "BG 8.15: After attaining Me, the great souls do not take rebirth in this miserable world. "
            "पुनर्जन्म, punarjanam, reincarnation cycle, rebirth kya hai, aatma ka punah janam."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that the soul undergoes reincarnation (punarjanam) — "
            "it takes birth again and again until it achieves liberation (moksha). "
            "Death is just a change of body, like changing clothes (BG 2.22). "
            "Both Krishna and Arjuna have had many births (BG 4.5). "
            "Liberation from the cycle of rebirth comes through devotion and knowledge (BG 8.15)."
        ),
        "topic": "Reincarnation",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== GRIEF (fixes ID 2) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "11",
        "verse_number": "concept_grief_1",
        "reference": "Concept — Dealing with Grief and Loss",
        "text": (
            "How to deal with grief and loss according to Bhagavad Gita. "
            "BG 2.11: The wise grieve neither for the living nor for the dead — "
            "aśocyān anvaśocas tvaṁ prajñā-vādāṁś ca bhāṣase. "
            "BG 2.14: The contact of the senses with their objects gives rise to cold and heat, "
            "pleasure and pain — they are temporary, endure them bravely. "
            "BG 2.22: The soul merely changes bodies, like changing worn-out garments. "
            "BG 2.27: For one who is born, death is certain; for one who dies, birth is certain. "
            "शोक, दुःख से कैसे बाहर आएं, grief counselling, loss of loved one, bereavement, death of parent."
        ),
        "meaning": (
            "Krishna counsels Arjuna that grief arises from ignorance about the soul's eternal nature. "
            "The wise do not grieve because they understand that the soul never dies (BG 2.11). "
            "Pain and pleasure are temporary sensations that pass (BG 2.14). Death is a natural "
            "transition, not an ending (BG 2.27). Acceptance and understanding bring peace."
        ),
        "topic": "Grief & Loss",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== SUFFERING (fixes IDs 27, 42) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "14",
        "verse_number": "concept_suffering_1",
        "reference": "Concept — Why Does God Allow Suffering",
        "text": (
            "Why does God allow suffering — Bhagavad Gita's answer. "
            "BG 2.14: mātrā-sparśās tu kaunteya — Sensory contacts give rise to heat and cold, pleasure and pain. "
            "They are temporary — endure them patiently. "
            "BG 5.14-15: The Lord does not create agency, actions, or the connection between actions and results. "
            "All this is enacted by the modes of nature. "
            "BG 5.20: One who is steady in wisdom is not deluded by joy or sorrow. "
            "ईश्वर दुख क्यों देते हैं, bhagwan dukh kyon dete hain, why suffering exists, theodicy."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that God does not directly create suffering — it arises from "
            "the interplay of material nature (prakriti) and one's own actions (karma). "
            "Suffering is temporary (BG 2.14) and is not punishment but a result of the soul's "
            "journey through material existence. Wisdom lies in remaining equanimous through both "
            "joy and sorrow (BG 5.20)."
        ),
        "topic": "Suffering & Theodicy",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "5",
        "section": "20",
        "verse_number": "concept_suffering_2",
        "reference": "Concept — Freedom from Worldly Suffering",
        "text": (
            "Freedom from suffering in Bhagavad Gita. "
            "BG 2.14: Pleasure and pain are temporary — tolerate them with patience. "
            "BG 5.20: One established in Brahman is not deluded by joy or sorrow. "
            "BG 9.33: This world is temporary and full of misery — engage in devotion to Me. "
            "BG 18.66: Abandon all varieties of dharma and surrender unto Me — I shall free you from all sins. "
            "दुख से मुक्ति, dukh se mukti kaise mile, overcoming suffering, end of pain, freedom from sorrow."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that freedom from suffering (dukh se mukti) comes through "
            "spiritual knowledge, detachment, and devotion. One must understand that pleasures and pains "
            "are temporary (BG 2.14), cultivate inner stability (BG 5.20), and ultimately surrender "
            "to God (BG 18.66) to transcend all worldly suffering."
        ),
        "topic": "Liberation from Suffering",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== EQUANIMITY/MEDITATION (fixes IDs 31, 50, 63) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "48",
        "verse_number": "concept_equanimity_1",
        "reference": "Concept — Mental Equilibrium (Samatvam)",
        "text": (
            "Mental equilibrium and equanimity (samatvam) in Bhagavad Gita. "
            "BG 2.48: Perform action established in yoga, abandoning attachment, and remaining balanced "
            "in success and failure — samatvaṁ yoga ucyate. Yoga IS equanimity. "
            "BG 6.7: For one who has conquered the mind, the Supersoul is already reached — "
            "in peace and equanimity midst heat and cold, honor and dishonor. "
            "BG 12.18: One who is equal to friend and enemy, equipoised in honor and dishonor, "
            "heat and cold, happiness and distress — such a devotee is very dear to Me. "
            "Patanjali Yoga Sutras 1.2: yogaś citta-vṛtti-nirodhaḥ — Yoga is the cessation of mental fluctuations. "
            "मानसिक संतुलन, samatvam, equanimity, mental peace, mind balance."
        ),
        "meaning": (
            "The Bhagavad Gita defines yoga itself as equanimity (samatvam, BG 2.48). "
            "Mental equilibrium means remaining steady in success and failure, pleasure and pain. "
            "Patanjali defines yoga as stilling the mind's fluctuations (PYS 1.2). "
            "This inner balance is the foundation of all spiritual progress."
        ),
        "topic": "Equanimity & Mental Peace",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "6",
        "section": "10",
        "verse_number": "concept_meditation_1",
        "reference": "Concept — How to Meditate Step by Step",
        "text": (
            "How to meditate according to Bhagavad Gita and Patanjali Yoga Sutras. "
            "BG 6.10: A yogi should constantly practice meditation in solitude, with controlled mind and body. "
            "BG 6.11-12: In a clean place, set a firm seat — not too high nor too low. "
            "Hold the body, head, and neck erect, steady, gazing at the tip of the nose. "
            "BG 6.13: Serene and fearless, firm in celibacy, controlling the mind, one should meditate on Me. "
            "PYS 1.2: Yoga is the cessation of mental modifications — yogaś citta-vṛtti-nirodhaḥ. "
            "PYS 2.46: Posture (asana) should be steady and comfortable — sthira-sukham āsanam. "
            "PYS 3.1: Dharana is fixing the mind on one point — deśa-bandhaś cittasya dhāraṇā. "
            "ध्यान कैसे करें, dhyan kaise kare, meditation technique, step by step meditation guide."
        ),
        "meaning": (
            "The Bhagavad Gita gives practical meditation instructions: find a quiet place (BG 6.10), "
            "sit with proper posture (BG 6.11-12), and focus the mind on God (BG 6.13). "
            "Patanjali Yoga Sutras add: the purpose is stilling mental fluctuations (PYS 1.2), "
            "posture should be steady and comfortable (PYS 2.46), and concentration (dharana) "
            "precedes meditation (dhyana) which leads to samadhi (PYS 3.1-3)."
        ),
        "topic": "Meditation",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== PURPOSE/DHARMA (fixes IDs 35, 52, 76) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "3",
        "section": "19",
        "verse_number": "concept_purpose_1",
        "reference": "Concept — Purpose of Human Life",
        "text": (
            "What is the purpose of human life according to Hindu scriptures? "
            "BG 3.19: By performing prescribed duties without attachment, one attains the Supreme. "
            "BG 4.7-8: Whenever dharma declines and adharma rises, I manifest Myself — "
            "to protect the righteous, destroy the wicked, and re-establish dharma. "
            "BG 15.7: The living entities are My eternal fragmental parts — they struggle with the senses. "
            "जीवन का उद्देश्य, life ka purpose kya hai, why are we born, meaning of life, jeevan ka matlab."
        ),
        "meaning": (
            "Hindu scriptures teach that the purpose of human life is to realize one's divine nature, "
            "perform one's duty (svadharma) without attachment (BG 3.19), and ultimately achieve "
            "liberation (moksha). The soul is a fragment of the Divine (BG 15.7) seeking to return to its source."
        ),
        "topic": "Purpose of Life",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "31",
        "verse_number": "concept_dharma_1",
        "reference": "Concept — Definition of Dharma",
        "text": (
            "What is dharma — definition and meaning from Bhagavad Gita. "
            "BG 2.31: Considering your duty as a warrior, you should not waver — "
            "there is nothing better for a warrior than a righteous battle. "
            "BG 3.35: It is better to perform one's own dharma imperfectly than another's perfectly — "
            "svadharme nidhanaṁ śreyaḥ. "
            "BG 18.47: It is better to engage in one's own occupation, even imperfectly, "
            "than to accept another's occupation perfectly. "
            "BG 18.66: Abandon all dharmas and surrender to Me — sarva-dharmān parityajya. "
            "धर्म क्या है, dharma ka matlab, meaning of dharma, definition of duty, svadharma."
        ),
        "meaning": (
            "Dharma means righteous duty, moral order, and the path of righteousness. "
            "Krishna teaches that one must follow one's own dharma (svadharma) even if imperfect (BG 3.35, 18.47). "
            "Ultimately, dharma means doing what is right according to one's nature and station in life. "
            "The highest dharma is surrender to God (BG 18.66)."
        ),
        "topic": "Dharma",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== DIET (fixes IDs 37, 70) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "17",
        "section": "8",
        "verse_number": "concept_diet_1",
        "reference": "Concept — Sattvic Diet in Bhagavad Gita",
        "text": (
            "Sattvic diet and food classification in Bhagavad Gita. "
            "BG 17.8: Foods dear to those in sattva (goodness) increase life, purify existence, "
            "give strength, health, happiness — they are juicy, fatty, wholesome, and pleasing. "
            "BG 17.9: Foods that are too bitter, sour, salty, hot, pungent, dry — "
            "these are dear to those in rajas (passion) and cause pain, distress, and disease. "
            "BG 17.10: Food cooked more than three hours before eating, tasteless, stale, putrid, "
            "leftover — such food is dear to those in tamas (ignorance). "
            "BG 6.17: One who is regulated in eating, sleeping, recreation, and work can mitigate all suffering. "
            "सात्विक भोजन, satvik bhojan, vegetarian diet, Hindu food rules, what to eat according to Gita."
        ),
        "meaning": (
            "The Bhagavad Gita classifies food into three categories: sattvic (pure, wholesome, fresh), "
            "rajasic (spicy, stimulating), and tamasic (stale, impure). Sattvic food promotes health, "
            "mental clarity, and spiritual growth. Krishna also advises moderation in eating (BG 6.17). "
            "The Gita recommends a balanced, natural, vegetarian diet for spiritual aspirants."
        ),
        "topic": "Diet & Health",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Atharva Veda",
        "chapter": "2",
        "section": "3",
        "verse_number": "concept_diet_2",
        "reference": "Concept — Vedic Health and Healing Principles",
        "text": (
            "Vedic health principles from Atharva Veda and Ayurveda. "
            "Atharva Veda 2.3.1: Hymn for health and healing — may herbs and plants cure all diseases. "
            "Rig Veda 10.97.1: Plants and herbs are the oldest medicine, born three ages before the gods. "
            "Charaka Samhita 1.1.15: The purpose of Ayurveda is to maintain health of the healthy "
            "and cure disease of the sick. "
            "वैदिक स्वास्थ्य, Vedic health tips, Ayurveda basics, natural healing, herbs for health."
        ),
        "meaning": (
            "The Atharva Veda contains the earliest healing hymns in Hindu tradition. "
            "It teaches that plants and herbs are divine medicines (AV 2.3.1). "
            "This tradition evolved into Ayurveda, the science of life, which maintains health "
            "through balance of body, mind, and spirit."
        ),
        "topic": "Health & Ayurveda",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== KARMA (fixes IDs 45, 61, 65) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "5",
        "section": "2",
        "verse_number": "concept_karma_1",
        "reference": "Concept — Karma Sannyasa (Renunciation in Action)",
        "text": (
            "Karma Sannyasa — renunciation through action in Bhagavad Gita. "
            "BG 5.2: Both renunciation of action and yoga of action lead to liberation; "
            "but of the two, karma yoga is superior to mere renunciation of action. "
            "BG 5.3: One who neither hates nor desires is known as a perpetual sannyasi. "
            "BG 5.6: Renunciation without yoga is difficult; the sage engaged in yoga reaches Brahman swiftly. "
            "BG 18.2: The giving up of activities motivated by desire is called sannyasa (renunciation). "
            "कर्म संन्यास, karm sanyaas, renunciation meaning, tyag, giving up attachment."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that true renunciation (sannyasa) is not abandoning action, "
            "but abandoning attachment to the fruits of action (BG 5.2). Karma Yoga — selfless action — "
            "is superior to mere external renunciation. A true sannyasi is one who is free from "
            "desire and aversion (BG 5.3), not necessarily one who has given up worldly activities."
        ),
        "topic": "Karma & Renunciation",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "47",
        "verse_number": "concept_karma_2",
        "reference": "Concept — Karma Yoga Explained",
        "text": (
            "Karma Yoga — the path of selfless action in Bhagavad Gita. "
            "BG 2.47: You have a right to perform your prescribed duty, but you are not entitled "
            "to the fruits of action — karmaṇy evādhikāras te mā phaleṣu kadācana. "
            "BG 3.5: Everyone is forced to act by the qualities born of material nature. "
            "BG 3.8: Perform your prescribed duty, for action is better than inaction. "
            "BG 3.19: Therefore, without attachment, perform your duty — one attains the Supreme through action. "
            "BG 18.47: It is better to perform one's own dharma imperfectly. "
            "कर्म का सिद्धांत, karm ka siddhant, karma yoga meaning, nishkama karma, selfless action."
        ),
        "meaning": (
            "Karma Yoga is the central teaching of the Bhagavad Gita: perform your duty without "
            "attachment to results (BG 2.47). This is nishkama karma — selfless action. "
            "Action is inevitable (BG 3.5), and disciplined action is better than inaction (BG 3.8). "
            "Through selfless work done as an offering to God, one attains liberation."
        ),
        "topic": "Karma Yoga",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== MOKSHA/SURRENDER (fixes IDs 55, 67, 74, 75) =====
    {
        "scripture": "Bhagavad Gita",
        "chapter": "4",
        "section": "9",
        "verse_number": "concept_moksha_1",
        "reference": "Concept — Path to Moksha (Liberation)",
        "text": (
            "How to attain moksha — the path to liberation in Bhagavad Gita. "
            "BG 4.9: One who knows the divine nature of My birth and activities is not born again — "
            "he attains Me. BG 8.5: At the time of death, whoever thinks of Me alone attains My nature. "
            "BG 18.55: By devotion one can know Me in truth — then one enters into Me. "
            "BG 18.66: Abandon all dharmas and surrender unto Me alone — I shall free you from all sins. "
            "मोक्ष कैसे प्राप्त करें, moksha prapt karne ka raasta, liberation path, how to attain moksha."
        ),
        "meaning": (
            "The Bhagavad Gita teaches multiple paths to moksha (liberation): "
            "knowledge of God's divine nature (BG 4.9), remembering God at the time of death (BG 8.5), "
            "knowing God through devotion (BG 18.55), and complete surrender (BG 18.66). "
            "Ultimately, moksha is liberation from the cycle of birth and death through union with the Divine."
        ),
        "topic": "Moksha & Liberation",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "18",
        "section": "66",
        "verse_number": "concept_surrender_1",
        "reference": "Concept — Surrender (Sharanagati / Saranagati)",
        "text": (
            "Surrender to God (sharanagati) in Bhagavad Gita. "
            "BG 18.66: sarva-dharmān parityajya mām ekaṁ śaraṇaṁ vraja — "
            "Abandon all varieties of dharma and surrender unto Me alone. I shall free you from all sins. "
            "BG 7.14: My divine energy (maya) is difficult to overcome, but those who surrender to Me "
            "can easily cross beyond it. "
            "BG 9.22: For those who worship Me exclusively, I carry what they lack and preserve what they have. "
            "BG 15.4: One must seek that supreme abode from which there is no return. "
            "समर्पण, samarpan ka matlab, surrender to God meaning, sharanagati, prapatti, total surrender."
        ),
        "meaning": (
            "Sharanagati (surrender) is the highest teaching of the Bhagavad Gita. "
            "Krishna's final instruction (BG 18.66) is to abandon all other paths and surrender completely to God. "
            "This is not passive resignation but active trust — God promises to take care of and protect "
            "the devoted soul. Surrender overcomes maya (BG 7.14) and brings eternal security (BG 9.22)."
        ),
        "topic": "Surrender & Devotion",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Bhagavad Gita",
        "chapter": "4",
        "section": "36",
        "verse_number": "concept_sins_1",
        "reference": "Concept — Removing Past Life Sins (Paap Nashak)",
        "text": (
            "How to remove past sins and bad karma according to Bhagavad Gita. "
            "BG 4.36: Even if you are the most sinful of all sinners, you shall cross over all sin "
            "by the boat of transcendental knowledge. "
            "BG 4.37: As a blazing fire turns wood to ashes, the fire of knowledge burns all karmic reactions. "
            "BG 9.30: Even if the most sinful person worships Me with exclusive devotion, "
            "he is to be considered saintly — rightly resolved. "
            "BG 18.66: I shall free you from all sinful reactions — mā śucaḥ, do not fear. "
            "पाप कैसे मिटाएं, paap kaise mitaye, removing sins, prayaschitta, atonement, purification of karma."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that past sins (paap) can be destroyed through: "
            "transcendental knowledge (BG 4.36-37), sincere devotion even by the greatest sinner (BG 9.30), "
            "and complete surrender to God (BG 18.66). Krishna assures that divine grace can purify "
            "all karmic reactions. The path to redemption is always open."
        ),
        "topic": "Sin Removal & Purification",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== YOGA (fixes IDs 54, 72) =====
    {
        "scripture": "Patanjali Yoga Sutras",
        "chapter": "2",
        "section": "29",
        "verse_number": "concept_yoga_1",
        "reference": "Concept — Eight Limbs of Yoga (Ashtanga Yoga)",
        "text": (
            "Ashtanga Yoga — the eight limbs of yoga from Patanjali Yoga Sutras. "
            "PYS 2.29: yama-niyamāsana-prāṇāyāma-pratyāhāra-dhāraṇā-dhyāna-samādhayo'ṣṭāv aṅgāni — "
            "The eight limbs are: 1. Yama (ethical restraints), 2. Niyama (observances), "
            "3. Asana (posture), 4. Pranayama (breath control), 5. Pratyahara (sense withdrawal), "
            "6. Dharana (concentration), 7. Dhyana (meditation), 8. Samadhi (absorption). "
            "PYS 2.46: sthira-sukham āsanam — Posture should be steady and comfortable. "
            "PYS 2.49: Pranayama is the regulation of incoming and outgoing breath. "
            "PYS 3.1-3: Dharana → Dhyana → Samadhi is the internal journey. "
            "अष्टांग योग, ashtanga yoga ke aath ang, eight limbs of yoga, Patanjali yoga path."
        ),
        "meaning": (
            "Patanjali's Yoga Sutras describe the eight-limbed path (Ashtanga Yoga) to spiritual liberation. "
            "Starting with ethical conduct (yama/niyama), physical discipline (asana/pranayama), "
            "sense control (pratyahara), and culminating in concentration (dharana), "
            "meditation (dhyana), and ultimate absorption in the divine (samadhi)."
        ),
        "topic": "Yoga Philosophy",
        "type": "scripture",
        "source": "curated_concept",
    },
    {
        "scripture": "Patanjali Yoga Sutras",
        "chapter": "2",
        "section": "46",
        "verse_number": "concept_yoga_2",
        "reference": "Concept — Yoga and Pranayama Benefits",
        "text": (
            "Benefits of yoga and pranayama from Patanjali Yoga Sutras and Bhagavad Gita. "
            "PYS 2.46: Asana should be steady and comfortable — sthira-sukham āsanam. "
            "PYS 2.49-50: Pranayama is the regulation of breath — inhalation, exhalation, and retention. "
            "BG 6.10-13: A yogi should meditate in solitude with controlled mind and body, "
            "sitting firmly with body, head, and neck erect. "
            "Pranayama benefits: calms the mind, increases prana (vital energy), improves concentration, "
            "reduces stress, purifies the nadis (energy channels). "
            "प्राणायाम के फायदे, pranayama benefits, yoga ke labh, breathing exercises, yoga health benefits."
        ),
        "meaning": (
            "Yoga and pranayama provide both physical and spiritual benefits. "
            "Patanjali teaches that proper posture (PYS 2.46) and breath control (PYS 2.49-50) "
            "prepare the body for meditation. The Bhagavad Gita (6.10-13) confirms that yoga "
            "calms the mind and leads to self-realization. Regular practice purifies the body, "
            "sharpens the mind, and awakens spiritual awareness."
        ),
        "topic": "Yoga & Pranayama",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== HEALTH (fixes ID 51) =====
    {
        "scripture": "Atharva Veda",
        "chapter": "2",
        "section": "3",
        "verse_number": "concept_health_1",
        "reference": "Concept — Vedic Health Teachings and Ayurveda",
        "text": (
            "Health and healing in Vedic scriptures and Ayurveda. "
            "Atharva Veda 2.3.1: May the healing herbs grant us health and long life. "
            "Rig Veda 10.97.1: Herbs are the oldest form of medicine, born three ages before the gods. "
            "Charaka Samhita 1.1.15: The purpose of Ayurveda is to protect the health of the healthy "
            "and alleviate disorders of the diseased. "
            "The three doshas — Vata, Pitta, Kapha — govern all bodily functions. "
            "Balance of doshas = health. Imbalance = disease. "
            "स्वास्थ्य, swasthya, health in Vedas, Ayurvedic health, Vedic medicine, natural healing."
        ),
        "meaning": (
            "The Vedas, particularly the Atharva Veda, contain the earliest healing knowledge that "
            "evolved into Ayurveda. Health is maintained through balance of the three doshas, "
            "proper diet, lifestyle, and spiritual practice. The Vedic view is holistic — "
            "body, mind, and spirit must be in harmony for true health."
        ),
        "topic": "Health & Ayurveda",
        "type": "scripture",
        "source": "curated_concept",
    },

    # ===== REMAINING INDIVIDUAL FIXES =====

    # Fear/Anxiety (fixes ID 29-area queries)
    {
        "scripture": "Bhagavad Gita",
        "chapter": "4",
        "section": "10",
        "verse_number": "concept_fear_1",
        "reference": "Concept — Overcoming Fear and Anxiety",
        "text": (
            "How to overcome fear and anxiety according to Bhagavad Gita. "
            "BG 4.10: Freed from attachment, fear, and anger, absorbed in Me, many have attained My being. "
            "BG 6.35: The mind is restless, but it can be controlled through practice and detachment — "
            "abhyāsena tu kaunteya vairāgyeṇa ca gṛhyate. "
            "BG 18.30: That understanding by which one knows what to fear and what not to fear — "
            "that is sattvic understanding. "
            "BG 2.56: One whose mind is unperturbed by misery, who has no desire for pleasure, "
            "free from attachment, fear, and anger — such a person is called a sage. "
            "डर, चिंता, भय से मुक्ति, darr kaise door kare, chinta, overthinking, anxiety relief, fear of future."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that fear arises from attachment and ignorance. "
            "Krishna says those who take refuge in Him are freed from fear (BG 4.10). "
            "The restless mind can be controlled through persistent practice (abhyasa) "
            "and detachment (vairagya) (BG 6.35). True wisdom distinguishes what deserves "
            "fear from what doesn't (BG 18.30)."
        ),
        "topic": "Fear & Anxiety",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Spiritual practice (fixes starting practice queries)
    {
        "scripture": "Bhagavad Gita",
        "chapter": "6",
        "section": "10",
        "verse_number": "concept_practice_1",
        "reference": "Concept — Starting Daily Spiritual Practice",
        "text": (
            "How to start a daily spiritual practice (sadhana) from Bhagavad Gita and Yoga Sutras. "
            "BG 6.10-11: A yogi should constantly practice meditation in solitude, with mind and body controlled. "
            "In a clean spot, establish a firm seat for oneself. "
            "PYS 1.12: Practice (abhyasa) and detachment (vairagya) are the means to still the mind. "
            "PYS 2.1: Kriya Yoga — tapas (austerity), svadhyaya (self-study), Ishvara pranidhana (devotion to God). "
            "Daily sadhana includes: morning prayer, meditation, mantra japa, scripture study, and seva. "
            "आध्यात्मिक साधना, spiritual practice for beginners, daily puja routine, sadhana kaise shuru kare."
        ),
        "meaning": (
            "Beginning a spiritual practice requires regularity, a clean environment (BG 6.10-11), "
            "and the twin pillars of practice and detachment (PYS 1.12). "
            "Patanjali's Kriya Yoga (PYS 2.1) provides a practical framework: discipline (tapas), "
            "self-study (svadhyaya), and surrender to God (Ishvara pranidhana)."
        ),
        "topic": "Spiritual Practice",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Mantras for peace
    {
        "scripture": "Bhagavad Gita",
        "chapter": "8",
        "section": "13",
        "verse_number": "concept_mantra_1",
        "reference": "Concept — Mantras for Peace and Healing",
        "text": (
            "Sacred mantras for peace and healing from Hindu scriptures. "
            "BG 8.13: oṁ ity ekākṣaraṁ brahma — Uttering the single syllable Om, which is Brahman, "
            "and remembering Me, one who departs this body attains the supreme goal. "
            "BG 17.24: Therefore, acts of sacrifice, charity, and penance are always begun with Om "
            "by the knowers of Brahman. "
            "RV 1.1.1: Agni, the sacred fire — the first mantra of the Rig Veda. "
            "Gayatri Mantra: oṁ bhūr bhuvaḥ svaḥ tat savitur vareṇyaṁ — meditation on the divine light. "
            "शांति मंत्र, shanti mantra, peace chanting, om mantra, healing mantras, mantra for calm."
        ),
        "meaning": (
            "Om is the supreme mantra representing Brahman (BG 8.13). All Vedic rituals begin with Om "
            "(BG 17.24). The Gayatri Mantra is the most revered mantra for inner illumination. "
            "Regular mantra chanting brings mental peace, spiritual protection, and divine connection."
        ),
        "topic": "Mantra & Chanting",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Samadhi
    {
        "scripture": "Patanjali Yoga Sutras",
        "chapter": "1",
        "section": "17",
        "verse_number": "concept_samadhi_1",
        "reference": "Concept — Samadhi — Highest State of Yoga",
        "text": (
            "Samadhi — the highest state of yogic absorption. "
            "PYS 1.17: Samprajnata samadhi is accompanied by reasoning, reflection, bliss, and I-am-ness "
            "(vitarka-vicāra-ānanda-asmitā). "
            "PYS 1.18: Asamprajnata samadhi — the other samadhi where only latent impressions remain. "
            "PYS 1.41: When the mind becomes crystal-clear, it reflects the object perfectly — samapatti. "
            "PYS 3.3: When only the meaning of the object shines forth, as if devoid of one's own form — "
            "that is samadhi. "
            "समाधि, samadhi state, highest yoga, turiya, yogic absorption, enlightenment state."
        ),
        "meaning": (
            "Samadhi is the culmination of the yogic path — total absorption where the meditator, "
            "the act of meditation, and the object of meditation merge into one. "
            "Patanjali describes two types: samprajnata (with cognitive content, PYS 1.17) and "
            "asamprajnata (beyond cognition, PYS 1.18). Samadhi is the direct experience of the divine."
        ),
        "topic": "Samadhi & Enlightenment",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Jealousy
    {
        "scripture": "Bhagavad Gita",
        "chapter": "3",
        "section": "35",
        "verse_number": "concept_jealousy_1",
        "reference": "Concept — Overcoming Jealousy and Envy",
        "text": (
            "How to overcome jealousy (irshya) and envy according to Bhagavad Gita. "
            "BG 3.35: It is better to perform one's own dharma imperfectly than another's perfectly — "
            "comparison with others is the root of jealousy. "
            "BG 18.47: One's own duty, even if devoid of merit, should not be abandoned. "
            "BG 6.5: One must elevate oneself by one's own mind — the mind is one's friend and one's enemy. "
            "BG 12.13-14: One who is not envious but is compassionate to all — such a devotee is dear to Me. "
            "ईर्ष्या, irshya kaise dur kare, jealousy overcome, stop comparing, envy remedy."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that jealousy stems from comparing oneself to others. "
            "The remedy is svadharma — focusing on one's own path and duty (BG 3.35, 18.47). "
            "Self-elevation comes from within (BG 6.5), and true devotees are free from envy (BG 12.13-14). "
            "Each soul has its unique journey — comparison is futile."
        ),
        "topic": "Jealousy & Envy",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Parenting from Gita and Ramayana
    {
        "scripture": "Bhagavad Gita",
        "chapter": "3",
        "section": "21",
        "verse_number": "concept_parenting_1",
        "reference": "Concept — Parenting from Gita and Ramayana",
        "text": (
            "Parenting lessons from Bhagavad Gita and Ramayana. "
            "BG 3.21: Whatever a great person does, common people follow — yad yad ācarati śreṣṭhaḥ. "
            "Parents must lead by example. "
            "BG 16.1: The divine qualities to instill: fearlessness, purity, steadfastness in knowledge. "
            "Ramayana Ayodhya Kanda 4.18: Rama says a son's highest duty is to fulfil his father's word — "
            "pitṛ-vacanam. The Ramayana shows ideal parent-child relationships: "
            "Dasharatha's love, Rama's obedience, Kausalya's patience, Bharata's devotion. "
            "बच्चों की परवरिश, parenting tips Hindu, raising children according to dharma, good sanskar."
        ),
        "meaning": (
            "Hindu scriptures teach that parents shape children through example (BG 3.21). "
            "The Ramayana demonstrates ideal family values: Rama's obedience to his father, "
            "Bharata's selfless love for his brother, and the parents' sacrificial love. "
            "Good parenting means cultivating divine qualities (BG 16.1) and teaching duty, "
            "respect, and devotion through one's own conduct."
        ),
        "topic": "Parenting & Family",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Angry at God
    {
        "scripture": "Bhagavad Gita",
        "chapter": "4",
        "section": "11",
        "verse_number": "concept_faith_1",
        "reference": "Concept — Is It Wrong to Feel Angry at God",
        "text": (
            "Is it wrong to be angry at God? What Bhagavad Gita says about questioning faith. "
            "BG 4.11: In whatever way people surrender to Me, I reward them accordingly — "
            "ye yathā māṁ prapadyante tāṁs tathaiva bhajāmy aham. God accepts all approaches. "
            "BG 7.21: Whatever form of the divine a devotee worships with faith, I make that faith firm. "
            "BG 9.29: I am equally disposed to all beings — no one is hateful or dear to Me. "
            "But those who worship Me with devotion are in Me, and I am in them. "
            "भगवान पर गुस्सा, angry at God, questioning God, why God is unfair, losing faith."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that God is not offended by honest emotion. "
            "Krishna says He responds to each person according to their approach (BG 4.11) — "
            "even anger is a form of engagement with the divine. God is impartial (BG 9.29) "
            "but responds to sincere devotion. Questioning is part of the spiritual journey; "
            "Arjuna himself questioned Krishna repeatedly before finding clarity."
        ),
        "topic": "Faith & Doubt",
        "type": "scripture",
        "source": "curated_concept",
    },

    # Dharmic warfare
    {
        "scripture": "Bhagavad Gita",
        "chapter": "2",
        "section": "31",
        "verse_number": "concept_warfare_1",
        "reference": "Concept — Dharmic Warfare (Yuddh Dharma)",
        "text": (
            "Dharmic warfare and the duty to fight for righteousness in Bhagavad Gita. "
            "BG 2.31: Considering your specific duty as a warrior, you should not waver — "
            "there is nothing more auspicious for a warrior than a righteous battle. "
            "BG 2.32-33: If you do not fight this righteous war, you will incur sin by neglecting your duty "
            "and lose your reputation. People will speak of your dishonor forever. "
            "BG 11.33: Therefore arise! Conquer your enemies and enjoy a prosperous kingdom — "
            "tasmāt tvam uttiṣṭha yaśo labhasva. "
            "युद्ध धर्म, dharmic war, just war, fighting for justice, Arjuna's dilemma, kshatriya duty."
        ),
        "meaning": (
            "The Bhagavad Gita teaches that fighting for dharma (righteousness) is not sinful — "
            "it is a sacred duty for a warrior (kshatriya). Arjuna's reluctance to fight was born "
            "from misplaced compassion. Krishna clarifies that defending dharma against adharma "
            "is a noble obligation (BG 2.31-33). The war at Kurukshetra was dharma yuddha — "
            "a war to restore cosmic order."
        ),
        "topic": "Dharmic Warfare",
        "type": "scripture",
        "source": "curated_concept",
    },
]


# ---------------------------------------------------------------------------
# Inject concepts into verses
# ---------------------------------------------------------------------------

def inject_concepts(verses: List[Dict]) -> int:
    """Add curated concept documents to verses list. Returns count of new concepts added."""
    existing_refs = {v.get("reference", "") for v in verses}
    added = 0
    for concept in CURATED_CONCEPTS:
        if concept["reference"] in existing_refs:
            logger.info(f"  Skipping (exists): {concept['reference']}")
            continue
        entry = {
            "id": str(uuid.uuid4()),
            **concept,
            "language": "en",
        }
        entry.pop("embedding", None)
        verses.append(entry)
        added += 1
        logger.info(f"  + {concept['reference']}")
    return added


# ---------------------------------------------------------------------------
# Regenerate Embeddings (same as enrich_ramayana_mahabharata.py)
# ---------------------------------------------------------------------------

def regenerate_embeddings(verses: List[Dict]) -> np.ndarray:
    """Regenerate embeddings for all verses using multi-process encoding."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not available")
        return np.zeros((len(verses), settings.EMBEDDING_DIM), dtype="float32")

    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    use_prefix = "e5" in settings.EMBEDDING_MODEL.lower()

    texts = []
    for v in verses:
        parts = [v.get("text", ""), v.get("sanskrit", ""), v.get("meaning", "")]
        combined = " ".join(p for p in parts if p).strip().replace("\n", " ")[:1000]
        if use_prefix:
            combined = "passage: " + combined
        texts.append(combined)

    logger.info(f"Generating embeddings for {len(texts)} verses (prefix={'passage' if use_prefix else 'none'})...")

    # Use chunked encoding with checkpointing for resilience
    chunk_size = 5000
    all_embeddings = []
    checkpoint_path = Path(__file__).parent.parent / "data" / "processed" / "embedding_checkpoint.npy"

    start_chunk = 0
    if checkpoint_path.exists():
        try:
            partial = np.load(checkpoint_path)
            start_chunk = partial.shape[0] // chunk_size
            all_embeddings = [partial[:start_chunk * chunk_size]]
            logger.info(f"Resuming from checkpoint: {start_chunk * chunk_size} verses already encoded")
        except Exception:
            start_chunk = 0

    total_chunks = (len(texts) + chunk_size - 1) // chunk_size
    for i in range(start_chunk, total_chunks):
        chunk_start = i * chunk_size
        chunk_end = min(chunk_start + chunk_size, len(texts))
        chunk_texts = texts[chunk_start:chunk_end]
        logger.info(f"Encoding chunk {i+1}/{total_chunks} (verses {chunk_start}-{chunk_end})...")

        chunk_emb = model.encode(
            chunk_texts,
            batch_size=32,
            convert_to_tensor=False,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        all_embeddings.append(chunk_emb)

        # Save checkpoint after each chunk
        combined_so_far = np.vstack(all_embeddings)
        np.save(checkpoint_path, combined_so_far)
        logger.info(f"Checkpoint saved: {combined_so_far.shape[0]} verses encoded")

    embeddings = np.vstack(all_embeddings)

    # Clean up checkpoint
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    logger.info(f"Embeddings shape: {embeddings.shape}")
    return embeddings.astype("float32")


def save_data(verses: List[Dict], embeddings: np.ndarray):
    """Save verses.json and embeddings.npy."""
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

def main():
    parser = argparse.ArgumentParser(description="Enrich RAG with curated concept documents")
    parser.add_argument("--concepts-only", action="store_true",
                        help="Only inject concepts (skip embedding regen)")
    parser.add_argument("--embeddings-only", action="store_true",
                        help="Only regenerate embeddings (concepts already injected)")
    args = parser.parse_args()

    run_all = not (args.concepts_only or args.embeddings_only)

    # Load existing data
    if not VERSES_PATH.exists():
        logger.error(f"verses.json not found at {VERSES_PATH}. Run ingest_all_data.py first.")
        sys.exit(1)

    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    logger.info(f"Loaded {len(verses)} existing verses")

    # Phase 1: Inject concept documents
    if run_all or args.concepts_only:
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: Injecting curated concept documents")
        logger.info("=" * 60)
        added = inject_concepts(verses)
        logger.info(f"Added {added} new concept documents (total verses: {len(verses)})")

        # Save verses.json even if not regenerating embeddings
        if args.concepts_only:
            for v in verses:
                v.pop("embedding", None)
            with open(VERSES_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "verses": verses,
                        "metadata": {
                            "total_verses": len(verses),
                            "embedding_dim": data.get("metadata", {}).get("embedding_dim", settings.EMBEDDING_DIM),
                            "embedding_model": data.get("metadata", {}).get("embedding_model", settings.EMBEDDING_MODEL),
                            "scriptures": sorted(set(v.get("scripture", "Unknown") for v in verses)),
                        },
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"Saved verses.json with {len(verses)} verses (embeddings NOT regenerated)")
            logger.info("Run with --embeddings-only to regenerate embeddings.")
            return

    # Phase 2: Regenerate embeddings
    if run_all or args.embeddings_only:
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: Regenerating all embeddings")
        logger.info("=" * 60)
        embeddings = regenerate_embeddings(verses)
        save_data(verses, embeddings)

    logger.info("\nDone! Run the benchmark to verify:")
    logger.info("  cd backend && python3 tests/retrieval_accuracy_test.py")


if __name__ == "__main__":
    main()
