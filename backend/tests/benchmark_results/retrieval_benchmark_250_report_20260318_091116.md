# RAG Benchmark Report

Generated: 2026-03-18 09:11:16
Total queries: 244
Average latency: 3904ms | p50: 3841ms | p95: 4955ms | p99: 5251ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 80.7% (threshold >= 97%)
- FAIL: MRR = 0.784 (threshold >= 0.85)
- FAIL: Scripture Accuracy@3 = 63.4% (threshold >= 70%)
- FAIL: p95 latency = 4955ms (threshold <= 2500ms)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.784 |
| hit@1 | 73.8% |
| hit@3 | 80.7% |
| hit@5 | 85.2% |
| hit@7 | 87.7% |
| precision@3 | 0.520 |
| recall@3 | 0.568 |
| recall@7 | 0.683 |
| ndcg@3 | 0.782 |
| ndcg@5 | 0.804 |
| scripture_accuracy@3 | 63.4% |
| Temple Contamination | 0 queries |
| Meditation Noise | 5 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 3841ms |
| p95 | 4955ms |
| p99 | 5251ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| mantra | 2 | 0.167 | 50.0% | 0.250 | 0.167 | 0.167 | 25.0% | 0 | 0 |
| story_narrative | 10 | 0.333 | 40.0% | 0.350 | 0.200 | 0.300 | 30.0% | 0 | 0 |
| health | 5 | 0.500 | 60.0% | 0.539 | 0.333 | 0.200 | 29.0% | 0 | 0 |
| loneliness | 3 | 0.500 | 66.7% | 0.564 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| love | 3 | 0.500 | 66.7% | 0.564 | 0.444 | 0.500 | 66.7% | 0 | 0 |
| mantra_specific | 10 | 0.550 | 50.0% | 0.492 | 0.200 | 0.300 | 30.0% | 0 | 0 |
| cross_scripture | 10 | 0.609 | 60.0% | 0.569 | 0.200 | 0.300 | 30.0% | 0 | 0 |
| duty | 4 | 0.625 | 75.0% | 0.673 | 0.417 | 0.354 | 70.8% | 0 | 0 |
| edge_emoji_caps | 2 | 0.625 | 50.0% | 0.500 | 0.167 | 0.500 | 50.0% | 0 | 0 |
| faith | 2 | 0.625 | 50.0% | 0.500 | 0.500 | 0.500 | 50.0% | 0 | 0 |
| shame | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| dharma | 9 | 0.685 | 66.7% | 0.667 | 0.667 | 0.567 | 61.1% | 0 | 0 |
| edge_short | 5 | 0.700 | 80.0% | 0.739 | 0.533 | 0.800 | 80.0% | 0 | 0 |
| ayurveda_specific | 10 | 0.714 | 70.0% | 0.700 | 0.233 | 0.550 | 55.0% | 0 | 0 |
| confusion | 3 | 0.714 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| ayurveda | 4 | 0.750 | 75.0% | 0.750 | 0.250 | 0.208 | 22.5% | 0 | 0 |
| narrative | 2 | 0.750 | 100.0% | 0.847 | 0.500 | 0.361 | 50.0% | 0 | 0 |
| temple | 7 | 0.750 | 71.4% | 0.714 | 0.381 | 0.440 | 71.4% | 0 | 0 |
| procedural | 12 | 0.767 | 75.0% | 0.750 | 0.306 | 0.472 | 47.2% | 0 | 3 |
| death | 4 | 0.786 | 75.0% | 0.750 | 0.333 | 0.271 | 75.0% | 0 | 0 |
| devotion | 14 | 0.792 | 85.7% | 0.800 | 0.595 | 0.422 | 58.3% | 0 | 0 |
| edge_codeswitching | 8 | 0.812 | 87.5% | 0.837 | 0.500 | 0.750 | 75.0% | 0 | 2 |
| karma | 7 | 0.821 | 85.7% | 0.813 | 0.762 | 0.551 | 85.7% | 0 | 0 |
| addiction | 4 | 0.833 | 100.0% | 0.875 | 0.833 | 0.833 | 100.0% | 0 | 0 |
| frustration | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| jealousy | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| pregnancy_fertility | 3 | 0.833 | 100.0% | 0.898 | 0.333 | 0.500 | 50.0% | 0 | 0 |
| yoga | 6 | 0.833 | 83.3% | 0.807 | 0.500 | 0.399 | 58.3% | 0 | 0 |
| soul/atman | 5 | 0.850 | 80.0% | 0.800 | 0.733 | 0.650 | 80.0% | 0 | 0 |
| edge_typo | 7 | 0.857 | 85.7% | 0.857 | 0.429 | 0.786 | 78.6% | 0 | 0 |
| liberation/moksha | 6 | 0.861 | 83.3% | 0.833 | 0.667 | 0.583 | 83.3% | 0 | 0 |
| anger | 6 | 1.000 | 100.0% | 1.000 | 0.778 | 0.556 | 80.6% | 0 | 0 |
| anxiety | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.622 | 61.1% | 0 | 0 |
| career_work | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 0.762 | 75.0% | 0 | 0 |
| edge_long | 3 | 1.000 | 100.0% | 1.000 | 0.889 | 0.889 | 100.0% | 0 | 0 |
| education_exam | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| ethics_moral | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| family | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.500 | 41.7% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.733 | 60.0% | 0 | 0 |
| financial_stress | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| grief | 5 | 1.000 | 100.0% | 1.000 | 0.867 | 0.600 | 63.3% | 0 | 0 |
| guilt | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| hopelessness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| meditation | 6 | 1.000 | 100.0% | 1.000 | 0.611 | 0.465 | 55.6% | 0 | 0 |
| parenting | 2 | 1.000 | 100.0% | 1.000 | 0.500 | 0.583 | 50.0% | 0 | 0 |
| relationships | 2 | 1.000 | 100.0% | 1.000 | 0.833 | 0.800 | 66.7% | 0 | 0 |
| self-worth | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.625 | 50.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.625 | 75.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.743 | 76.4% | 0.734 | 0.478 | 0.515 | 60.6% |
| hi | 62 | 0.790 | 79.0% | 0.790 | 0.570 | 0.605 | 63.2% |
| transliterated | 61 | 0.786 | 83.6% | 0.796 | 0.508 | 0.586 | 63.3% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.562 | 62.5% | 0.587 | 0.458 | 3141ms |
| 11-20 words | 45 | 0.833 | 86.7% | 0.835 | 0.593 | 4070ms |
| 20+ words | 3 | 1.000 | 100.0% | 1.000 | 0.889 | 4711ms |
| 4-10 words | 194 | 0.755 | 77.3% | 0.750 | 0.485 | 3882ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.514 | 50.0% | 0.491 | 0.222 |
| scripture_level | 232 | 0.785 | 81.0% | 0.784 | 0.530 |

