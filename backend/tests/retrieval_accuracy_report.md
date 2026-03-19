# Retrieval Accuracy Test Report

Generated: 2026-03-17 09:59:05
Total queries: 100
Average latency: 1419ms per query

## Overall Metrics

| Metric | Value |
|--------|-------|
| MRR | 0.900 |
| Hit@1 | 83.0% |
| Hit@3 | 98.0% |
| Hit@5 | 98.0% |
| Hit@7 | 98.0% |
| Precision@3 | 0.683 |
| Recall@3 | 0.491 |
| Recall@7 | 0.678 |
| Scripture Accuracy@3 | 73.7% |

## Contamination Analysis

- **Temple contamination**: 0/93 non-temple queries have temple docs in results
- **Meditation template noise**: 1 queries have meditation template docs
  - Affected queries:
    - ID 98: "How to do pranayama breathing exercise?" (3 med docs)

## Per-Category Breakdown

| Category | N | MRR | Hit@3 | P@3 | R@3 | Scr.Acc@3 | Temple Contam | Med Noise |
|----------|---|-----|-------|-----|-----|-----------|---------------|-----------|
| anger | 4 | 1.000 | 100.0% | 0.583 | 0.396 | 70.8% | 0 | 0 |
| anxiety | 2 | 0.750 | 100.0% | 0.500 | 0.367 | 58.3% | 0 | 0 |
| ayurveda | 4 | 1.000 | 100.0% | 0.917 | 0.625 | 57.5% | 0 | 0 |
| death | 3 | 1.000 | 100.0% | 0.667 | 0.467 | 100.0% | 0 | 0 |
| devotion | 13 | 0.923 | 100.0% | 0.821 | 0.546 | 69.9% | 0 | 0 |
| dharma | 7 | 0.857 | 100.0% | 0.667 | 0.495 | 92.9% | 0 | 0 |
| digital_life | 1 | 1.000 | 100.0% | 1.000 | 0.429 | 50.0% | 0 | 0 |
| duty | 3 | 1.000 | 100.0% | 0.778 | 0.464 | 61.1% | 0 | 0 |
| faith | 1 | 1.000 | 100.0% | 0.333 | 0.333 | 100.0% | 0 | 0 |
| family | 5 | 0.767 | 100.0% | 0.533 | 0.400 | 40.0% | 0 | 0 |
| fear | 4 | 1.000 | 100.0% | 0.750 | 0.583 | 75.0% | 0 | 0 |
| grief | 4 | 0.875 | 100.0% | 0.667 | 0.417 | 62.5% | 0 | 0 |
| health | 4 | 1.000 | 100.0% | 0.750 | 0.432 | 72.5% | 0 | 0 |
| karma | 5 | 0.900 | 100.0% | 0.867 | 0.607 | 100.0% | 0 | 0 |
| liberation/moksha | 5 | 0.867 | 100.0% | 0.867 | 0.629 | 90.0% | 0 | 0 |
| love | 2 | 1.000 | 100.0% | 0.833 | 0.625 | 100.0% | 0 | 0 |
| mantra | 2 | 1.000 | 100.0% | 0.667 | 0.381 | 46.4% | 0 | 0 |
| meditation | 5 | 0.900 | 100.0% | 0.600 | 0.399 | 56.7% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 0.667 | 0.417 | 75.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.0% | 0 | 0 |
| parenting | 1 | 0.500 | 100.0% | 0.333 | 0.333 | 50.0% | 0 | 0 |
| procedural | 2 | 1.000 | 100.0% | 0.500 | 0.833 | 83.3% | 0 | 1 |
| relationships | 1 | 1.000 | 100.0% | 0.667 | 0.400 | 66.7% | 0 | 0 |
| self-worth | 2 | 0.500 | 50.0% | 0.167 | 0.125 | 25.0% | 0 | 0 |
| soul/atman | 4 | 1.000 | 100.0% | 0.833 | 0.625 | 100.0% | 0 | 0 |
| spiritual_practice | 1 | 1.000 | 100.0% | 0.667 | 0.500 | 100.0% | 0 | 0 |
| temple | 7 | 0.905 | 100.0% | 0.571 | 0.555 | 85.7% | 0 | 0 |
| yoga | 5 | 0.800 | 100.0% | 0.533 | 0.379 | 80.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | P@3 | R@3 | Scripture Acc@3 |
|----------|---|-----|-------|-----|-----|-----------------|
| en | 56 | 0.866 | 98.2% | 0.613 | 0.454 | 76.8% |
| hi | 22 | 0.932 | 95.5% | 0.833 | 0.562 | 71.9% |
| transliterated | 22 | 0.955 | 100.0% | 0.712 | 0.515 | 67.7% |

