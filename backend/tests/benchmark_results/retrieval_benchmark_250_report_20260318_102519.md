# RAG Benchmark Report

Generated: 2026-03-18 10:25:19
Total queries: 244
Average latency: 3898ms | p50: 3831ms | p95: 5142ms | p99: 5560ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 82.0% (threshold >= 97%)
- FAIL: MRR = 0.795 (threshold >= 0.85)
- FAIL: Scripture Accuracy@3 = 64.8% (threshold >= 70%)
- FAIL: p95 latency = 5142ms (threshold <= 2500ms)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.795 |
| hit@1 | 75.4% |
| hit@3 | 82.0% |
| hit@5 | 84.4% |
| hit@7 | 86.9% |
| precision@3 | 0.540 |
| recall@3 | 0.583 |
| recall@7 | 0.673 |
| ndcg@3 | 0.796 |
| ndcg@5 | 0.807 |
| scripture_accuracy@3 | 64.8% |
| Temple Contamination | 0 queries |
| Meditation Noise | 5 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 3831ms |
| p95 | 5142ms |
| p99 | 5560ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| mantra | 2 | 0.250 | 50.0% | 0.347 | 0.333 | 0.333 | 25.0% | 0 | 0 |
| story_narrative | 10 | 0.333 | 40.0% | 0.350 | 0.200 | 0.300 | 30.0% | 0 | 0 |
| frustration | 3 | 0.500 | 66.7% | 0.564 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| health | 5 | 0.500 | 60.0% | 0.539 | 0.333 | 0.200 | 29.0% | 0 | 0 |
| pregnancy_fertility | 3 | 0.500 | 66.7% | 0.564 | 0.222 | 0.333 | 33.3% | 0 | 0 |
| mantra_specific | 10 | 0.550 | 50.0% | 0.500 | 0.200 | 0.300 | 30.0% | 0 | 0 |
| death | 4 | 0.562 | 50.0% | 0.500 | 0.167 | 0.125 | 50.0% | 0 | 0 |
| duty | 4 | 0.625 | 75.0% | 0.673 | 0.417 | 0.354 | 70.8% | 0 | 0 |
| financial_stress | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| guilt | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| love | 3 | 0.667 | 66.7% | 0.667 | 0.556 | 0.583 | 66.7% | 0 | 0 |
| shame | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| edge_short | 5 | 0.667 | 80.0% | 0.684 | 0.467 | 0.700 | 80.0% | 0 | 0 |
| cross_scripture | 10 | 0.684 | 70.0% | 0.669 | 0.267 | 0.400 | 40.0% | 0 | 0 |
| dharma | 9 | 0.704 | 66.7% | 0.667 | 0.630 | 0.544 | 61.1% | 0 | 0 |
| ayurveda_specific | 10 | 0.714 | 70.0% | 0.700 | 0.233 | 0.550 | 55.0% | 0 | 0 |
| confusion | 3 | 0.722 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| ayurveda | 4 | 0.750 | 75.0% | 0.750 | 0.250 | 0.208 | 22.5% | 0 | 0 |
| parenting | 2 | 0.750 | 100.0% | 0.847 | 0.500 | 0.583 | 50.0% | 0 | 0 |
| temple | 7 | 0.750 | 71.4% | 0.714 | 0.381 | 0.440 | 71.4% | 0 | 0 |
| edge_typo | 7 | 0.786 | 85.7% | 0.813 | 0.429 | 0.786 | 78.6% | 0 | 0 |
| edge_codeswitching | 8 | 0.812 | 87.5% | 0.837 | 0.500 | 0.750 | 75.0% | 0 | 2 |
| jealousy | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| loneliness | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| yoga | 6 | 0.833 | 83.3% | 0.807 | 0.500 | 0.399 | 58.3% | 0 | 0 |
| devotion | 14 | 0.839 | 85.7% | 0.835 | 0.595 | 0.422 | 58.3% | 0 | 0 |
| procedural | 12 | 0.847 | 83.3% | 0.833 | 0.361 | 0.556 | 55.6% | 0 | 3 |
| soul/atman | 5 | 0.900 | 100.0% | 0.926 | 0.800 | 0.700 | 100.0% | 0 | 0 |
| karma | 7 | 0.929 | 100.0% | 0.956 | 0.905 | 0.658 | 100.0% | 0 | 0 |
| addiction | 4 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| anger | 6 | 1.000 | 100.0% | 0.973 | 0.889 | 0.611 | 80.6% | 0 | 0 |
| anxiety | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.622 | 61.1% | 0 | 0 |
| career_work | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.778 | 0.810 | 75.0% | 0 | 0 |
| edge_emoji_caps | 2 | 1.000 | 100.0% | 1.000 | 0.500 | 1.000 | 100.0% | 0 | 0 |
| edge_long | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| education_exam | 3 | 1.000 | 100.0% | 1.000 | 0.889 | 0.889 | 100.0% | 0 | 0 |
| ethics_moral | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| faith | 2 | 1.000 | 100.0% | 1.000 | 0.833 | 1.000 | 100.0% | 0 | 0 |
| family | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.500 | 41.7% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.733 | 60.0% | 0 | 0 |
| grief | 5 | 1.000 | 100.0% | 1.000 | 0.867 | 0.600 | 63.3% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| hopelessness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| liberation/moksha | 6 | 1.000 | 100.0% | 1.000 | 0.833 | 0.655 | 91.7% | 0 | 0 |
| meditation | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.507 | 61.1% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 0.960 | 0.500 | 0.361 | 50.0% | 0 | 0 |
| relationships | 2 | 1.000 | 100.0% | 1.000 | 0.833 | 0.800 | 66.7% | 0 | 0 |
| self-worth | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.625 | 50.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.625 | 75.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.755 | 78.0% | 0.748 | 0.514 | 0.540 | 63.2% |
| hi | 62 | 0.742 | 74.2% | 0.742 | 0.543 | 0.569 | 58.4% |
| transliterated | 61 | 0.855 | 90.2% | 0.871 | 0.536 | 0.630 | 68.2% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.542 | 62.5% | 0.552 | 0.417 | 3111ms |
| 11-20 words | 45 | 0.815 | 84.4% | 0.824 | 0.585 | 4166ms |
| 20+ words | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 4345ms |
| 4-10 words | 194 | 0.774 | 79.4% | 0.771 | 0.510 | 3855ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.514 | 50.0% | 0.482 | 0.259 |
| scripture_level | 232 | 0.797 | 82.3% | 0.800 | 0.547 |