## Worst 15 Queries (by MRR)

### ID 19: "What does the Gita teach about the three gunas?"
- Category: dharma | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 14.5, Bhagavad Gita 14.6, Bhagavad Gita 14.7, Bhagavad Gita 14.8, Bhagavad Gita 14.10
- Latency: 3721ms
- Retrieved (7 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 3.21 teaches (score=0.862)
     Text: Gita 3.21 teaches yad yad acharati shreshthah — whatever a great perso...
  2. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.47 teaches (score=0.803)
     Text: Gita 2.47 teaches focus on action, not fruits — financial outcomes are...
  3. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 4.39 teaches (score=0.581)
     Text: Gita 4.39 teaches shraddhaval labhate jnanam — the person of faith att...
  4. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.58 describ (score=0.573)
     Text: Gita 2.58 describes the wise person who withdraws the senses from sens...
  5. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 9.29 says sa (score=0.471)
     Text: Gita 9.29 says samoham sarvabhuteshu — I am equally present in all bei...

### ID 37: "What does the Gita say about vegetarian food and diet?"
- Category: health | Language: en | Match: exact
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 17.8, Bhagavad Gita 17.9, Bhagavad Gita 17.10, Bhagavad Gita 6.17
- Latency: 4205ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.275)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.000)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.000)
     Text: Pouring oil into the ears, inunction, anointing the feet, body-massage...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.275)
     Text: That is named the Science of Life, wherein are laid down the good and ...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.000)
     Text: The compilations of these disciples, which were thus approved by the g...

