# RAG Benchmark Report

Generated: 2026-03-18 11:48:03
Total queries: 244
Average latency: 4218ms | p50: 4107ms | p95: 5449ms | p99: 6842ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 88.1% (threshold >= 97%)
- FAIL: p95 latency = 5449ms (threshold <= 2500ms)
- FAIL: Category 'guilt' has MRR = 0.0 (3 queries)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.851 |
| hit@1 | 80.7% |
| hit@3 | 88.1% |
| hit@5 | 90.2% |
| hit@7 | 92.6% |
| precision@3 | 0.577 |
| recall@3 | 0.637 |
| recall@7 | 0.752 |
| ndcg@3 | 0.852 |
| ndcg@5 | 0.858 |
| scripture_accuracy@3 | 73.1% |
| Temple Contamination | 0 queries |
| Meditation Noise | 4 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 4107ms |
| p95 | 5449ms |
| p99 | 6842ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| guilt | 3 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| relationships | 2 | 0.250 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| ayurveda_specific | 10 | 0.648 | 70.0% | 0.642 | 0.267 | 0.600 | 60.0% | 0 | 0 |
| financial_stress | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| love | 3 | 0.667 | 66.7% | 0.640 | 0.444 | 0.500 | 66.7% | 0 | 0 |
| shame | 3 | 0.667 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| yoga | 6 | 0.667 | 83.3% | 0.697 | 0.444 | 0.339 | 66.7% | 0 | 0 |
| story_narrative | 10 | 0.700 | 80.0% | 0.732 | 0.333 | 0.700 | 70.0% | 0 | 0 |
| anxiety | 3 | 0.714 | 66.7% | 0.667 | 0.333 | 0.289 | 27.8% | 0 | 0 |
| confusion | 3 | 0.722 | 66.7% | 0.667 | 0.444 | 0.667 | 66.7% | 0 | 0 |
| addiction | 4 | 0.750 | 75.0% | 0.750 | 0.750 | 0.750 | 75.0% | 0 | 0 |
| ayurveda | 4 | 0.750 | 75.0% | 0.750 | 0.417 | 0.375 | 40.0% | 0 | 0 |
| edge_emoji_caps | 2 | 0.750 | 100.0% | 0.847 | 0.500 | 1.000 | 100.0% | 0 | 0 |
| temple | 7 | 0.750 | 71.4% | 0.714 | 0.381 | 0.440 | 71.4% | 0 | 0 |
| death | 4 | 0.786 | 75.0% | 0.750 | 0.333 | 0.258 | 75.0% | 0 | 0 |
| dharma | 9 | 0.794 | 77.8% | 0.778 | 0.704 | 0.594 | 66.7% | 0 | 0 |
| health | 5 | 0.800 | 80.0% | 0.800 | 0.533 | 0.312 | 54.0% | 0 | 0 |
| cross_scripture | 10 | 0.820 | 90.0% | 0.839 | 0.400 | 0.567 | 56.7% | 0 | 0 |
| edge_short | 5 | 0.829 | 80.0% | 0.784 | 0.400 | 0.600 | 80.0% | 0 | 0 |
| edge_long | 3 | 0.833 | 100.0% | 0.898 | 0.889 | 0.889 | 100.0% | 0 | 0 |
| frustration | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| jealousy | 3 | 0.833 | 100.0% | 0.898 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| pregnancy_fertility | 3 | 0.833 | 100.0% | 0.898 | 0.333 | 0.500 | 50.0% | 0 | 0 |
| mantra_specific | 10 | 0.870 | 90.0% | 0.855 | 0.400 | 0.700 | 75.0% | 0 | 0 |
| procedural | 12 | 0.875 | 91.7% | 0.879 | 0.389 | 0.639 | 63.9% | 0 | 3 |
| liberation/moksha | 6 | 0.889 | 100.0% | 0.917 | 0.778 | 0.649 | 91.7% | 0 | 0 |
| devotion | 14 | 0.893 | 92.9% | 0.907 | 0.786 | 0.543 | 71.4% | 0 | 0 |
| meditation | 6 | 0.917 | 100.0% | 0.938 | 0.722 | 0.540 | 69.4% | 0 | 0 |
| edge_codeswitching | 8 | 0.938 | 100.0% | 0.962 | 0.542 | 0.875 | 87.5% | 0 | 1 |
| anger | 6 | 1.000 | 100.0% | 1.000 | 0.778 | 0.556 | 80.6% | 0 | 0 |
| career_work | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.778 | 0.810 | 75.0% | 0 | 0 |
| duty | 4 | 1.000 | 100.0% | 1.000 | 0.750 | 0.557 | 91.7% | 0 | 0 |
| edge_typo | 7 | 1.000 | 100.0% | 0.989 | 0.476 | 0.929 | 100.0% | 0 | 0 |
| education_exam | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| ethics_moral | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| faith | 2 | 1.000 | 100.0% | 1.000 | 0.833 | 1.000 | 100.0% | 0 | 0 |
| family | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.500 | 52.8% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.733 | 60.0% | 0 | 0 |
| grief | 5 | 1.000 | 100.0% | 1.000 | 1.000 | 0.700 | 73.3% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| hopelessness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| karma | 7 | 1.000 | 100.0% | 1.000 | 0.952 | 0.694 | 100.0% | 0 | 0 |
| loneliness | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| mantra | 2 | 1.000 | 100.0% | 0.960 | 0.500 | 0.405 | 57.1% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 0.960 | 0.833 | 0.667 | 100.0% | 0 | 0 |
| parenting | 2 | 1.000 | 100.0% | 1.000 | 0.333 | 0.417 | 50.0% | 0 | 0 |
| self-worth | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.625 | 50.0% | 0 | 0 |
| soul/atman | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.700 | 100.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.625 | 75.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.858 | 89.8% | 0.860 | 0.572 | 0.633 | 77.9% |
| hi | 62 | 0.744 | 75.8% | 0.747 | 0.538 | 0.570 | 59.2% |
| transliterated | 61 | 0.862 | 88.5% | 0.861 | 0.568 | 0.651 | 70.1% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.768 | 75.0% | 0.740 | 0.417 | 3578ms |
| 11-20 words | 45 | 0.844 | 88.9% | 0.862 | 0.600 | 4409ms |
| 20+ words | 3 | 0.833 | 100.0% | 0.898 | 0.889 | 7840ms |
| 4-10 words | 194 | 0.830 | 85.6% | 0.828 | 0.555 | 4182ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.542 | 61.1% | 0.545 | 0.241 |
| scripture_level | 232 | 0.853 | 87.9% | 0.854 | 0.588 |