## Worst 10 Queries (by MRR)

### ID 97: "कैसे अपना आत्मविश्वास बढ़ाएं?"
- Category: self-worth | Language: hi
- MRR: 0.000 | Hit@3: No | Hit@7: No
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 3.35, Bhagavad Gita 18.48
- Retrieved (0 docs):

### ID 8: "How should I fulfill my family responsibilities?"
- Category: family | Language: en
- MRR: 0.333 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 3.35, Bhagavad Gita 18.47, Ramayana Ayodhya Kanda 2.12, Ramayana Ayodhya Kanda 109.10
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.276)
     Text: One should have recourse to such means of livelihood as are not contra...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.274)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  3. [Ramayana] Ramayana ayodhyakanda 19.8 (score=0.274)
     Text: किम् पुनर् मनुज इन्द्रेण स्वयम् पित्रा प्रचोदितः ।तव च प्रिय काम अर्थम...
  4. [Ramayana] Ramayana ayodhyakanda 2.15 (score=0.270)
     Text: यदीदम् मेऽनुरूपार्धं मया साधु सुमन्त्रितम् ।भवन्तो मेऽनुमन्यन्तां कथं ...
  5. [Ramayana] Ramayana sundarakanda 13.19 (score=0.269)
     Text: कथम् नु खलु कर्तव्यम् विषमम् प्रतिभाति मे ।अस्मिन्न् एवम् गते कर्ये प्...

### ID 29: "How to practice non-attachment while living in the world?"
- Category: liberation/moksha | Language: en
- MRR: 0.333 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 3.19, Bhagavad Gita 5.7, Bhagavad Gita 12.12
- Retrieved (4 docs):
  1. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.40 (score=0.300)
     Text: From cleanliness there comes indifference towards body and nonattachme...
  2. [Ramayana] Ramayana sundarakanda 40.6 (score=0.292)
     Text: स वीर्यवान् कथं सीतां हृतां समनुमन्यसे ।वसन्तीं रक्षसां मध्ये महेन्द्र...
  3. [Bhagavad Gita] Concept — Starting Daily Spiritual Practice (score=0.290)
     Text: How to start a daily spiritual practice (sadhana) from Bhagavad Gita a...
  4. [Ramayana] Ramayana ayodhyakanda 2.25 (score=0.289)
     Text: कथं नु मयि धर्मेण पृथिवीमनुशासति ।भवन्तो द्रष्टुमिच्छन्ति युवराजं ममात...