### ID 39: "What is the concept of dharmic warfare or just war?"
- Category: duty | Language: en | Match: exact
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.31, Bhagavad Gita 2.32, Bhagavad Gita 2.33, Bhagavad Gita 11.33
- Latency: 3969ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 18.31 (score=0.280)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  2. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...
  3. [Bhagavad Gita] Bhagavad Gita 13.4 (score=0.273)
     Text: 13.4 What the field is and of what nature, what are its modifications ...
  4. [Bhagavad Gita] Bhagavad Gita 13.3 (score=0.000)
     Text: 13.3 Do thou also know Me as the knower of the field in all fields, O ...
  5. [Bhagavad Gita] Bhagavad Gita 13.5 (score=0.000)
     Text: 13.5 Sages have sung in many ways, in various distinctive chants and a...

### ID 43: "शिव जी की पूजा कैसे करें?"
- Category: devotion | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Rig Veda 7.59.12, Atharva Veda 11.2.1
- Latency: 4153ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 12.6 (score=1.155)
     Text: 12.6 But to those who worship Me, renouncing all actions in Me, regard...
  2. [Bhagavad Gita] Bhagavad Gita 12.5 (score=0.000)
     Text: 12.5 Greater is their trouble whose minds are set on the unmanifested;...
  3. [Bhagavad Gita] Bhagavad Gita 12.7 (score=0.000)
     Text: 12.7 To those whose minds are set on Me, O Arjuna, verily I become ere...
  4. [Bhagavad Gita] Bhagavad Gita 7.26 (score=1.150)
     Text: 7.26 I know, O Arjuna, the beings of the past, the present and the fut...
  5. [Bhagavad Gita] Bhagavad Gita 7.25 (score=0.000)
     Text: 7.25 I am not manifest to all (as I am) veiled by the Yoga-Maya. This ...

### ID 51: "योग सूत्र में यम और नियम क्या हैं?"
- Category: yoga | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.30, Patanjali Yoga Sutras 2.31, Patanjali Yoga Sutras 2.32, Patanjali Yoga Sutras 2.35
- Latency: 5251ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 6.21 (score=1.081)
     Text: 6.21 When he (the Yogi) feels that Infinite Bliss which can be grasped...
  2. [Bhagavad Gita] Bhagavad Gita 6.20 (score=0.000)
     Text: 6.20 When the mind, restrained by the practice of Yoga attains to quie...
  3. [Bhagavad Gita] Bhagavad Gita 6.22 (score=0.000)
     Text: 6.22 Which, having obtained, he thinks there is no other gain superior...
  4. [Bhagavad Gita] Bhagavad Gita 18.31 (score=1.073)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  5. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...

### ID 52: "आयुर्वेद में तीन दोष क्या हैं?"
- Category: ayurveda | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Atharva Veda 1.12.1, Atharva Veda 6.44.1, Rig Veda 10.97.1, Rig Veda 10.97.12
- Latency: 3401ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 11.20 (score=0.916)
     Text: 11.20 This space between the earth and the heaven and all the arters a...
  2. [Bhagavad Gita] Bhagavad Gita 11.19 (score=0.000)
     Text: 11.19 I see Thee without beginning, middle or end, infinite in power, ...
  3. [Bhagavad Gita] Bhagavad Gita 11.21 (score=0.000)
     Text: 11.21 Verily, into Thee enter these hosts of gods; some extol Thee in ...
  4. [Bhagavad Gita] Bhagavad Gita 17.1 (score=0.913)
     Text: 17.1 Arjuna said  Those who, setting aside the ordinances of the scrip...
  5. [Bhagavad Gita] Bhagavad Gita 17.2 (score=0.000)
     Text: 17.2 The Blessed Lord said  Threefold is the faith of the embodied, wh...

