# RAG Benchmark Report

Generated: 2026-03-17 11:58:03
Total queries: 244
Average latency: 1964ms | p50: 1998ms | p95: 2841ms | p99: 3154ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 91.0% (threshold >= 97%)
- FAIL: p95 latency = 2841ms (threshold <= 2500ms)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.860 |
| hit@1 | 81.1% |
| hit@3 | 91.0% |
| hit@5 | 92.2% |
| hit@7 | 92.6% |
| precision@3 | 0.571 |
| recall@3 | 0.619 |
| recall@7 | 0.735 |
| ndcg@3 | 0.866 |
| ndcg@5 | 0.866 |
| scripture_accuracy@3 | 79.4% |
| Temple Contamination | 0 queries |
| Meditation Noise | 4 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 1998ms |
| p95 | 2841ms |
| p99 | 3154ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| relationships | 2 | 0.183 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| ayurveda_specific | 10 | 0.300 | 30.0% | 0.300 | 0.100 | 0.150 | 90.0% | 0 | 0 |
| edge_long | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 0.333 | 33.3% | 0 | 0 |
| mantra_specific | 10 | 0.475 | 50.0% | 0.463 | 0.233 | 0.450 | 50.0% | 0 | 0 |
| edge_emoji_caps | 2 | 0.500 | 100.0% | 0.662 | 0.500 | 1.000 | 100.0% | 0 | 0 |
| procedural | 12 | 0.604 | 66.7% | 0.605 | 0.306 | 0.514 | 51.4% | 0 | 4 |
| edge_typo | 7 | 0.643 | 71.4% | 0.670 | 0.381 | 0.714 | 71.4% | 0 | 0 |
| confusion | 3 | 0.667 | 100.0% | 0.796 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| anxiety | 3 | 0.833 | 100.0% | 0.877 | 0.333 | 0.344 | 61.1% | 0 | 0 |
| financial_stress | 3 | 0.833 | 100.0% | 0.877 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| yoga | 6 | 0.833 | 100.0% | 0.887 | 0.611 | 0.482 | 83.3% | 0 | 0 |
| karma | 7 | 0.857 | 100.0% | 0.912 | 0.810 | 0.617 | 100.0% | 0 | 0 |
| edge_short | 5 | 0.867 | 100.0% | 0.884 | 0.533 | 0.800 | 100.0% | 0 | 0 |
| story_narrative | 10 | 0.867 | 100.0% | 0.900 | 0.367 | 0.850 | 95.0% | 0 | 0 |
| dharma | 9 | 0.889 | 100.0% | 0.907 | 0.667 | 0.533 | 94.4% | 0 | 0 |
| liberation/moksha | 6 | 0.889 | 100.0% | 0.903 | 0.833 | 0.690 | 91.7% | 0 | 0 |
| grief | 5 | 0.900 | 100.0% | 0.926 | 0.800 | 0.583 | 63.3% | 0 | 0 |
| temple | 7 | 0.905 | 100.0% | 0.929 | 0.571 | 0.555 | 85.7% | 0 | 0 |
| meditation | 6 | 0.917 | 100.0% | 0.898 | 0.556 | 0.415 | 55.6% | 0 | 0 |
| cross_scripture | 10 | 0.933 | 100.0% | 0.934 | 0.500 | 0.717 | 71.7% | 0 | 0 |
| addiction | 4 | 1.000 | 100.0% | 1.000 | 0.583 | 0.583 | 100.0% | 0 | 0 |
| anger | 6 | 1.000 | 100.0% | 1.000 | 0.667 | 0.500 | 80.6% | 0 | 0 |
| ayurveda | 4 | 1.000 | 100.0% | 1.000 | 0.917 | 0.625 | 57.5% | 0 | 0 |
| career_work | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| death | 4 | 1.000 | 100.0% | 0.980 | 0.667 | 0.517 | 100.0% | 0 | 0 |
| devotion | 14 | 1.000 | 100.0% | 0.983 | 0.833 | 0.573 | 73.8% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.595 | 83.3% | 0 | 0 |
| duty | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.598 | 70.8% | 0 | 0 |
| edge_codeswitching | 8 | 1.000 | 100.0% | 0.990 | 0.542 | 0.875 | 93.8% | 0 | 0 |
| education_exam | 3 | 1.000 | 100.0% | 1.000 | 0.889 | 0.889 | 100.0% | 0 | 0 |
| ethics_moral | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| faith | 2 | 1.000 | 100.0% | 1.000 | 0.500 | 0.667 | 100.0% | 0 | 0 |
| family | 6 | 1.000 | 100.0% | 0.987 | 0.778 | 0.583 | 63.9% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.733 | 60.0% | 0 | 0 |
| frustration | 3 | 1.000 | 100.0% | 1.000 | 0.333 | 0.500 | 100.0% | 0 | 0 |
| guilt | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| health | 5 | 1.000 | 100.0% | 1.000 | 0.600 | 0.395 | 68.0% | 0 | 0 |
| hopelessness | 3 | 1.000 | 100.0% | 0.973 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| jealousy | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| loneliness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| love | 3 | 1.000 | 100.0% | 1.000 | 0.778 | 0.750 | 100.0% | 0 | 0 |
| mantra | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.381 | 46.4% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.417 | 75.0% | 0 | 0 |
| parenting | 2 | 1.000 | 100.0% | 1.000 | 0.333 | 0.417 | 50.0% | 0 | 0 |
| pregnancy_fertility | 3 | 1.000 | 100.0% | 0.973 | 0.333 | 0.500 | 50.0% | 0 | 0 |
| self-worth | 4 | 1.000 | 100.0% | 1.000 | 0.500 | 0.458 | 50.0% | 0 | 0 |
| shame | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| soul/atman | 5 | 1.000 | 100.0% | 1.000 | 0.800 | 0.700 | 100.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 0.960 | 0.667 | 0.750 | 100.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.788 | 86.6% | 0.804 | 0.512 | 0.550 | 77.4% |
| hi | 62 | 0.892 | 91.9% | 0.895 | 0.634 | 0.663 | 78.2% |
| transliterated | 61 | 0.893 | 90.2% | 0.883 | 0.574 | 0.657 | 76.7% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.792 | 87.5% | 0.792 | 0.542 | 2409ms |
| 11-20 words | 45 | 0.956 | 100.0% | 0.966 | 0.578 | 1786ms |
| 20+ words | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 2560ms |
| 4-10 words | 194 | 0.822 | 87.1% | 0.828 | 0.557 | 1970ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.546 | 66.7% | 0.581 | 0.259 |
| scripture_level | 232 | 0.862 | 90.5% | 0.866 | 0.580 |

