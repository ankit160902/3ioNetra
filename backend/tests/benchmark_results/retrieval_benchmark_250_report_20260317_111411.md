# RAG Benchmark Report

Generated: 2026-03-17 11:14:11
Total queries: 250
Average latency: 1471ms | p50: 1372ms | p95: 2213ms | p99: 2720ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 77.2% (threshold >= 97%)
- FAIL: MRR = 0.706 (threshold >= 0.85)
- FAIL: Scripture Accuracy@3 = 65.8% (threshold >= 70%)
- FAIL: Category 'edge_adversarial' has MRR = 0.0 (5 queries)
- FAIL: Category 'frustration' has MRR = 0.0 (3 queries)
- FAIL: Category 'hopelessness' has MRR = 0.0 (3 queries)
- FAIL: Category 'off_topic' has MRR = 0.0 (1 queries)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.706 |
| hit@1 | 63.6% |
| hit@3 | 77.2% |
| hit@5 | 80.4% |
| hit@7 | 81.2% |
| precision@3 | 0.469 |
| recall@3 | 0.489 |
| recall@7 | 0.634 |
| ndcg@3 | 0.715 |
| ndcg@5 | 0.722 |
| scripture_accuracy@3 | 65.8% |
| Temple Contamination | 0 queries |
| Meditation Noise | 4 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 1372ms |
| p95 | 2213ms |
| p99 | 2720ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| frustration | 3 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| hopelessness | 3 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| loneliness | 3 | 0.056 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| pregnancy_fertility | 3 | 0.083 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| jealousy | 3 | 0.111 | 33.3% | 0.167 | 0.111 | 0.167 | 33.3% | 0 | 0 |
| career_work | 3 | 0.167 | 33.3% | 0.210 | 0.111 | 0.167 | 33.3% | 0 | 0 |
| ethics_moral | 3 | 0.178 | 33.3% | 0.167 | 0.111 | 0.167 | 33.3% | 0 | 0 |
| financial_stress | 3 | 0.222 | 33.3% | 0.210 | 0.111 | 0.167 | 33.3% | 0 | 0 |
| addiction | 4 | 0.250 | 25.0% | 0.250 | 0.167 | 0.167 | 25.0% | 0 | 0 |
| education_exam | 3 | 0.250 | 33.3% | 0.231 | 0.222 | 0.222 | 33.3% | 0 | 0 |
| ayurveda_specific | 10 | 0.300 | 30.0% | 0.300 | 0.100 | 0.150 | 60.0% | 0 | 0 |
| edge_long | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 0.333 | 33.3% | 0 | 0 |
| shame | 3 | 0.444 | 66.7% | 0.500 | 0.333 | 0.500 | 66.7% | 0 | 0 |
| mantra_specific | 10 | 0.475 | 50.0% | 0.463 | 0.233 | 0.450 | 50.0% | 0 | 0 |
| edge_emoji_caps | 2 | 0.500 | 100.0% | 0.662 | 0.500 | 1.000 | 100.0% | 0 | 0 |
| self-worth | 4 | 0.500 | 50.0% | 0.500 | 0.250 | 0.312 | 37.5% | 0 | 0 |
| relationships | 2 | 0.600 | 50.0% | 0.500 | 0.333 | 0.200 | 33.3% | 0 | 0 |
| procedural | 12 | 0.604 | 66.7% | 0.605 | 0.306 | 0.514 | 51.4% | 0 | 4 |
| edge_typo | 7 | 0.643 | 71.4% | 0.670 | 0.381 | 0.714 | 71.4% | 0 | 0 |
| confusion | 3 | 0.667 | 100.0% | 0.754 | 0.333 | 0.500 | 100.0% | 0 | 0 |
| family | 6 | 0.694 | 100.0% | 0.782 | 0.500 | 0.375 | 41.7% | 0 | 0 |
| guilt | 3 | 0.733 | 66.7% | 0.667 | 0.333 | 0.500 | 66.7% | 0 | 0 |
| parenting | 2 | 0.750 | 100.0% | 0.847 | 0.500 | 0.667 | 75.0% | 0 | 0 |
| anxiety | 3 | 0.833 | 100.0% | 0.877 | 0.333 | 0.344 | 61.1% | 0 | 0 |
| yoga | 6 | 0.833 | 100.0% | 0.887 | 0.500 | 0.399 | 75.0% | 0 | 0 |
| karma | 7 | 0.857 | 100.0% | 0.912 | 0.810 | 0.617 | 100.0% | 0 | 0 |
| story_narrative | 10 | 0.858 | 90.0% | 0.850 | 0.333 | 0.800 | 85.0% | 0 | 0 |
| edge_short | 5 | 0.867 | 100.0% | 0.884 | 0.533 | 0.800 | 100.0% | 0 | 0 |
| dharma | 9 | 0.889 | 100.0% | 0.907 | 0.667 | 0.533 | 94.4% | 0 | 0 |
| liberation/moksha | 6 | 0.889 | 100.0% | 0.903 | 0.833 | 0.690 | 91.7% | 0 | 0 |
| grief | 5 | 0.900 | 100.0% | 0.926 | 0.733 | 0.533 | 70.0% | 0 | 0 |
| temple | 7 | 0.905 | 100.0% | 0.929 | 0.571 | 0.555 | 85.7% | 0 | 0 |
| meditation | 6 | 0.917 | 100.0% | 0.898 | 0.611 | 0.499 | 63.9% | 0 | 0 |
| devotion | 14 | 0.929 | 100.0% | 0.950 | 0.810 | 0.555 | 72.0% | 0 | 0 |
| cross_scripture | 10 | 0.933 | 100.0% | 0.934 | 0.500 | 0.717 | 71.7% | 0 | 0 |
| anger | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.486 | 80.6% | 0 | 0 |
| ayurveda | 4 | 1.000 | 100.0% | 1.000 | 0.917 | 0.625 | 57.5% | 0 | 0 |
| death | 4 | 1.000 | 100.0% | 0.980 | 0.750 | 0.579 | 100.0% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.476 | 83.3% | 0 | 0 |
| duty | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.598 | 70.8% | 0 | 0 |
| edge_codeswitching | 8 | 1.000 | 100.0% | 0.990 | 0.500 | 0.812 | 93.8% | 0 | 0 |
| faith | 2 | 1.000 | 100.0% | 1.000 | 0.500 | 0.667 | 100.0% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 0.984 | 0.733 | 0.667 | 80.0% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 0.667 | 100.0% | 0 | 0 |
| health | 5 | 1.000 | 100.0% | 1.000 | 0.667 | 0.445 | 68.0% | 0 | 0 |
| love | 3 | 1.000 | 100.0% | 1.000 | 0.778 | 0.750 | 100.0% | 0 | 0 |
| mantra | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.381 | 46.4% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.417 | 75.0% | 0 | 0 |
| soul/atman | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.700 | 100.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 0.960 | 0.667 | 0.750 | 100.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.698 | 79.5% | 0.716 | 0.446 | 0.467 | 69.0% |
| hi | 62 | 0.694 | 74.2% | 0.701 | 0.522 | 0.515 | 65.0% |
| transliterated | 61 | 0.736 | 75.4% | 0.726 | 0.464 | 0.508 | 59.9% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.792 | 87.5% | 0.792 | 0.542 | 2359ms |
| 11-20 words | 45 | 0.567 | 64.4% | 0.581 | 0.326 | 1374ms |
| 20+ words | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 1647ms |
| 4-10 words | 194 | 0.740 | 80.4% | 0.749 | 0.502 | 1454ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.546 | 66.7% | 0.581 | 0.259 |
| scripture_level | 232 | 0.718 | 78.0% | 0.725 | 0.486 |