### ID 54: "भारत के प्रसिद्ध मंदिर कौन से हैं?"
- Category: temple | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Tirupati Balaji (Andhra Pradesh), Temple: Jagannath (Odisha), Temple: Meenakshi (Tamil Nadu), Temple: Somnath (Gujarat)
- Latency: 4399ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 4.34 (score=0.924)
     Text: 4.34 Know That by long prostration, by estion and by service; the wise...
  2. [Bhagavad Gita] Bhagavad Gita 4.33 (score=0.000)
     Text: Swami Sivananda did not comment on this sloka...
  3. [Bhagavad Gita] Bhagavad Gita 4.35 (score=0.000)
     Text: 4.35 Knowing ï1thatï1 thou shalt not, O Arjuna, again get deluded like...
  4. [Bhagavad Gita] Bhagavad Gita 18.31 (score=0.923)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  5. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...

### ID 55: "भगवान से प्रेम कैसे करें?"
- Category: love | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.29, Bhagavad Gita 12.14, Bhagavad Gita 18.65, Bhagavad Gita 18.55
- Latency: 4962ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 97.11 (score=1.078)
     Text: स्नेहेनाक्रान्तहृदय: शोकेनाकुलितेन्द्रिय:।द्रष्टुमभ्यागतो ह्येष भरतो न...
  2. [Ramayana] Ramayana ayodhyakanda 97.10 (score=0.000)
     Text: श्रुत्वा प्रव्राजितं मां हि जटावल्कलधारिणम्।जानक्या सहितं वीर त्वया च ...
  3. [Ramayana] Ramayana ayodhyakanda 97.12 (score=0.000)
     Text: अम्बां च कैकयीं रुष्य परुषं चाप्रियं वदन्।प्रसाद्य पितरं श्रीमान् राज्...
  4. [Ramayana] Ramayana yudhhakanda 117.35 (score=1.077)
     Text: विस्मयाच्च प्रहर्षाच्च स्नेहाच्च पतिदेवता ।उदैक्षत मुखं भर्तुः सौम्यं ...
  5. [Ramayana] Ramayana yudhhakanda 117.34 (score=0.000)
     Text: सा वस्त्रसंरुद्धमुखी लज्जया जनसंसदि ।रुरोदासाद्य भर्तारमार्यपुत्रेति भ...

