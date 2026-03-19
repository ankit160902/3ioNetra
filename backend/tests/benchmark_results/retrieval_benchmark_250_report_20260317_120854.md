# RAG Benchmark Report

Generated: 2026-03-17 12:08:54
Total queries: 244
Average latency: 1426ms | p50: 1341ms | p95: 2164ms | p99: 2394ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 94.7% (threshold >= 97%)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.889 |
| hit@1 | 83.6% |
| hit@3 | 94.7% |
| hit@5 | 95.9% |
| hit@7 | 96.3% |
| precision@3 | 0.587 |
| recall@3 | 0.654 |
| recall@7 | 0.772 |
| ndcg@3 | 0.897 |
| ndcg@5 | 0.898 |
| scripture_accuracy@3 | 79.9% |
| Temple Contamination | 0 queries |
| Meditation Noise | 4 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 1341ms |
| p95 | 2164ms |
| p99 | 2394ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| relationships | 2 | 0.183 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| edge_long | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 0.333 | 33.3% | 0 | 0 |
| mantra_specific | 10 | 0.475 | 50.0% | 0.463 | 0.233 | 0.450 | 50.0% | 0 | 0 |
| edge_emoji_caps | 2 | 0.500 | 100.0% | 0.662 | 0.500 | 1.000 | 100.0% | 0 | 0 |
| edge_typo | 7 | 0.643 | 71.4% | 0.670 | 0.381 | 0.714 | 71.4% | 0 | 0 |
| confusion | 3 | 0.667 | 100.0% | 0.796 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| procedural | 12 | 0.771 | 83.3% | 0.765 | 0.361 | 0.597 | 59.7% | 0 | 4 |
| ayurveda_specific | 10 | 0.817 | 100.0% | 0.869 | 0.433 | 0.900 | 90.0% | 0 | 0 |
| anxiety | 3 | 0.833 | 100.0% | 0.850 | 0.444 | 0.411 | 72.2% | 0 | 0 |
| financial_stress | 3 | 0.833 | 100.0% | 0.877 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| yoga | 6 | 0.833 | 100.0% | 0.887 | 0.556 | 0.440 | 83.3% | 0 | 0 |
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
| en | 127 | 0.817 | 90.6% | 0.835 | 0.530 | 0.590 | 77.8% |
| hi | 62 | 0.925 | 95.2% | 0.926 | 0.651 | 0.687 | 79.0% |
| transliterated | 61 | 0.917 | 93.4% | 0.909 | 0.585 | 0.689 | 77.3% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.792 | 87.5% | 0.792 | 0.542 | 2232ms |
| 11-20 words | 45 | 0.956 | 100.0% | 0.964 | 0.593 | 1317ms |
| 20+ words | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 1537ms |
| 4-10 words | 194 | 0.859 | 91.8% | 0.867 | 0.574 | 1400ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.546 | 66.7% | 0.581 | 0.259 |
| scripture_level | 232 | 0.893 | 94.4% | 0.899 | 0.598 |

## Worst 15 Queries (by MRR)

### ID 161: "What are the steps for performing a havan at home?"
- Category: procedural | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 4.24, Rig Veda 1.1
- Latency: 945ms
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
- Latency: 894ms
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
- Ground truth: Ramayana sundarakanda 1.1
- Latency: 1827ms
- Retrieved (7 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.283)
     Text: The benefits of nasal medications; their procedures, which kind of nas...
  2. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.6 (score=0.279)
     Text: The patient should reside in a place which is warm and free from draug...
  3. [Patanjali Yoga Sutras] Concept — Yoga and Pranayama Benefits (score=0.253)
     Text: Benefits of yoga and pranayama from Patanjali Yoga Sutras and Bhagavad...
  4. [Bhagavad Gita] Bhagavad Gita 6.27 (score=0.249)
     Text: 6.27 Supreme Bliss verily comes to this Yogi whose mind is ite peacefu...
  5. [Bhagavad Gita] Bhagavad Gita 18.78 (score=0.245)
     Text: 18.78 Wherever is Krishna, the Lord of Yoga; wherever is Arjuna, the w...

### ID 186: "I have been going through a very difficult phase in my life where I lost my father recently and I am also facing problems at work and my relationship with my wife is not good and I don't know what to do and sometimes I feel like giving up on everything because nothing seems to be working out in my favor"
- Category: edge_long | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.47, Bhagavad Gita 18.66
- Latency: 1242ms
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
- Latency: 1941ms
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