## Worst 15 Queries (by MRR)

### ID 97: "कैसे अपना आत्मविश्वास बढ़ाएं?"
- Category: self-worth | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 3.35, Bhagavad Gita 18.48
- Latency: 1947ms
- Retrieved (0 docs):

### ID 102: "मुझे अपने पिछले कर्मों पर बहुत शर्म आती है"
- Category: shame | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.36, Bhagavad Gita 9.30
- Latency: 1275ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 19.15 (score=0.286)
     Text: व्रीडा अन्वितः स्वयम् यच् च न्Rपः त्वाम् न अभिभाषते ।न एतत् किम्चिन् न...
  2. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 4.27 (score=0.272)
     Text: In between the state of discrimination (viveka) other pratyayas arise ...
  3. [Mahabharata] Mahabharata 1.93 (score=0.271)
     Text: नातिप्रीति मनाश चासीद विवादांश चान्वमॊदत
दयूतादीन अनयान घॊरान परवृद्धा...
  4. [Mahabharata] Mahabharata 12 136.98 (score=0.270)
     Text: अथ वा पूर्ववैरं तवं समरन कालं विकर्षसि
पश्य दुष्कृतकर्मत्वं वयक्तम आयु...
  5. [Mahabharata] Mahabharata 3 144.14 (score=0.270)
     Text: तत सर्वम अनवाप्यैव शरमशॊकाद धि कर्शिता