### ID 61: "dharma kya hai"
- Category: dharma | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.7, Bhagavad Gita 4.7, Bhagavad Gita 4.8, Bhagavad Gita 18.66
- Latency: 3815ms
- Retrieved (1 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.7 shows Ar (score=0.225)
     Text: Gita 2.7 shows Arjuna's moment of complete confusion — karpanya-dosho-...

### ID 100: "ओँ नमः शिवाय का जाप कैसे करें?"
- Category: mantra | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 7.59.12, Atharva Veda 11.2.1, Temple: Kashi Vishwanath (Uttar Pradesh)
- Latency: 4401ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 4.4 (score=1.064)
     Text: 4.4 Arjuna said  Later on was Thy birth, and prior to it was the birth...
  2. [Bhagavad Gita] Bhagavad Gita 4.3 (score=0.000)
     Text: 4.3 That same ancient Yoga has been today taught to thee by Me, for th...
  3. [Bhagavad Gita] Bhagavad Gita 4.5 (score=0.000)
     Text: 4.5 The Blessed Lord said  Many births of Mine have passed as well as ...
  4. [Bhagavad Gita] Bhagavad Gita 10.17 (score=1.060)
     Text: 10.17 How shall I, ever meditating, know Thee, O Yogin? In what aspect...
  5. [Bhagavad Gita] Bhagavad Gita 10.16 (score=0.000)
     Text: 10.16 Thou shouldst indeed tell, without reserve, of Thy divine glorie...

### ID 102: "मुझे अपने पिछले कर्मों पर बहुत शर्म आती है"
- Category: shame | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.36, Bhagavad Gita 9.30
- Latency: 3820ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana aranyakanda 63.4 (score=1.073)
     Text: पूर्वम् मया नूनम् अभीप्सितानिपापानि कर्माणि असत्कृत् कृतानि ।तत्र अयम्...
  2. [Ramayana] Ramayana aranyakanda 63.3 (score=0.000)
     Text: न मत् विधो दुष्कृत कर्म कारीमन्ये द्वितीयो अस्ति वसुंधरायाम् ।शोक अनुश...
  3. [Ramayana] Ramayana aranyakanda 63.5 (score=0.000)
     Text: राज्य प्रणाशः स्व जनैः वियोगःपितुर् विनाशो जननी वियोगः ।सर्वानि मे लक्...
  4. [Mahabharata] Mahabharata 12 185.15 (score=1.072)
     Text: इह शरमॊ भयं मॊहः कषुधा तीव्रा च जायते
लॊभश चार्थकृतॊ नॄणां येन मुह्यन्...
  5. [Mahabharata] Mahabharata 12 185.14 (score=0.000)
     Text: इह धर्मपराः के चित के चिन नैकृतिका नराः
सुखिता दुःखिताः के चिन निर्धना...

### ID 112: "mujhe bahut akela feel hota hai koi mera nahi hai"
- Category: loneliness | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 9.29
- Latency: 3879ms
- Retrieved (2 docs):
  1. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.40 (score=0.249)
     Text: From cleanliness there comes indifference towards body and nonattachme...
  2. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 9.29 says sa (score=0.222)
     Text: Gita 9.29 says samoham sarvabhuteshu — I am equally present in all bei...

### ID 153: "What is the concept of dharma across Gita, Ramayana and Mahabharata?"
- Category: cross_scripture | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.7, Ramayana Ayodhya Kanda 2.12, Mahabharata 1.1
- Latency: 3635ms
- Retrieved (7 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Grihastha dharma  (score=0.881)
     Text: Grihastha dharma teaches that family duty is sacred. Gita 3.35 says sw...
  2. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.47 says ka (score=0.588)
     Text: Gita 2.47 says karmanye vadhikaraste ma phaleshu kadachana — you have ...
  3. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 3.21 teaches (score=0.541)
     Text: Gita 3.21 teaches yad yad acharati shreshthah — whatever a great perso...
  4. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 9.30 says ap (score=0.378)
     Text: Gita 9.30 says api cet suduracharo bhajate mam ananyabhak — even the m...
  5. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 7.11 says dh (score=0.331)
     Text: Gita 7.11 says dharmaaviruddho bhuteshu kaamo'smi — I am the desire in...

### ID 159: "सूर्य नमस्कार कैसे करें?"
- Category: procedural | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.46
- Latency: 4491ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana yudhhakanda 107.19 (score=1.043)
     Text: ब्रह्मोशानाच्युतेशाय सूर्यायादित्यवर्चसे ।भास्वते सर्वभक्षाय रौद्राय व...
  2. [Ramayana] Ramayana yudhhakanda 107.18 (score=0.000)
     Text: नम उग्राय वीराय सारङ्गाय नमो नमः ।नमः पद्मप्रबोधाय मार्ताण्डाय नमो नमः...
  3. [Ramayana] Ramayana yudhhakanda 107.20 (score=0.000)
     Text: तमोघ्नाय हिमध्नाय शत्रुघ्नायामितात्मने ।कृतघ्नघ्नाय देवाय ज्योतिषां पत...
  4. [Mahabharata] Mahabharata 6 20.1 (score=1.042)
     Text: [धृ]
सूर्यॊदये संजय के नु पूर्वं; युयुत्सवॊ हृष्यमाणा इवासन
मामका वा भ...
  5. [Mahabharata] Mahabharata 6 20.2 (score=0.000)
     Text: केषां जघन्यौ सॊमसूर्यौ स वायू; केषां सेनां शवापदा वयाभषन्त
केषां यूनां...

### ID 163: "om ka sahi tarika kya hai chanting ke liye?"
- Category: procedural | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 8.13, Patanjali Yoga Sutras 1.27
- Latency: 3602ms
- Retrieved (0 docs):