### ID 242: "गायत्री मंत्र का क्या अर्थ और महत्व है?"
- Category: mantra_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 3.62
- Latency: 1842ms
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

### ID 243: "gayatri mantra ka arth aur mahatva kya hai?"
- Category: mantra_specific | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 3.62
- Latency: 2007ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Concept — Mantras for Peace and Healing (score=1.053)
     Text: Sacred mantras for peace and healing from Hindu scriptures. BG 8.13: o...
  2. [Bhagavad Gita] Bhagavad Gita 10.35 (score=0.442)
     Text: 10.35 Among the hymns also I am the Brihatsaman; among metres Gayatri ...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.279)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  4. [Bhagavad Gita] Bhagavad Gita 9.16 (score=0.276)
     Text: 9.16 I am the Kratu; I am the Yajna; I am the offering (food) to the m...
  5. [Bhagavad Gita] Bhagavad Gita 18.30 (score=0.274)
     Text: 18.30 The intellect which knows the path of work and renunciation, wha...

### ID 249: "महामृत्युंजय मंत्र कब और कैसे जपें?"
- Category: mantra_specific | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Rig Veda 7.59
- Latency: 1865ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 9.16 (score=0.291)
     Text: 9.16 I am the Kratu; I am the Yajna; I am the offering (food) to the m...
  2. [Ramayana] Ramayana ayodhyakanda 72.52 (score=0.284)
     Text: When your intellect, bewildered by the scriptures, becomes unwavering ...
  3. [Bhagavad Gita] Bhagavad Gita 6.20 (score=0.283)
     Text: 6.20 When the mind, restrained by the practice of Yoga attains to quie...
  4. [Bhagavad Gita] Bhagavad Gita 15.8 (score=0.282)
     Text: 15.8 When the Lord (as the individual soul) obtains a body and when He...
  5. [Bhagavad Gita] Bhagavad Gita 4.10 (score=0.278)
     Text: 4.10 Freed from attachment, fear and anger, absorbed in Me, taking ref...

### ID 250: "hanuman chalisa padhne ke kya fayde hain?"
- Category: mantra_specific | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Ramayana sundarakanda 1.1
- Latency: 1975ms
- Retrieved (3 docs):
  1. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.292)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  2. [Bhagavad Gita] Bhagavad Gita 13.4 (score=0.275)
     Text: 13.4 What the field is and of what nature, what are its modifications ...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.272)
     Text: That is named the Science of Life, wherein are laid down the good and ...

### ID 81: "I'm going through a really tough breakup and feel lost"
- Category: relationships | Language: en | Match: scripture_level
- MRR: 0.167 | Hit@3: No | Hit@7: Yes | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.14, Bhagavad Gita 2.47, Bhagavad Gita 6.5
- Latency: 907ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 35.57 (score=0.292)
     Text: तेषां नो विप्रनष्टानां विन्ध्ये पर्वतसत्तमे ।भृशं शोकपरीतानामहोरात्रगण...
  2. [Ramayana] Ramayana ayodhyakanda 16.20 (score=0.290)
     Text: हन्त शीघ्रम् इतः गत्वा द्रक्ष्यामि च मही पतिः ।सह त्वम् परिवारेण सुखम्...
  3. [Ramayana] Ramayana sundarakanda 15.39 (score=0.290)
     Text: दुह्खेन बुबुधे सीताम् हनुमान् अनलम्कृताम् ।सम्स्कारेण यथा हीनाम् वाचम्...
  4. [Ramayana] Ramayana sundarakanda 11.44 (score=0.287)
     Text: न शक्यम् प्रमदा नष्टा मृगीषु परिमार्गितुम् ।तद् इदम् मार्गितम् तावत् श...
  5. [Ramayana] Ramayana sundarakanda 35.39 (score=0.287)
     Text: तानि रामाय दत्तानि मयैवोपहृतानि च ।स्वनवन्त्यवकीर्णानि तस्मिन् विगतचेत...