शेते निपतिता भूमौ पापस्य मम कर्...

### ID 108: "मेरे दोस्तों की सफलता देखकर मुझे ईर्ष्या होती है"
- Category: jealousy | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 12.13, Bhagavad Gita 16.1
- Latency: 1328ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 40.7 (score=0.278)
     Text: एष चूडामणिर्दिव्यो मया सुपरिरक्षितः ।एतं दृष्ट्वा प्रहृष्यामि व्यसने त...
  2. [Ramayana] Ramayana yudhhakanda 115.20 (score=0.275)
     Text: कृतकार्यं समृद्धार्थं दृष्ट्वा रामो विभीषणम् ।प्रतिजग्राह तत् सर्वं तस...
  3. [Ramayana] Ramayana sundarakanda 15.24 (score=0.275)
     Text: प्रियम् जनम् अपश्यन्तीम् पश्यन्तीम् राक्षसी गणम् ।स्व गणेन मृगीम् हीना...
  4. [Ramayana] Ramayana sundarakanda 1.87 (score=0.272)
     Text: प्रेक्ष्य सर्वे कपिवरं सहसा विगतक्लमम् ।तस्मिन् प्लवगशार्दूले प्लवमाने...
  5. [Ramayana] Ramayana sundarakanda 1.203 (score=0.272)
     Text: सागरस्य च पत्नीनां मुखान्यपि विलोकयन् ।स महामेघसंकाशं समीक्ष्यात्मानमा...

### ID 109: "mere doston ki success dekhkar mujhe jealousy hoti hai"
- Category: jealousy | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 12.13, Bhagavad Gita 16.1
- Latency: 1296ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 40.7 (score=0.287)
     Text: एष चूडामणिर्दिव्यो मया सुपरिरक्षितः ।एतं दृष्ट्वा प्रहृष्यामि व्यसने त...
  2. [Ramayana] Ramayana sundarakanda 15.24 (score=0.282)
     Text: प्रियम् जनम् अपश्यन्तीम् पश्यन्तीम् राक्षसी गणम् ।स्व गणेन मृगीम् हीना...
  3. [Ramayana] Ramayana yudhhakanda 115.20 (score=0.280)
     Text: कृतकार्यं समृद्धार्थं दृष्ट्वा रामो विभीषणम् ।प्रतिजग्राह तत् सर्वं तस...
  4. [Ramayana] Ramayana sundarakanda 1.87 (score=0.279)
     Text: प्रेक्ष्य सर्वे कपिवरं सहसा विगतक्लमम् ।तस्मिन् प्लवगशार्दूले प्लवमाने...
  5. [Ramayana] Ramayana sundarakanda 13.41 (score=0.278)
     Text: वानप्रस्थो भविष्यामि अदृष्ट्वा जनक आत्मजाम् ।सागर अनूपजे देशे बहु मूल ...

### ID 111: "मुझे बहुत अकेलापन लगता है, कोई मेरा नहीं है"
- Category: loneliness | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 9.29
- Latency: 1790ms
- Retrieved (7 docs):
  1. [Atharva Veda] Atharva Veda 20.134 (score=0.272)
     Text: Here, in this way, from east, west, north, south, and below - you have...
  2. [Rig Veda] Rig Veda 5.8 (score=0.270)
     Text: The worshipers of truth kindle you, Agni, the ancient one, the ancient...
  3. [Ramayana] Ramayana sundarakanda 35.83 (score=0.269)
     Text: विश्वासार्थं तु वैदेहि भर्तुरुक्ता मया गुणाः ।अचिराद् राघवो देवि त्वाम...
  4. [Ramayana] Ramayana sundarakanda 35.72 (score=0.267)
     Text: एतत्ते सर्वमाख्यातं यथावृत्तमनिन्दिते ।अभिभाषस्व मां देवि दूतो दाशरथेर...
  5. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 1.21 (score=0.266)
     Text: Those who have an intense urge attain asamprajnata samadhi very soon...