## Worst 15 Queries (by MRR)

### ID 37: "What does the Gita say about vegetarian food and diet?"
- Category: health | Language: en | Match: exact
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 17.8, Bhagavad Gita 17.9, Bhagavad Gita 17.10, Bhagavad Gita 6.17
- Latency: 4007ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.8 (score=0.304)
     Text: The measured diet not only does not impair one’s health but positively...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.7 (score=0.000)
     Text: It is not that the quantity of a substance does not count. From the po...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.9 (score=0.000)
     Text: One should never, accordingly, eat such heavy articles as pastry flatt...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.290)
     Text: That is named the Science of Life, wherein are laid down the good and ...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.000)
     Text: The compilations of these disciples, which were thus approved by the g...

### ID 39: "What is the concept of dharmic warfare or just war?"
- Category: duty | Language: en | Match: exact
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.31, Bhagavad Gita 2.32, Bhagavad Gita 2.33, Bhagavad Gita 11.33
- Latency: 4022ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 18.31 (score=0.298)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  2. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.289)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.000)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.000)
     Text: Pouring oil into the ears, inunction, anointing the feet, body-massage...

### ID 43: "शिव जी की पूजा कैसे करें?"
- Category: devotion | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Rig Veda 7.59.12, Atharva Veda 11.2.1
- Latency: 2976ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 12.6 (score=1.177)
     Text: 12.6 But to those who worship Me, renouncing all actions in Me, regard...
  2. [Bhagavad Gita] Bhagavad Gita 12.5 (score=0.000)
     Text: 12.5 Greater is their trouble whose minds are set on the unmanifested;...
  3. [Bhagavad Gita] Bhagavad Gita 12.7 (score=0.000)
     Text: 12.7 To those whose minds are set on Me, O Arjuna, verily I become ere...
  4. [Bhagavad Gita] Bhagavad Gita 7.26 (score=1.165)
     Text: 7.26 I know, O Arjuna, the beings of the past, the present and the fut...
  5. [Bhagavad Gita] Bhagavad Gita 7.25 (score=0.000)
     Text: 7.25 I am not manifest to all (as I am) veiled by the Yoga-Maya. This ...