## Worst 15 Queries (by MRR)

### ID 43: "शिव जी की पूजा कैसे करें?"
- Category: devotion | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Rig Veda 7.59.12, Atharva Veda 11.2.1
- Latency: 4480ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 12.6 (score=1.156)
     Text: 12.6 But to those who worship Me, renouncing all actions in Me, regard...
  2. [Bhagavad Gita] Bhagavad Gita 12.5 (score=0.000)
     Text: 12.5 Greater is their trouble whose minds are set on the unmanifested;...
  3. [Bhagavad Gita] Bhagavad Gita 12.7 (score=0.000)
     Text: 12.7 To those whose minds are set on Me, O Arjuna, verily I become ere...
  4. [Bhagavad Gita] Bhagavad Gita 7.26 (score=1.154)
     Text: 7.26 I know, O Arjuna, the beings of the past, the present and the fut...
  5. [Bhagavad Gita] Bhagavad Gita 7.25 (score=0.000)
     Text: 7.25 I am not manifest to all (as I am) veiled by the Yoga-Maya. This ...

### ID 51: "योग सूत्र में यम और नियम क्या हैं?"
- Category: yoga | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.30, Patanjali Yoga Sutras 2.31, Patanjali Yoga Sutras 2.32, Patanjali Yoga Sutras 2.35
- Latency: 4068ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 6.21 (score=1.097)
     Text: 6.21 When he (the Yogi) feels that Infinite Bliss which can be grasped...
  2. [Bhagavad Gita] Bhagavad Gita 6.22 (score=0.000)
     Text: 6.22 Which, having obtained, he thinks there is no other gain superior...
  3. [Bhagavad Gita] Bhagavad Gita 18.31 (score=1.088)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  4. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...
  5. [Bhagavad Gita] Bhagavad Gita 9.22 (score=1.086)
     Text: 9.22 For those men who worship Me alone, thinking of no other, for tho...