### ID 112: "mujhe bahut akela feel hota hai koi mera nahi hai"
- Category: loneliness | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 9.29
- Latency: 1406ms
- Retrieved (7 docs):
  1. [Rig Veda] Rig Veda 5.8 (score=0.274)
     Text: The worshipers of truth kindle you, Agni, the ancient one, the ancient...
  2. [Atharva Veda] Atharva Veda 20.134 (score=0.272)
     Text: Here, in this way, from east, west, north, south, and below - you have...
  3. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 1.21 (score=0.272)
     Text: Those who have an intense urge attain asamprajnata samadhi very soon...
  4. [Ramayana] Ramayana sundarakanda 35.83 (score=0.271)
     Text: विश्वासार्थं तु वैदेहि भर्तुरुक्ता मया गुणाः ।अचिराद् राघवो देवि त्वाम...
  5. [Atharva Veda] Atharva Veda 20.115 (score=0.270)
     Text: I have grasped the wisdom of truth from my father, and I am born like ...

### ID 113: "I am so frustrated with my life, nothing is going right"
- Category: frustration | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 2.48
- Latency: 213ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 109.27 (score=0.275)
     Text: सन्तुष्टपञ्चवर्गो ऽहं लोकयात्रां प्रवर्त्तये ।अकुह: श्रद्दधानस्सन् कार...
  2. [Mahabharata] Mahabharata 1.161 (score=0.272)
     Text: संजयैवं गते पराणांस तयक्तुम इच्छामि माचिरम
सतॊकं हय अपि न पश्यामि फलं ...
  3. [Mahabharata] Mahabharata 12 142.43 (score=0.270)
     Text: अहॊ मम नृशंसस्य गर्हितस्य सवकर्मणा
अधर्मः सुमहान घॊरॊ भविष्यति न संशयः...
  4. [Mahabharata] Mahabharata 8 29.36 (score=0.270)
     Text: ऋद्धं गेहं सर्वकामैर यच च मे वसु किं चन
तत सर्वम अस्मै सत्कृत्य परयच्छ...
  5. [Mahabharata] Mahabharata 3 238.7 (score=0.270)
     Text: ये मे निराकृता नित्यं रिपुर येषाम अहं सदा
तैर मॊक्षितॊ ऽहं दुर्बुद्धिर...

### ID 114: "मैं अपनी ज़िंदगी से बहुत निराश हूँ, कुछ भी सही नहीं हो रहा"
- Category: frustration | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 2.48
- Latency: 1183ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.161 (score=0.272)
     Text: संजयैवं गते पराणांस तयक्तुम इच्छामि माचिरम
सतॊकं हय अपि न पश्यामि फलं ...
  2. [Mahabharata] Mahabharata 12 142.43 (score=0.269)
     Text: अहॊ मम नृशंसस्य गर्हितस्य सवकर्मणा
अधर्मः सुमहान घॊरॊ भविष्यति न संशयः...
  3. [Mahabharata] Mahabharata 12 31.41 (score=0.268)
     Text: संजीवितश चापि मया वासवानुमते तदा
भवितव्यं तथा तच च न तच छक्यम अतॊ ऽनयथ...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.268)
     Text: That is named the Science of Life, wherein are laid down the good and ...
  5. [Mahabharata] Mahabharata 3 238.7 (score=0.268)
     Text: ये मे निराकृता नित्यं रिपुर येषाम अहं सदा
तैर मॊक्षितॊ ऽहं दुर्बुद्धिर...

### ID 115: "main apni zindagi se bahut frustrated hoon kuch bhi sahi nahi ho raha"
- Category: frustration | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 2.48
- Latency: 1812ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.161 (score=0.273)
     Text: संजयैवं गते पराणांस तयक्तुम इच्छामि माचिरम