### ID 33: "What are the famous Jyotirlinga temples?"
- Category: temple | Language: en
- MRR: 0.333 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Temple: Mallikarjuna (Andhra Pradesh), Temple: Omkareshwar (Madhya Pradesh), Temple: Kedarnath (Uttarakhand)
- Retrieved (7 docs):
  1. [Hindu Temples] Temple: Shri Bhimashankar Jyotirlinga Wildlife Reserve (Maha (score=1.082)
     Text: Temple Name: Shri Bhimashankar Jyotirlinga Wildlife Reserve

State: Ma...
  2. [Hindu Temples] Temple: Shri Ghrishneshwar Jyotirlinga (Maharashtra) (score=1.082)
     Text: Temple Name: Shri Ghrishneshwar Jyotirlinga

State: Maharashtra

Locat...
  3. [Hindu Temples] Temple: Shri Omkareshwar Jyotirlinga Temple (Madhya Pradesh) (score=1.079)
     Text: Temple Name: Shri Omkareshwar Jyotirlinga Temple

State: Madhya Prades...
  4. [Hindu Temples] Temple: Sri Nagesvara Jyotirlinga replica (Sikkim) (score=1.079)
     Text: Temple Name: Sri Nagesvara Jyotirlinga replica

State: Sikkim

Locatio...
  5. [Hindu Temples] Temple: Shri Kedarnath Jyotirlinga Temple (Uttarakhand) (score=1.075)
     Text: Temple Name: Shri Kedarnath Jyotirlinga Temple

State: Uttarakhand

Lo...

### ID 3: "What does Krishna say about performing your duty without attachment to results?"
- Category: karma | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 2.48, Bhagavad Gita 3.19, Bhagavad Gita 5.10
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 72.48 (score=1.073)
     Text: Perform your duties without attachment, remaining equipoised in succes...
  2. [Bhagavad Gita] Concept — Karma Yoga Explained (score=1.059)
     Text: Karma Yoga — the path of selfless action in Bhagavad Gita. BG 2.47: Yo...
  3. [Bhagavad Gita] Concept — Purpose of Human Life (score=1.036)
     Text: What is the purpose of human life according to Hindu scriptures? BG 3....
  4. [Bhagavad Gita] Bhagavad Gita 3.19 (score=0.982)
     Text: 3.19 Therefore without attachment, do thou always perform action which...
  5. [Ramayana] Ramayana ayodhyakanda 72.47 (score=0.959)
     Text: You have a right to perform your prescribed duty, but you are not enti...

### ID 11: "What are the eight limbs of yoga?"
- Category: yoga | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Patanjali Yoga Sutras 2.29, Patanjali Yoga Sutras 2.30, Patanjali Yoga Sutras 2.46, Patanjali Yoga Sutras 2.49
- Retrieved (7 docs):
  1. [Patanjali Yoga Sutras] Concept — Eight Limbs of Yoga (Ashtanga Yoga) (score=1.117)
     Text: Ashtanga Yoga — the eight limbs of yoga from Patanjali Yoga Sutras. PY...
  2. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.29 (score=0.841)
     Text: Self restraints, fixed rules, postures, breath control, sense withdraw...
  3. [Bhagavad Gita] Bhagavad Gita 4.28 (score=0.821)
     Text: 4.28 Others again offer wealth, austerity and Yoga as sacrifice, while...
  4. [Bhagavad Gita] Bhagavad Gita 6.37 (score=0.275)
     Text: 6.37 Arjuna said  He who is unable to control himself though he has th...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.274)
     Text: Which articles should be kept in the mouth and why; what are the advan...

### ID 19: "What does the Gita teach about the three gunas?"
- Category: dharma | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 14.5, Bhagavad Gita 14.6, Bhagavad Gita 14.7, Bhagavad Gita 14.8, Bhagavad Gita 14.10
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 72.45 (score=0.974)
     Text: The Vedas deal with the three gunas (qualities of nature); rise above ...
  2. [Bhagavad Gita] Bhagavad Gita 18.19 (score=0.476)
     Text: 18.19 Knowledge, action and actor are declared in the science of the G...
  3. [Bhagavad Gita] Bhagavad Gita 14.21 (score=0.387)
     Text: 14.21 Arjuna said  What are the marks of him who has transcended the t...
  4. [Bhagavad Gita] Bhagavad Gita 3.28 (score=0.366)
     Text: 3.28 But he who knows the Truth, O mighty-armed (Arjuna), about the di...
  5. [Mahabharata] Mahabharata Bhishma Parva — The Battle of Kurukshetra (score=0.355)
     Text: The great war of Kurukshetra is fought between the Pandavas and Kaurav...

### ID 25: "What is the role of pranayama in yoga practice?"
- Category: yoga | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Patanjali Yoga Sutras 2.49, Patanjali Yoga Sutras 2.50, Patanjali Yoga Sutras 2.51, Bhagavad Gita 4.29
- Retrieved (7 docs):
  1. [Patanjali Yoga Sutras] Concept — Yoga and Pranayama Benefits (score=1.104)
     Text: Benefits of yoga and pranayama from Patanjali Yoga Sutras and Bhagavad...
  2. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.49 (score=1.047)
     Text: The asana having been done, pranayama is the cessation of the movement...
  3. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.50 (score=1.002)
     Text: Pranayama is external, internal or suppressed, regulated by place, tim...
  4. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.29 (score=0.841)
     Text: Self restraints, fixed rules, postures, breath control, sense withdraw...
  5. [Patanjali Yoga Sutras] Concept — Eight Limbs of Yoga (Ashtanga Yoga) (score=0.841)
     Text: Ashtanga Yoga — the eight limbs of yoga from Patanjali Yoga Sutras. PY...