### ID 52: "आयुर्वेद में तीन दोष क्या हैं?"
- Category: ayurveda | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Atharva Veda 1.12.1, Atharva Veda 6.44.1, Rig Veda 10.97.1, Rig Veda 10.97.12
- Latency: 4006ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 11.20 (score=0.930)
     Text: 11.20 This space between the earth and the heaven and all the arters a...
  2. [Bhagavad Gita] Bhagavad Gita 11.19 (score=0.000)
     Text: 11.19 I see Thee without beginning, middle or end, infinite in power, ...
  3. [Bhagavad Gita] Bhagavad Gita 11.21 (score=0.000)
     Text: 11.21 Verily, into Thee enter these hosts of gods; some extol Thee in ...
  4. [Bhagavad Gita] Bhagavad Gita 14.20 (score=0.927)
     Text: 14.20 The embodied one having crossed beyond these three Gunas out of ...
  5. [Bhagavad Gita] Bhagavad Gita 14.19 (score=0.000)
     Text: 14.19 When the seer beholds no agent other than the Gunas and knows Th...

### ID 54: "भारत के प्रसिद्ध मंदिर कौन से हैं?"
- Category: temple | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Tirupati Balaji (Andhra Pradesh), Temple: Jagannath (Odisha), Temple: Meenakshi (Tamil Nadu), Temple: Somnath (Gujarat)
- Latency: 5461ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 18.31 (score=0.931)
     Text: 18.31 That, by which one wrongly understands Dharma and Adharma and al...
  2. [Bhagavad Gita] Bhagavad Gita 18.32 (score=0.000)
     Text: 18.32 That, which, enveloped in darkness, sees Adharma as Dharma and a...
  3. [Bhagavad Gita] Bhagavad Gita 16.7 (score=0.929)
     Text: 16.7 The demoniacal know not what to do and what to refrain from; neit...
  4. [Bhagavad Gita] Bhagavad Gita 16.6 (score=0.000)
     Text: 16.6 There are two types of beings in this world, the divine and the d...
  5. [Bhagavad Gita] Bhagavad Gita 4.34 (score=0.929)
     Text: 4.34 Know That by long prostration, by estion and by service; the wise...

### ID 55: "भगवान से प्रेम कैसे करें?"
- Category: love | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.29, Bhagavad Gita 12.14, Bhagavad Gita 18.65, Bhagavad Gita 18.55
- Latency: 3850ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana yudhhakanda 106.23 (score=1.097)
     Text: भर्तृस्नेहपरीतेन मयेदं यत्कृतं विभो ।। ६.१०६.२३ ।।...
  2. [Ramayana] Ramayana yudhhakanda 106.22 (score=0.000)
     Text: न मया स्वेच्छया वीर रथो ऽयमपवाहितः ।। ६.१०६.२२ ।।...
  3. [Ramayana] Ramayana yudhhakanda 106.24 (score=0.000)
     Text: आज्ञापय यथातत्त्वं वक्ष्यस्यरिनिषूदन ।तत्करिष्याम्यहं वीर गतानृण्येन च...
  4. [Ramayana] Ramayana ayodhyakanda 97.11 (score=1.096)
     Text: स्नेहेनाक्रान्तहृदय: शोकेनाकुलितेन्द्रिय:।द्रष्टुमभ्यागतो ह्येष भरतो न...
  5. [Ramayana] Ramayana ayodhyakanda 97.10 (score=0.000)
     Text: श्रुत्वा प्रव्राजितं मां हि जटावल्कलधारिणम्।जानक्या सहितं वीर त्वया च ...