सतॊकं हय अपि न पश्यामि फलं ...
  2. [Rig Veda] Rig Veda 9.15 (score=0.271)
     Text: This hero goes with subtle wisdom, with swift chariots, going to the o...
  3. [Mahabharata] Mahabharata 12 142.43 (score=0.270)
     Text: अहॊ मम नृशंसस्य गर्हितस्य सवकर्मणा
अधर्मः सुमहान घॊरॊ भविष्यति न संशयः...
  4. [Mahabharata] Mahabharata 3 238.7 (score=0.270)
     Text: ये मे निराकृता नित्यं रिपुर येषाम अहं सदा
तैर मॊक्षितॊ ऽहं दुर्बुद्धिर...
  5. [Mahabharata] Mahabharata 8 29.36 (score=0.269)
     Text: ऋद्धं गेहं सर्वकामैर यच च मे वसु किं चन
तत सर्वम अस्मै सत्कृत्य परयच्छ...

### ID 119: "I have lost all hope and feel like giving up"
- Category: hopelessness | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.39, Bhagavad Gita 6.5
- Latency: 362ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.106 (score=0.344)
     Text: यदाश्रौषं दरौपदीम अश्रुकण्ठीं; सभां नीतां दुःखिताम एकवस्त्राम
रजस्वलां...
  2. [Mahabharata] Mahabharata 1.155 (score=0.303)
     Text: यदाश्रौषं बरह्मशिरॊ ऽरजुनेन मुक्तं; सवस्तीत्य अस्त्रम अस्त्रेण शान्तम
...
  3. [Mahabharata] Mahabharata 1.150 (score=0.302)
     Text: यदाश्रौषं शरान्तम एकं शयानं; हरदं गत्वा सतम्भयित्वा तद अम्भः
दुर्यॊधनं...
  4. [Mahabharata] Mahabharata 1.121 (score=0.299)
     Text: यदाश्रौषं मन्त्रिणं वासुदेवं; तथा भीष्मं शांतनवं च तेषाम
भारद्वाजं चाश...
  5. [Mahabharata] Mahabharata 1.136 (score=0.294)
     Text: यदाश्रौषं शरान्तहये धनंजये; मुक्त्वा हयान पाययित्वॊपवृत्तान
पुनर युक्त...

### ID 120: "मैंने सब उम्मीद खो दी है, हार मान लेना चाहता हूँ"
- Category: hopelessness | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.39, Bhagavad Gita 6.5
- Latency: 1203ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.161 (score=0.772)
     Text: संजयैवं गते पराणांस तयक्तुम इच्छामि माचिरम
सतॊकं हय अपि न पश्यामि फलं ...
  2. [Mahabharata] Mahabharata 1.155 (score=0.400)
     Text: यदाश्रौषं बरह्मशिरॊ ऽरजुनेन मुक्तं; सवस्तीत्य अस्त्रम अस्त्रेण शान्तम
...
  3. [Mahabharata] Mahabharata 1.121 (score=0.396)
     Text: यदाश्रौषं मन्त्रिणं वासुदेवं; तथा भीष्मं शांतनवं च तेषाम
भारद्वाजं चाश...
  4. [Mahabharata] Mahabharata 1.106 (score=0.392)
     Text: यदाश्रौषं दरौपदीम अश्रुकण्ठीं; सभां नीतां दुःखिताम एकवस्त्राम
रजस्वलां...
  5. [Mahabharata] Mahabharata 1.137 (score=0.390)
     Text: यदाश्रौषं वाहनेष्व आश्वसत्सु; रथॊपस्थे तिष्ठता गाण्डिवेन
सर्वान यॊधान ...

### ID 121: "maine sab ummeed kho di hai haar maan lena chahta hoon"
- Category: hopelessness | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.39, Bhagavad Gita 6.5
- Latency: 286ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.2 (score=0.226)
     Text: Thus declared the worshipful Atreya....
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch2.2 (score=0.226)
     Text: Thus declared the worshipful Atreya....
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.2 (score=0.226)
     Text: Thus declared the worshipful Atreya....
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.2 (score=0.226)
     Text: Thus declared the worshipful Atreya....
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch4.2 (score=0.226)
     Text: Thus declared the worshipful Atreya....