### ID 51: "योग सूत्र में यम और नियम क्या हैं?"
- Category: yoga | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.30, Patanjali Yoga Sutras 2.31, Patanjali Yoga Sutras 2.32, Patanjali Yoga Sutras 2.35
- Latency: 3719ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 6.21 (score=1.100)
     Text: 6.21 When he (the Yogi) feels that Infinite Bliss which can be grasped...
  2. [Bhagavad Gita] Bhagavad Gita 6.22 (score=0.000)
     Text: 6.22 Which, having obtained, he thinks there is no other gain superior...
  3. [Bhagavad Gita] Bhagavad Gita 9.22 (score=1.088)
     Text: 9.22 For those men who worship Me alone, thinking of no other, for tho...
  4. [Bhagavad Gita] Bhagavad Gita 9.21 (score=0.000)
     Text: 9.21 They, having enjoyed the vast heaven, enter the world of mortals ...
  5. [Bhagavad Gita] Bhagavad Gita 9.23 (score=0.000)
     Text: 9.23 Even those devotees who, endowed with faith, worship other gods, ...

### ID 52: "आयुर्वेद में तीन दोष क्या हैं?"
- Category: ayurveda | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Atharva Veda 1.12.1, Atharva Veda 6.44.1, Rig Veda 10.97.1, Rig Veda 10.97.12
- Latency: 3754ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 11.20 (score=0.931)
     Text: 11.20 This space between the earth and the heaven and all the arters a...
  2. [Bhagavad Gita] Bhagavad Gita 11.19 (score=0.000)
     Text: 11.19 I see Thee without beginning, middle or end, infinite in power, ...
  3. [Bhagavad Gita] Bhagavad Gita 11.21 (score=0.000)
     Text: 11.21 Verily, into Thee enter these hosts of gods; some extol Thee in ...
  4. [Bhagavad Gita] Bhagavad Gita 14.20 (score=0.929)
     Text: 14.20 The embodied one having crossed beyond these three Gunas out of ...
  5. [Bhagavad Gita] Bhagavad Gita 14.19 (score=0.000)
     Text: 14.19 When the seer beholds no agent other than the Gunas and knows Th...

### ID 54: "भारत के प्रसिद्ध मंदिर कौन से हैं?"
- Category: temple | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Tirupati Balaji (Andhra Pradesh), Temple: Jagannath (Odisha), Temple: Meenakshi (Tamil Nadu), Temple: Somnath (Gujarat)
- Latency: 5525ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 4.34 (score=0.939)
     Text: 4.34 Know That by long prostration, by estion and by service; the wise...
  2. [Bhagavad Gita] Bhagavad Gita 4.33 (score=0.000)
     Text: Swami Sivananda did not comment on this sloka...
  3. [Bhagavad Gita] Bhagavad Gita 4.35 (score=0.000)
     Text: 4.35 Knowing ï1thatï1 thou shalt not, O Arjuna, again get deluded like...
  4. [Bhagavad Gita] Bhagavad Gita 18.31 (score=0.939)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  5. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...

### ID 55: "भगवान से प्रेम कैसे करें?"
- Category: love | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.29, Bhagavad Gita 12.14, Bhagavad Gita 18.65, Bhagavad Gita 18.55
- Latency: 3903ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 97.11 (score=1.098)
     Text: स्नेहेनाक्रान्तहृदय: शोकेनाकुलितेन्द्रिय:।द्रष्टुमभ्यागतो ह्येष भरतो न...
  2. [Ramayana] Ramayana ayodhyakanda 97.10 (score=0.000)
     Text: श्रुत्वा प्रव्राजितं मां हि जटावल्कलधारिणम्।जानक्या सहितं वीर त्वया च ...
  3. [Ramayana] Ramayana ayodhyakanda 97.12 (score=0.000)
     Text: अम्बां च कैकयीं रुष्य परुषं चाप्रियं वदन्।प्रसाद्य पितरं श्रीमान् राज्...
  4. [Ramayana] Ramayana ayodhyakanda 45.5 (score=1.095)
     Text: अवेक्षमाणः सस्नेहम् चक्षुषा प्रपिबन्न् इव ।उवाच रामः स्नेहेन ताः प्रजा...
  5. [Ramayana] Ramayana ayodhyakanda 45.4 (score=0.000)
     Text: स याच्यमानः काकुत्स्थः स्वाभिः प्रकृतिभिस् तदा ।कुर्वाणः पितरम् सत्यम्...