### ID 31: "How to maintain mental equilibrium in success and failure?"
- Category: meditation | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 2.48, Bhagavad Gita 6.7, Bhagavad Gita 12.18, Bhagavad Gita 14.24
- Retrieved (3 docs):
  1. [Bhagavad Gita] Concept — Mental Equilibrium (Samatvam) (score=1.086)
     Text: Mental equilibrium and equanimity (samatvam) in Bhagavad Gita. BG 2.48...
  2. [Bhagavad Gita] Bhagavad Gita 2.48 (score=0.562)
     Text: 2.48 Perform action, O Arjuna, being steadfast in Yoga, abandoning att...
  3. [Ramayana] Ramayana ayodhyakanda 72.48 (score=0.364)
     Text: Perform your duties without attachment, remaining equipoised in succes...

### ID 40: "What is the universal form of God described in the Gita?"
- Category: devotion | Language: en
- MRR: 0.500 | Hit@3: Yes | Hit@7: Yes
- Ground truth: Bhagavad Gita 11.5, Bhagavad Gita 11.9, Bhagavad Gita 11.12, Bhagavad Gita 11.16, Bhagavad Gita 11.32
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata — Krishna's Universal Form (Vishwaroop Darshan) (score=1.098)
     Text: In the Bhagavad Gita (Chapter 11), Arjuna asks Krishna to reveal his t...
  2. [Bhagavad Gita] Concept — Krishna's Vishwaroop (Universal Form) (score=1.043)
     Text: Krishna's Vishwaroop Darshan — the cosmic universal form. BG 11.5: Beh...
  3. [Bhagavad Gita] Concept — Is It Wrong to Feel Angry at God (score=0.499)
     Text: Is it wrong to be angry at God? What Bhagavad Gita says about question...
  4. [Bhagavad Gita] Concept — Surrender (Sharanagati / Saranagati) (score=0.289)
     Text: Surrender to God (sharanagati) in Bhagavad Gita. BG 18.66: sarva-dharm...
  5. [Bhagavad Gita] Bhagavad Gita 11.45 (score=0.287)
     Text: 11.45 I am delighted, having seen what has never been seen before; and...


## Ablation Tests (English queries 1-40)

### A1: min_score threshold

| min_score | MRR | Hit@3 | P@3 | R@3 | Temple Contam | Med Noise |
|-----------|-----|-------|-----|-----|---------------|-----------|
| 0.05 | 0.875 | 100.0% | 0.667 | 0.446 | 0 | 0 |
| 0.1 | 0.875 | 100.0% | 0.667 | 0.446 | 0 | 0 |
| 0.15 | 0.875 | 100.0% | 0.667 | 0.446 | 0 | 0 |
| 0.2 | 0.875 | 100.0% | 0.667 | 0.446 | 0 | 0 |
| 0.25 | 0.875 | 100.0% | 0.658 | 0.442 | 0 | 0 |

### A2: top_k values

| top_k | MRR | Hit@3 | Hit@K | P@3 | R@K | Temple Contam | Med Noise |
|-------|-----|-------|-------|-----|-----|---------------|-----------|
| 10 | 0.875 | 100.0% | 100.0% | 0.667 | 0.678 | 0 | 0 |
| 3 | 0.867 | 97.5% | 97.5% | 0.633 | 0.425 | 0 | 0 |
| 5 | 0.867 | 97.5% | 97.5% | 0.650 | 0.587 | 0 | 0 |
| 7 | 0.875 | 100.0% | 100.0% | 0.667 | 0.662 | 0 | 0 |

### A3: Intent weighting

| Config | MRR | Hit@3 | P@3 | Temple Contam | Med Noise |
|--------|-----|-------|-----|---------------|-----------|
| No intent | 0.867 | 97.5% | 0.650 | 0 | 0 |

## Improvement Plan

Based on the test results, prioritized improvements:

### P2: Curated Narrative Documents
- Create 50-100 synthetic English story summaries for key epic episodes
- (Rama's exile, Hanuman's leap, Draupadi's disrobing, etc.)

### P2: Separate Indices
- Route queries to scripture vs temple vs procedural indices based on intent classification