### ID 122: "I am struggling with addiction and can't stop myself"
- Category: addiction | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.62, Bhagavad Gita 2.63, Bhagavad Gita 6.5
- Latency: 547ms
- Retrieved (5 docs):
  1. [Ramayana] Ramayana ayodhyakanda 20.31 (score=0.281)
     Text: स ष्ट्चाअष्टौ च वर्षाणि वत्स्यामि विजने वने ।आसेवमानो वन्यानि फलमूलैश्...
  2. [Ramayana] Ramayana sundarakanda 13.65 (score=0.278)
     Text: ब्रह्मा स्वयम्भूर् भगवान् देवाः चैव दिशन्तु मे ।सिद्धिम् अग्निः च वायु...
  3. [Mahabharata] Mahabharata 1 3.44 (score=0.276)
     Text: स उपाध्यायं परत्युवाच
भॊ एतासां गवां पयसा वृत्तिं कल्पयामीति...
  4. [Mahabharata] Mahabharata 1 3.36 (score=0.276)
     Text: स उपाध्यायं परत्युवाच
भैक्षेण वृत्तिं कल्पयामीति...
  5. [Ramayana] Ramayana sundarakanda 28.18 (score=0.274)
     Text: शोकाभितप्ता बहुधा विचिन्त्य सीता ऽथ वेण्युद्ग्रथनं गृहीत्वा ।उद्बध्य व...

### ID 123: "मैं नशे की लत से जूझ रहा हूँ और खुद को रोक नहीं पा रहा"
- Category: addiction | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.62, Bhagavad Gita 2.63, Bhagavad Gita 6.5
- Latency: 1904ms
- Retrieved (5 docs):
  1. [Ramayana] Ramayana ayodhyakanda 72.11 (score=0.281)
     Text: शून्यो अयम् शयनीयः ते पर्यन्को हेम भूषितः ।न च अयम् इक्ष्वाकु जनः प्रह...
  2. [Mahabharata] Mahabharata 1.159 (score=0.271)
     Text: तमसा तव अभ्यवस्तीर्णॊ मॊह आविशतीव माम
संज्ञां नॊपलभे सूत मनॊ विह्वलतीव...
  3. [Ramayana] Ramayana kishkindhakanda 7.6 (score=0.270)
     Text: मया अपि व्यसनम् प्राप्तम् भार्या विरहजम् महत् ।न अहम् एवम् हि शोचामि ध...
  4. [Mahabharata] Mahabharata 12 171.44 (score=0.270)
     Text: तृप्तः सवस्थेन्द्रियॊ नित्यं यथा लब्धेन वर्तयन
न सकामं करिष्यामि तवाम ...
  5. [Mahabharata] Mahabharata 12 107.3 (score=0.269)
     Text: आनृशंस्येन धर्मेण लॊके हय अस्मिञ जिजीविषुः
नाहम एतद अलं कर्तुं नैतन मय...

### ID 124: "main nashe ki lat se ladh raha hoon aur khud ko rok nahi paa raha"
- Category: addiction | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.62, Bhagavad Gita 2.63, Bhagavad Gita 6.5
- Latency: 1697ms
- Retrieved (5 docs):
  1. [Ramayana] Ramayana ayodhyakanda 72.11 (score=0.279)
     Text: शून्यो अयम् शयनीयः ते पर्यन्को हेम भूषितः ।न च अयम् इक्ष्वाकु जनः प्रह...
  2. [Mahabharata] Mahabharata 1.159 (score=0.271)
     Text: तमसा तव अभ्यवस्तीर्णॊ मॊह आविशतीव माम
संज्ञां नॊपलभे सूत मनॊ विह्वलतीव...
  3. [Ramayana] Ramayana kishkindhakanda 7.6 (score=0.270)
     Text: मया अपि व्यसनम् प्राप्तम् भार्या विरहजम् महत् ।न अहम् एवम् हि शोचामि ध...
  4. [Mahabharata] Mahabharata 12 171.44 (score=0.270)
     Text: तृप्तः सवस्थेन्द्रियॊ नित्यं यथा लब्धेन वर्तयन
न सकामं करिष्यामि तवाम ...
  5. [Mahabharata] Mahabharata 12 107.3 (score=0.269)
     Text: आनृशंस्येन धर्मेण लॊके हय अस्मिञ जिजीविषुः
नाहम एतद अलं कर्तुं नैतन मय...