## Worst 15 Queries (by MRR)

### ID 156: "How to perform Surya Namaskar step by step?"
- Category: procedural | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.46
- Latency: 1460ms
- Retrieved (6 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures Surya Namaskar.12 Poses (score=1.222)
     Text: Sequence of Surya Namaskar (Sun Salutation): 1. Pranamasana (Prayer po...
  2. [Sanatan Scriptures] Sanatan Scriptures Satyanarayan Puja.Ritual Steps (score=0.300)
     Text: Detailed Ritual Steps for Satyanarayan Puja at home: 1. Purification: ...
  3. [Rig Veda] Rig Veda 1.115 (score=0.265)
     Text: The brilliant face of the gods has risen, the eye of Mitra, Varuna, an...
  4. [Ramayana] Ramayana ayodhyakanda 72.48 (score=0.260)
     Text: Perform your duties without attachment, remaining equipoised in succes...
  5. [Mahabharata] Mahabharata 1.129 (score=0.257)
     Text: यदाश्रौषं शुक्रसूर्यौ च युक्तौ; कौन्तेयानाम अनुलॊमौ जयाय
नित्यं चास्मा...

### ID 159: "सूर्य नमस्कार कैसे करें?"
- Category: procedural | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.46
- Latency: 2007ms
- Retrieved (4 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures Surya Namaskar.12 Poses (score=1.223)
     Text: Sequence of Surya Namaskar (Sun Salutation): 1. Pranamasana (Prayer po...
  2. [Rig Veda] Rig Veda 1.115 (score=0.283)
     Text: The brilliant face of the gods has risen, the eye of Mitra, Varuna, an...
  3. [Sanatan Scriptures] Sanatan Scriptures Home Altar.Setup Guide (score=0.280)
     Text: How to set up a simple home altar: 1. Choose a clean, quiet space faci...
  4. [Mahabharata] Mahabharata 1.129 (score=0.268)
     Text: यदाश्रौषं शुक्रसूर्यौ च युक्तौ; कौन्तेयानाम अनुलॊमौ जयाय
नित्यं चास्मा...

### ID 161: "What are the steps for performing a havan at home?"
- Category: procedural | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.24, Rig Veda 1.1.1
- Latency: 1959ms
- Retrieved (7 docs):
  1. [Sanatan Scriptures] Sanatan Scriptures Satyanarayan Puja.Ritual Steps (score=0.994)
     Text: Detailed Ritual Steps for Satyanarayan Puja at home: 1. Purification: ...
  2. [Sanatan Scriptures] Sanatan Scriptures Breathwork.Anulom Vilom (score=0.297)
     Text: Steps for Anulom Vilom (Alternate Nostril Breathing): 1. Sit comfortab...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.284)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  4. [Yajur Veda] Yajur Veda 5.“अथ पञ्चमोऽध्यायः ।
अ॒ग्नेस्त॒नूर॑सि॒ विष्ण॑वे  (score=0.270)
     Text: You are the body of Agni, for Vishnu; you are the body of Soma, for Vi...
  5. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 3.31 (score=0.267)
     Text: By performing samyama on the throat pit, hunger and thirst retire...

### ID 167: "meditaiton techniques in hinduism"
- Category: edge_typo | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 1.2, Bhagavad Gita 6.10
- Latency: 2011ms
- Retrieved (2 docs):
  1. [Mahabharata] Mahabharata 1.152 (score=0.291)
     Text: यदाश्रौषं विविधांस तात मार्गान; गदायुद्धे मण्डलं संचरन्तम
मिथ्या हतं व...
  2. [Mahabharata] Mahabharata 1.130 (score=0.284)
     Text: यदा दरॊणॊ विविधान अस्त्रमार्गान; विदर्शयन समरे चित्रयॊधी
न पाण्डवाञ शर...

### ID 169: "hanumn chalisa benefits"
- Category: edge_typo | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Ramayana Sundara Kanda 1.1
- Latency: 2844ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.283)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.6 (score=0.279)
     Text: The patient should reside in a place which is warm and free from draug...
  3. [Patanjali Yoga Sutras] Concept — Yoga and Pranayama Benefits (score=0.253)
     Text: Benefits of yoga and pranayama from Patanjali Yoga Sutras and Bhagavad...
  4. [Bhagavad Gita] Bhagavad Gita 6.27 (score=0.249)
     Text: 6.27 Supreme Bliss verily comes to this Yogi whose mind is ite peacefu...
  5. [Bhagavad Gita] Bhagavad Gita 18.78 (score=0.244)
     Text: 18.78 Wherever is Krishna, the Lord of Yoga; wherever is Arjuna, the w...

### ID 186: "I have been going through a very difficult phase in my life where I lost my father recently and I am also facing problems at work and my relationship with my wife is not good and I don't know what to do and sometimes I feel like giving up on everything because nothing seems to be working out in my favor"
- Category: edge_long | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.47, Bhagavad Gita 18.66
- Latency: 2437ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.159 (score=0.283)
     Text: तमसा तव अभ्यवस्तीर्णॊ मॊह आविशतीव माम
संज्ञां नॊपलभे सूत मनॊ विह्वलतीव...
  2. [Ramayana] Ramayana sundarakanda 15.50 (score=0.280)
     Text: स्त्री प्रनष्टा इति कारुण्याद् आश्रिता इति आनृशम्स्यतः ।पत्नी नष्टा इत...
  3. [Ramayana] Ramayana sundarakanda 13.19 (score=0.279)
     Text: कथम् नु खलु कर्तव्यम् विषमम् प्रतिभाति मे ।अस्मिन्न् एवम् गते कर्ये प्...
  4. [Ramayana] Ramayana sundarakanda 35.59 (score=0.272)
     Text: विचित्य वनदुर्गाणि गिरिप्रस्रवणानि च ।अनासाद्य पदं देव्याः प्राणांस्त्...
  5. [Ramayana] Ramayana ayodhyakanda 109.23 (score=0.271)
     Text: श्रेष्ठं ह्यनार्यमेव स्याद्यद्भवानवधार्य्य माम् ।आह युक्तिकरैर्वाक्यैर...

### ID 187: "मैं एक बहुत कठिन दौर से गुज़र रहा हूँ जहाँ मेरे पिताजी का हाल ही में निधन हो गया है और मेरी नौकरी में भी समस्याएं हैं और मेरा परिवार भी बिखर रहा है और मुझे कोई रास्ता नहीं सूझ रहा कि मैं क्या करूँ क्योंकि सब कुछ गलत हो रहा है"
- Category: edge_long | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.47, Bhagavad Gita 18.66
- Latency: 2076ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 16.20 (score=0.279)
     Text: हन्त शीघ्रम् इतः गत्वा द्रक्ष्यामि च मही पतिः ।सह त्वम् परिवारेण सुखम्...
  2. [Mahabharata] Mahabharata 1.159 (score=0.274)
     Text: तमसा तव अभ्यवस्तीर्णॊ मॊह आविशतीव माम
संज्ञां नॊपलभे सूत मनॊ विह्वलतीव...
  3. [Ramayana] Ramayana sundarakanda 35.59 (score=0.272)
     Text: विचित्य वनदुर्गाणि गिरिप्रस्रवणानि च ।अनासाद्य पदं देव्याः प्राणांस्त्...
  4. [Ramayana] Ramayana ayodhyakanda 4.36 (score=0.272)
     Text: सीतया प्युपवस्तव्या रजनीयं मया सह ।एवमृत्विगुपाध्यायैस्सह मामुक्तवान् ...
  5. [Ramayana] Ramayana ayodhyakanda 2.39 (score=0.271)
     Text: निखिलेनानुपूर्व्याच्च पिता पुत्रानिवौरसान् ।शुश्रूषन्ते च वः शिष्याः क...

### ID 197: "How to balance the three doshas according to Ayurveda?"
- Category: ayurveda_specific | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1
- Latency: 1842ms
- Retrieved (7 docs):
  1. [Atharva Veda] Concept — Vedic Health Teachings and Ayurveda (score=0.965)
     Text: Health and healing in Vedic scriptures and Ayurveda. Atharva Veda 2.3....
  2. [Atharva Veda] Concept — Vedic Health and Healing Principles (score=0.292)
     Text: Vedic health principles from Atharva Veda and Ayurveda. Atharva Veda 2...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.3 (score=0.271)
     Text: Thereby, the vata and kapha-born diseases affecting the upper supracla...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch2.9 (score=0.269)
     Text: Turpeth, the three myrobalans, red physic nut, indigo, soap-pod, sweet...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch4.1 (score=0.268)
     Text: Thus the three groups of decoctives are complete...

### ID 198: "Ayurvedic remedies for stress and anxiety"
- Category: ayurveda_specific | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1, Atharva Veda 2.3.1
- Latency: 1985ms
- Retrieved (4 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.9 (score=0.307)
     Text: They are prescribed as digestive-stimulants,as antidotes to poison and...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.1 (score=0.285)
     Text: Indian jujube, horse gram, deodar, Indian groundsel, black gram linsee...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.2 (score=0.282)
     Text: The unguent of Indian groundsel turmeric and Indian be berberry, nardu...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.9 (score=0.264)
     Text: They are hot, acute, not ununctuous, pungent and saltish; and are used...

### ID 200: "ayurveda mein dosha balance kaise kare?"
- Category: ayurveda_specific | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1
- Latency: 2661ms
- Retrieved (6 docs):
  1. [Atharva Veda] Concept — Vedic Health Teachings and Ayurveda (score=0.957)
     Text: Health and healing in Vedic scriptures and Ayurveda. Atharva Veda 2.3....
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.2 (score=0.258)
     Text: The ointment prepared from Indian groundsel, guduch, liquorice, heart-...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.252)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  4. [Atharva Veda] Concept — Vedic Health and Healing Principles (score=0.252)
     Text: Vedic health principles from Atharva Veda and Ayurveda. Atharva Veda 2...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.7 (score=0.244)
     Text: The rooters are said to be sixteen and the fruiters nineteen. The prin...

### ID 202: "Ayurvedic daily routine for good health"
- Category: ayurveda_specific | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1
- Latency: 1958ms
- Retrieved (7 docs):
  1. [Atharva Veda] Concept — Vedic Health Teachings and Ayurveda (score=0.461)
     Text: Health and healing in Vedic scriptures and Ayurveda. Atharva Veda 2.3....
  2. [Atharva Veda] Concept — Vedic Health and Healing Principles (score=0.416)
     Text: Vedic health principles from Atharva Veda and Ayurveda. Atharva Veda 2...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.8 (score=0.313)
     Text: The measured diet not only does not impair one’s health but positively...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.8 (score=0.304)
     Text: By daily inunction a person becomes smooth in his limbs and plump, str...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.1 (score=0.295)
     Text: Indian jujube, horse gram, deodar, Indian groundsel, black gram linsee...

### ID 203: "What is Dinacharya in Ayurveda?"
- Category: ayurveda_specific | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1
- Latency: 1776ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.281)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.267)
     Text: That is named the Science of Life, wherein are laid down the good and ...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.1 (score=0.266)
     Text: the denunciation of quacks; and what indicates the best qualities of t...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.5 (score=0.259)
     Text: ‘Action,’ which is the cause of conjunction and disjunction, resides i...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.253)
     Text: The science relating to Life is regarded by the philosophers as the mo...