### ID 61: "dharma kya hai"
- Category: dharma | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.7, Bhagavad Gita 4.7, Bhagavad Gita 4.8, Bhagavad Gita 18.66
- Latency: 3588ms
- Retrieved (1 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.7 shows Ar (score=0.248)
     Text: Gita 2.7 shows Arjuna's moment of complete confusion — karpanya-dosho-...

### ID 100: "ओँ नमः शिवाय का जाप कैसे करें?"
- Category: mantra | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 7.59.12, Atharva Veda 11.2.1, Temple: Kashi Vishwanath (Uttar Pradesh)
- Latency: 3441ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 4.4 (score=1.070)
     Text: 4.4 Arjuna said  Later on was Thy birth, and prior to it was the birth...
  2. [Bhagavad Gita] Bhagavad Gita 4.3 (score=0.000)
     Text: 4.3 That same ancient Yoga has been today taught to thee by Me, for th...
  3. [Bhagavad Gita] Bhagavad Gita 4.5 (score=0.000)
     Text: 4.5 The Blessed Lord said  Many births of Mine have passed as well as ...
  4. [Bhagavad Gita] Bhagavad Gita 10.17 (score=1.069)
     Text: 10.17 How shall I, ever meditating, know Thee, O Yogin? In what aspect...
  5. [Bhagavad Gita] Bhagavad Gita 10.16 (score=0.000)
     Text: 10.16 Thou shouldst indeed tell, without reserve, of Thy divine glorie...

### ID 102: "मुझे अपने पिछले कर्मों पर बहुत शर्म आती है"
- Category: shame | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.36, Bhagavad Gita 9.30
- Latency: 4611ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 12 136.98 (score=1.099)
     Text: अथ वा पूर्ववैरं तवं समरन कालं विकर्षसि
पश्य दुष्कृतकर्मत्वं वयक्तम आयु...
  2. [Mahabharata] Mahabharata 12 136.97 (score=0.000)
     Text: ताथैव तवरमाणेन तवया कार्यं हितं मम
यत्नं कुरु महाप्राज्ञ यथा सवस्त्य आ...
  3. [Mahabharata] Mahabharata 12 136.99 (score=0.000)
     Text: यच च किं चिन मयाज्ञानात पुरस्ताद विप्रियं कृतम
न तन मनसि कर्तव्यं कषमय...
  4. [Mahabharata] Mahabharata 3 144.14 (score=1.099)
     Text: तत सर्वम अनवाप्यैव शरमशॊकाद धि कर्शिता
शेते निपतिता भूमौ पापस्य मम कर्...
  5. [Mahabharata] Mahabharata 3 144.13 (score=0.000)
     Text: सुखं पराप्स्यति पाञ्चाली पाण्डवान पराप्य वै पतीन
इति दरुपदराजेन पित्रा...

### ID 104: "I am consumed by guilt and can't forgive myself"
- Category: guilt | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.30, Bhagavad Gita 18.66
- Latency: 4201ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 12 16.3 (score=0.293)
     Text: न वक्ष्यामि न वक्ष्यामीत्य एवं मे मनसि सथितम
अति दुःखात तु वक्ष्यामि त...
  2. [Mahabharata] Mahabharata 12 16.2 (score=0.000)
     Text: राजन विदितधर्मॊ ऽसि न ते ऽसत्य अविदितं भुवि
उपशिक्षाम ते वृत्तं सदैव न...
  3. [Mahabharata] Mahabharata 12 16.4 (score=0.000)
     Text: भवतस तु परमॊहेन सर्वं संशयितं कृतम
विक्लवत्वं च नः पराप्तम अबलत्वं तथै...
  4. [Mahabharata] Mahabharata 6 95.8 (score=0.292)
     Text: अब्रवीच च विशुद्धात्मा नाहं हन्यां शिखण्डिनम
सत्रीपूर्वकॊ हय असौ जातस ...
  5. [Mahabharata] Mahabharata 6 95.7 (score=0.000)
     Text: तत्र कार्यम अहं मन्ये भीष्मस्यैवाभिरक्षणम
सा नॊ गुप्तः सुखाय सयाद धन्य...

### ID 114: "मैं अपनी ज़िंदगी से बहुत निराश हूँ, कुछ भी सही नहीं हो रहा"
- Category: frustration | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 2.48
- Latency: 5295ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 12 142.43 (score=1.097)
     Text: अहॊ मम नृशंसस्य गर्हितस्य सवकर्मणा
अधर्मः सुमहान घॊरॊ भविष्यति न संशयः...
  2. [Mahabharata] Mahabharata 12 142.42 (score=0.000)
     Text: अग्निमध्यं परविष्टं त लुब्धॊ दृष्ट्वाथ पक्षिणम
चिन्तयाम आस मनसा किम इद...
  3. [Mahabharata] Mahabharata 12 142.44 (score=0.000)
     Text: एवं बहुविधं भूरि विललाप स लुब्धकः
गर्हयन सवानि कर्माणि दविजं दृष्ट्वा ...
  4. [Mahabharata] Mahabharata 12 31.41 (score=1.097)
     Text: संजीवितश चापि मया वासवानुमते तदा
भवितव्यं तथा तच च न तच छक्यम अतॊ ऽनयथ...
  5. [Mahabharata] Mahabharata 12 31.40 (score=0.000)
     Text: स मयैतानि वाक्यानि शरावितः शॊकलालसः
यानि ते यदुवीरेण कथितानि महीपते...

### ID 126: "We are trying to conceive and want spiritual guidance for pregnancy"
- Category: pregnancy_fertility | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 7.11, Atharva Veda 2.3.1
- Latency: 4070ms
- Retrieved (0 docs):

### ID 144: "पैसों की बहुत तंगी है और समझ नहीं आ रहा क्या करूँ"
- Category: financial_stress | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 12.13
- Latency: 4367ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 4 15.27 (score=1.100)
     Text: [विराट]
परॊक्षं नाभिजानामि विग्रहं युवयॊर अहम
अर्थतत्त्वम अविज्ञाय किं...
  2. [Mahabharata] Mahabharata 4 15.26 (score=0.000)
     Text: नॊपालभे तवां नृपतौ विराट जनसंसदि
नाहम एतेन युक्ता वै हन्तुं मत्स्यतवान...
  3. [Mahabharata] Mahabharata 4 15.28 (score=0.000)
     Text: [वै]
ततस तु सभ्या विज्ञाय कृष्णां भूयॊ ऽभयपूजयन
साधु साध्व इति चाप्य आ...
  4. [Mahabharata] Mahabharata 5 113.6 (score=1.099)
     Text: वक्तुम इच्छामि तु सखे यथा जानासि मां पुरा
न तथा वित्तवान अस्मि कषीणं व...
  5. [Mahabharata] Mahabharata 5 113.5 (score=0.000)
     Text: अद्य मे सफलं जन्म तारितं चाद्य मे कुलम
अद्यायं तारितॊ देशॊ मम तार्क्ष्...

### ID 153: "What is the concept of dharma across Gita, Ramayana and Mahabharata?"
- Category: cross_scripture | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.7, Ramayana Ayodhya Kanda 2.12, Mahabharata 1.1
- Latency: 3496ms
- Retrieved (7 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Grihastha dharma  (score=0.893)
     Text: Grihastha dharma teaches that family duty is sacred. Gita 3.35 says sw...
  2. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.47 says ka (score=0.598)
     Text: Gita 2.47 says karmanye vadhikaraste ma phaleshu kadachana — you have ...
  3. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 3.21 teaches (score=0.553)
     Text: Gita 3.21 teaches yad yad acharati shreshthah — whatever a great perso...
  4. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 9.30 says ap (score=0.392)
     Text: Gita 9.30 says api cet suduracharo bhajate mam ananyabhak — even the m...
  5. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 7.11 says dh (score=0.342)
     Text: Gita 7.11 says dharmaaviruddho bhuteshu kaamo'smi — I am the desire in...