### ID 61: "dharma kya hai"
- Category: dharma | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.7, Bhagavad Gita 4.7, Bhagavad Gita 4.8, Bhagavad Gita 18.66
- Latency: 3840ms
- Retrieved (1 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 2.7 shows Ar (score=0.244)
     Text: Gita 2.7 shows Arjuna's moment of complete confusion — karpanya-dosho-...

### ID 102: "मुझे अपने पिछले कर्मों पर बहुत शर्म आती है"
- Category: shame | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.36, Bhagavad Gita 9.30
- Latency: 4397ms
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
- Latency: 3851ms
- Retrieved (7 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures curated_weak_categories.Gita 9.30 says ap (score=0.544)
     Text: Gita 9.30 says api cet suduracharo bhajate mam ananyabhak — even the m...
  2. [Mahabharata] Mahabharata 12 16.3 (score=0.293)
     Text: न वक्ष्यामि न वक्ष्यामीत्य एवं मे मनसि सथितम
अति दुःखात तु वक्ष्यामि त...
  3. [Mahabharata] Mahabharata 12 16.2 (score=0.000)
     Text: राजन विदितधर्मॊ ऽसि न ते ऽसत्य अविदितं भुवि
उपशिक्षाम ते वृत्तं सदैव न...
  4. [Mahabharata] Mahabharata 12 16.4 (score=0.000)
     Text: भवतस तु परमॊहेन सर्वं संशयितं कृतम
विक्लवत्वं च नः पराप्तम अबलत्वं तथै...
  5. [Mahabharata] Mahabharata 6 95.8 (score=0.292)
     Text: अब्रवीच च विशुद्धात्मा नाहं हन्यां शिखण्डिनम
सत्रीपूर्वकॊ हय असौ जातस ...

### ID 105: "मुझे बहुत अपराधबोध है और मैं खुद को माफ नहीं कर पा रहा"
- Category: guilt | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.30, Bhagavad Gita 18.66
- Latency: 4561ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 12 16.3 (score=1.099)
     Text: न वक्ष्यामि न वक्ष्यामीत्य एवं मे मनसि सथितम
अति दुःखात तु वक्ष्यामि त...
  2. [Mahabharata] Mahabharata 12 16.2 (score=0.000)
     Text: राजन विदितधर्मॊ ऽसि न ते ऽसत्य अविदितं भुवि
उपशिक्षाम ते वृत्तं सदैव न...
  3. [Mahabharata] Mahabharata 12 16.4 (score=0.000)
     Text: भवतस तु परमॊहेन सर्वं संशयितं कृतम
विक्लवत्वं च नः पराप्तम अबलत्वं तथै...
  4. [Mahabharata] Mahabharata 13 104.23 (score=1.099)
     Text: अहं तु पापयॊन्यां वै परसूतः कषत्रियर्षभ
निश्चयं नाधिगच्छामि कथं मुच्ये...
  5. [Mahabharata] Mahabharata 13 104.22 (score=0.000)
     Text: तथा पापकृतं विप्रम आश्रमस्थं महीपते
सर्वसङ्गविनिर्मुक्तं छन्दांस्य उत्...

### ID 106: "mujhe bahut guilt hai aur main khud ko maaf nahi kar pa raha"
- Category: guilt | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.30, Bhagavad Gita 18.66
- Latency: 4248ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 12 16.3 (score=0.296)
     Text: न वक्ष्यामि न वक्ष्यामीत्य एवं मे मनसि सथितम
अति दुःखात तु वक्ष्यामि त...
  2. [Mahabharata] Mahabharata 12 16.2 (score=0.000)
     Text: राजन विदितधर्मॊ ऽसि न ते ऽसत्य अविदितं भुवि
उपशिक्षाम ते वृत्तं सदैव न...
  3. [Mahabharata] Mahabharata 12 16.4 (score=0.000)
     Text: भवतस तु परमॊहेन सर्वं संशयितं कृतम
विक्लवत्वं च नः पराप्तम अबलत्वं तथै...
  4. [Mahabharata] Mahabharata 13 104.23 (score=0.294)
     Text: अहं तु पापयॊन्यां वै परसूतः कषत्रियर्षभ
निश्चयं नाधिगच्छामि कथं मुच्ये...
  5. [Mahabharata] Mahabharata 13 104.22 (score=0.000)
     Text: तथा पापकृतं विप्रम आश्रमस्थं महीपते
सर्वसङ्गविनिर्मुक्तं छन्दांस्य उत्...

### ID 123: "मैं नशे की लत से जूझ रहा हूँ और खुद को रोक नहीं पा रहा"
- Category: addiction | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.62, Bhagavad Gita 2.63, Bhagavad Gita 6.5
- Latency: 5091ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana kishkindhakanda 7.6 (score=1.093)
     Text: मया अपि व्यसनम् प्राप्तम् भार्या विरहजम् महत् ।न अहम् एवम् हि शोचामि ध...
  2. [Ramayana] Ramayana kishkindhakanda 7.5 (score=0.000)
     Text: अलम् वैक्लव्यम् आलम्ब्य धैर्यम् आत्मगतम् स्मर ।त्वत् विधानाम् न सदृशम्...
  3. [Ramayana] Ramayana kishkindhakanda 7.7 (score=0.000)
     Text: न अहम् ताम् अनुशोचामि प्राकृतो वानरो अपि सन् ।महात्मा च विनीतः च किम् ...
  4. [Mahabharata] Mahabharata 12 171.44 (score=1.093)
     Text: तृप्तः सवस्थेन्द्रियॊ नित्यं यथा लब्धेन वर्तयन
न सकामं करिष्यामि तवाम ...
  5. [Mahabharata] Mahabharata 12 171.43 (score=0.000)
     Text: कषमिष्ये ऽकषममाणानां न हिंसिष्ये च हिंसितः
दवेष्य मुक्तः परियं वक्ष्या...

### ID 144: "पैसों की बहुत तंगी है और समझ नहीं आ रहा क्या करूँ"
- Category: financial_stress | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 12.13
- Latency: 5518ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 4 15.27 (score=1.101)
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
  4. [Mahabharata] Mahabharata 5 113.6 (score=1.100)
     Text: वक्तुम इच्छामि तु सखे यथा जानासि मां पुरा
न तथा वित्तवान अस्मि कषीणं व...
  5. [Mahabharata] Mahabharata 5 113.5 (score=0.000)
     Text: अद्य मे सफलं जन्म तारितं चाद्य मे कुलम
अद्यायं तारितॊ देशॊ मम तार्क्ष्...

### ID 159: "सूर्य नमस्कार कैसे करें?"
- Category: procedural | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.46
- Latency: 4341ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 5.1 (score=1.061)
     Text: 5.1 Arjuna said  Renunciation of actions, O Krishna, Thou praisest, an...
  2. [Bhagavad Gita] Bhagavad Gita 5.2 (score=0.000)
     Text: 5.2 The Blessed Lord said  Renunciation and the Yoga of action both le...
  3. [Bhagavad Gita] Bhagavad Gita 18.75 (score=1.061)
     Text: 18.75 Through the grace of Vyasa I have heard this supreme and most se...
  4. [Bhagavad Gita] Bhagavad Gita 18.74 (score=0.000)
     Text: 18.74 Sanjaya said  Thus I have heard this wonderful dialogue between ...
  5. [Bhagavad Gita] Bhagavad Gita 18.76 (score=0.000)
     Text: 18.76 O King, remembering this wonderful and holy dialogue between Kri...

### ID 199: "आयुर्वेद में पाचन स्वास्थ्य के बारे में क्या कहा गया है?"
- Category: ayurveda_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1, Atharva Veda 10.2.1
- Latency: 5382ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 58.16 (score=0.931)
     Text: सर्वम् अन्तः पुरम् वाच्यम् सूत मद्वचनात्त्वया ।आरोग्यम् अविशेषेण यथा अ...
  2. [Ramayana] Ramayana ayodhyakanda 58.15 (score=0.000)
     Text: सूत मद्वचनात् तस्य तातस्य विदित आत्मनः ।शिरसा वन्दनीयस्य वन्द्यौ पादौ ...
  3. [Ramayana] Ramayana ayodhyakanda 58.17 (score=0.000)
     Text: माता च मम कौसल्या कुशलम् च अभिवादनम् ।अप्रमादम् च वक्तव्या ब्रूयाश्चैम...
  4. [Ramayana] Ramayana uttarakanda 36.16 (score=0.931)
     Text: यमो दण्डादवध्यत्वमरोगत्वं च नित्यशः ।वरं ददामि सन्तुष्ट अविषादं च संयु...
  5. [Ramayana] Ramayana uttarakanda 36.15 (score=0.000)
     Text: नचास्य भविता कश्चित्सदृशः शास्त्रदर्शने ।वरुणश्च वरं प्रादान्नास्य मृत...

### ID 204: "आयुर्वेद में रोग प्रतिरोधक शक्ति कैसे बढ़ाएं?"
- Category: ayurveda_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1, Atharva Veda 10.2.1
- Latency: 4947ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 14.11 (score=0.916)
     Text: 14.11 When through every gate (sense) in this body, the wisdom-light s...
  2. [Bhagavad Gita] Bhagavad Gita 14.10 (score=0.000)
     Text: 14.10 Now Sattva arises (prevails), O Arjuna, having overpowered Rajas...
  3. [Bhagavad Gita] Bhagavad Gita 14.12 (score=0.000)
     Text: 14.12 Greed, activity, the undertaking of actions, restlessness, longi...
  4. [Bhagavad Gita] Bhagavad Gita 2.17 (score=0.898)
     Text: 2.17 Know that to be indestructible, by Which all this is pervaded. No...
  5. [Bhagavad Gita] Bhagavad Gita 2.16 (score=0.000)
     Text: 2.16 The unreal hath no being; there is non-being of the real; the tru...