### ID 204: "आयुर्वेद में रोग प्रतिरोधक शक्ति कैसे बढ़ाएं?"
- Category: ayurveda_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1, Atharva Veda 10.2.1
- Latency: 2349ms
- Retrieved (6 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.296)
     Text: The ‘General’ is the cause of the increase of all things at all times ...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.2 (score=0.257)
     Text: The ointment prepared from Indian groundsel, guduch, liquorice, heart-...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.251)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  4. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.7 (score=0.241)
     Text: The rooters are said to be sixteen and the fruiters nineteen. The prin...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.240)
     Text: Shashtika rice, shali rice, green gram, rock-salt, emblic myrobalan ba...

### ID 205: "ayurveda ke according neend aur sleep cycle kaise theek kare?"
- Category: ayurveda_specific | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Charaka Samhita 1.1
- Latency: 2375ms
- Retrieved (4 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.8 (score=0.278)
     Text: One who has his head well oleated daily, does not get headache, baldne...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch3.2 (score=0.278)
     Text: The unguent of Indian groundsel turmeric and Indian be berberry, nardu...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.1 (score=0.265)
     Text: The urine of the mare is bitter and pungent and is curative of dermato...
  4. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 1.10 (score=0.261)
     Text: Sleep is the vritti of absence of mental contents for its support...

### ID 242: "गायत्री मंत्र का क्या अर्थ और महत्व है?"
- Category: mantra_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 3.62.10
- Latency: 2130ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Concept — Mantras for Peace and Healing (score=1.053)
     Text: Sacred mantras for peace and healing from Hindu scriptures. BG 8.13: o...
  2. [Bhagavad Gita] Bhagavad Gita 10.35 (score=0.437)
     Text: 10.35 Among the hymns also I am the Brihatsaman; among metres Gayatri ...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.275)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  4. [Bhagavad Gita] Bhagavad Gita 9.16 (score=0.273)
     Text: 9.16 I am the Kratu; I am the Yajna; I am the offering (food) to the m...
  5. [Ramayana] Ramayana ayodhyakanda 109.32 (score=0.269)
     Text: तेनैवमाज्ञाय यथावदर्थमेकोदयं सम्प्रतिपद्य विप्रा: ।धर्मं चरन्त: सकलं य...