### ID 213: "rishton mein problem hai kya karu?"
- Category: relationships | Language: transliterated | Match: scripture_level
- MRR: 0.200 | Hit@3: No | Hit@7: Yes | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.5, Bhagavad Gita 12.13
- Latency: 1841ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 13.19 (score=0.301)
     Text: कथम् नु खलु कर्तव्यम् विषमम् प्रतिभाति मे ।अस्मिन्न् एवम् गते कर्ये प्...
  2. [Ramayana] Ramayana ayodhyakanda 4.15 (score=0.295)
     Text: न किञ्चिन्म कर्तव्यं तवान्यत्राभिषेचनात् ।अतो युत्त्वामहं ब्रूयां तन्म...
  3. [Mahabharata] Mahabharata 1 3.107 (score=0.292)
     Text: स एनम अभिवाद्यॊवाच
भगवन पौष्यः खल्व अहम
किं करवाणीति...
  4. [Ramayana] Ramayana ayodhyakanda 109.23 (score=0.286)
     Text: श्रेष्ठं ह्यनार्यमेव स्याद्यद्भवानवधार्य्य माम् ।आह युक्तिकरैर्वाक्यैर...
  5. [Bhagavad Gita] Bhagavad Gita 16.24 (score=0.285)
     Text: 16.24 Therefore, let the scripture be thy authority in determining wha...

### ID 162: "How to chant Om correctly?"
- Category: procedural | Language: en | Match: scripture_level
- MRR: 0.250 | Hit@3: No | Hit@7: Yes | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 8.13, Patanjali Yoga Sutras 1.27
- Latency: 872ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 35.2 (score=0.282)
     Text: क्व ते रामेण संसर्गः कथं जानासि लक्ष्मणम् ।वानराणां नराणां च कथमासीत् ...
  2. [Ramayana] Ramayana ayodhyakanda 72.53 (score=0.282)
     Text: Arjuna asked: What are the characteristics of one who is steady in wis...
  3. [Sanatan Scriptures] Sanatan Scriptures Home Altar.Setup Guide (score=0.278)
     Text: How to set up a simple home altar: 1. Choose a clean, quiet space faci...
  4. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.39 (score=0.270)
     Text: On becoming steady in non-possessiveness, there arises the knowledge o...
  5. [Mahabharata] Mahabharata 1 2.131 (score=0.269)
     Text: यत्र परविश्य नगरं छद्मभिर नयवसन्त ते
दुरात्मनॊ वधॊ यत्र कीचकस्य वृकॊदर...

### ID 246: "Om Namah Shivaya ka kya mahatva hai?"
- Category: mantra_specific | Language: transliterated | Match: scripture_level
- MRR: 0.250 | Hit@3: No | Hit@7: Yes | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 8.13
- Latency: 2030ms
- Retrieved (7 docs):
  1. [Rig Veda] Concept — Om Namah Shivaya Meaning and Significance (score=1.121)
     Text: Om Namah Shivaya — the most sacred Shiva mantra. RV 7.59.12: tryambaka...
  2. [Atharva Veda] Concept — Shiva Puja Vidhi and Worship (score=0.527)
     Text: Shiva Puja Vidhi — how to worship Lord Shiva. Atharva Veda 11.2.1: Hom...
  3. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch5.1 (score=0.285)
     Text: Which articles should be kept in the mouth and why; what are the advan...
  4. [Bhagavad Gita] Bhagavad Gita 13.4 (score=0.277)
     Text: 13.4 What the field is and of what nature, what are its modifications ...
  5. [Charaka Samhita (Ayurveda)] Charaka Samhita (Ayurveda) charaka_samhita_sutrasthana_ch1.4 (score=0.275)
     Text: That is named the Science of Life, wherein are laid down the good and ...

### ID 29: "How to practice non-attachment while living in the world?"
- Category: liberation/moksha | Language: en | Match: scripture_level
- MRR: 0.333 | Hit@3: Yes | Hit@7: Yes | NDCG@3: 0.500
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 3.19, Bhagavad Gita 5.7, Bhagavad Gita 12.12
- Latency: 968ms
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
- Category: temple | Language: en | Match: exact
- MRR: 0.333 | Hit@3: Yes | Hit@7: Yes | NDCG@3: 0.500
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Temple: Mallikarjuna (Andhra Pradesh), Temple: Omkareshwar (Madhya Pradesh), Temple: Kedarnath (Uttarakhand)
- Latency: 952ms
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
