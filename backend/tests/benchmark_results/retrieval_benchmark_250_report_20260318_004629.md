# RAG Benchmark Report

Generated: 2026-03-18 00:46:29
Total queries: 244
Average latency: 4133ms | p50: 4024ms | p95: 5216ms | p99: 6323ms

## Regression Check

**STATUS: FAIL**

- FAIL: Hit@3 = 82.4% (threshold >= 97%)
- FAIL: MRR = 0.815 (threshold >= 0.85)
- FAIL: Scripture Accuracy@3 = 66.5% (threshold >= 70%)
- FAIL: p95 latency = 5216ms (threshold <= 2500ms)

## Overall Metrics

| Metric | Value |
|--------|-------|
| mrr | 0.815 |
| hit@1 | 78.3% |
| hit@3 | 82.4% |
| hit@5 | 86.1% |
| hit@7 | 88.9% |
| precision@3 | 0.507 |
| recall@3 | 0.575 |
| recall@7 | 0.688 |
| ndcg@3 | 0.807 |
| ndcg@5 | 0.816 |
| scripture_accuracy@3 | 66.5% |
| Temple Contamination | 0 queries |
| Meditation Noise | 3 queries |

## Latency Percentiles

| Percentile | Value |
|------------|-------|
| p50 | 4024ms |
| p95 | 5216ms |
| p99 | 6323ms |

## Per-Category Breakdown (sorted by MRR ascending)

| Category | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 | Temple | Med |
|----------|---|-----|-------|--------|-----|-----|-----------|--------|-----|
| edge_adversarial | 5 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| off_topic | 1 | 0.000 | 0.0% | 0.000 | 0.000 | 0.000 | 0.0% | 0 | 0 |
| edge_emoji_caps | 2 | 0.321 | 50.0% | 0.347 | 0.167 | 0.500 | 50.0% | 0 | 0 |
| anxiety | 3 | 0.333 | 33.3% | 0.333 | 0.111 | 0.067 | 11.1% | 0 | 0 |
| edge_long | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 0.333 | 33.3% | 0 | 0 |
| love | 3 | 0.333 | 33.3% | 0.307 | 0.222 | 0.167 | 33.3% | 0 | 0 |
| ayurveda_specific | 10 | 0.353 | 40.0% | 0.350 | 0.167 | 0.300 | 30.0% | 0 | 0 |
| death | 4 | 0.500 | 50.0% | 0.500 | 0.167 | 0.113 | 50.0% | 0 | 0 |
| relationships | 2 | 0.500 | 50.0% | 0.500 | 0.167 | 0.100 | 16.7% | 0 | 0 |
| health | 5 | 0.600 | 60.0% | 0.600 | 0.333 | 0.212 | 45.0% | 0 | 0 |
| edge_short | 5 | 0.629 | 60.0% | 0.584 | 0.267 | 0.400 | 60.0% | 0 | 0 |
| karma | 7 | 0.663 | 57.1% | 0.571 | 0.524 | 0.464 | 57.1% | 0 | 0 |
| yoga | 6 | 0.667 | 83.3% | 0.710 | 0.389 | 0.315 | 66.7% | 0 | 0 |
| liberation/moksha | 6 | 0.690 | 66.7% | 0.653 | 0.556 | 0.500 | 66.7% | 0 | 0 |
| ayurveda | 4 | 0.750 | 75.0% | 0.750 | 0.417 | 0.292 | 32.5% | 0 | 0 |
| duty | 4 | 0.750 | 75.0% | 0.750 | 0.583 | 0.348 | 45.8% | 0 | 0 |
| temple | 7 | 0.750 | 71.4% | 0.714 | 0.381 | 0.440 | 71.4% | 0 | 0 |
| mantra_specific | 10 | 0.764 | 80.0% | 0.761 | 0.333 | 0.650 | 75.0% | 0 | 0 |
| procedural | 12 | 0.787 | 75.0% | 0.750 | 0.333 | 0.528 | 52.8% | 0 | 3 |
| soul/atman | 5 | 0.800 | 80.0% | 0.800 | 0.600 | 0.550 | 80.0% | 0 | 0 |
| dharma | 9 | 0.833 | 77.8% | 0.778 | 0.370 | 0.289 | 66.7% | 0 | 0 |
| family | 6 | 0.833 | 83.3% | 0.833 | 0.500 | 0.375 | 38.9% | 0 | 0 |
| pregnancy_fertility | 3 | 0.833 | 100.0% | 0.898 | 0.333 | 0.500 | 50.0% | 0 | 0 |
| story_narrative | 10 | 0.842 | 80.0% | 0.800 | 0.267 | 0.700 | 70.0% | 0 | 0 |
| edge_typo | 7 | 0.878 | 85.7% | 0.846 | 0.429 | 0.857 | 85.7% | 0 | 0 |
| devotion | 14 | 0.893 | 92.9% | 0.901 | 0.786 | 0.543 | 67.3% | 0 | 0 |
| meditation | 6 | 0.917 | 100.0% | 0.938 | 0.722 | 0.540 | 69.4% | 0 | 0 |
| cross_scripture | 10 | 0.933 | 100.0% | 0.950 | 0.400 | 0.567 | 56.7% | 0 | 0 |
| edge_codeswitching | 8 | 0.938 | 100.0% | 0.962 | 0.542 | 0.875 | 87.5% | 0 | 0 |
| addiction | 4 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| anger | 6 | 1.000 | 100.0% | 1.000 | 0.778 | 0.556 | 80.6% | 0 | 0 |
| career_work | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| confusion | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| digital_life | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.714 | 75.0% | 0 | 0 |
| education_exam | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| ethics_moral | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| faith | 2 | 1.000 | 100.0% | 1.000 | 0.833 | 1.000 | 100.0% | 0 | 0 |
| fear | 5 | 1.000 | 100.0% | 1.000 | 0.733 | 0.667 | 60.0% | 0 | 0 |
| financial_stress | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| frustration | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| grief | 5 | 1.000 | 100.0% | 1.000 | 1.000 | 0.700 | 63.3% | 0 | 0 |
| guilt | 3 | 1.000 | 100.0% | 1.000 | 0.556 | 0.833 | 100.0% | 0 | 0 |
| habits_lust | 3 | 1.000 | 100.0% | 1.000 | 1.000 | 1.000 | 100.0% | 0 | 0 |
| hopelessness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| jealousy | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| loneliness | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| mantra | 2 | 1.000 | 100.0% | 1.000 | 0.333 | 0.238 | 32.1% | 0 | 0 |
| narrative | 2 | 1.000 | 100.0% | 1.000 | 0.667 | 0.417 | 75.0% | 0 | 0 |
| parenting | 2 | 1.000 | 100.0% | 1.000 | 0.333 | 0.417 | 50.0% | 0 | 0 |
| self-worth | 4 | 1.000 | 100.0% | 1.000 | 0.833 | 0.625 | 50.0% | 0 | 0 |
| shame | 3 | 1.000 | 100.0% | 1.000 | 0.667 | 1.000 | 100.0% | 0 | 0 |
| spiritual_practice | 2 | 1.000 | 100.0% | 1.000 | 0.333 | 0.375 | 50.0% | 0 | 0 |

## Per-Language Breakdown

| Language | N | MRR | Hit@3 | NDCG@3 | P@3 | R@3 | Scr.Acc@3 |
|----------|---|-----|-------|--------|-----|-----|-----------|
| en | 127 | 0.806 | 82.7% | 0.798 | 0.486 | 0.540 | 68.2% |
| hi | 62 | 0.672 | 66.1% | 0.661 | 0.457 | 0.518 | 51.8% |
| transliterated | 61 | 0.898 | 90.2% | 0.894 | 0.552 | 0.650 | 71.4% |

## Per-Query-Length Breakdown

| Length Bucket | N | MRR | Hit@3 | NDCG@3 | P@3 | Avg Latency |
|---------------|---|-----|-------|--------|-----|-------------|
| 1-3 words | 8 | 0.768 | 75.0% | 0.740 | 0.417 | 3761ms |
| 11-20 words | 45 | 0.881 | 88.9% | 0.875 | 0.578 | 4418ms |
| 20+ words | 3 | 0.333 | 33.3% | 0.333 | 0.333 | 4659ms |
| 4-10 words | 194 | 0.784 | 79.4% | 0.776 | 0.481 | 4070ms |

## Per-Match-Mode Breakdown

| Match Mode | N | MRR | Hit@3 | NDCG@3 | P@3 |
|------------|---|-----|-------|--------|-----|
| exact | 18 | 0.542 | 61.1% | 0.550 | 0.222 |
| scripture_level | 232 | 0.815 | 81.9% | 0.806 | 0.516 |

## Worst 15 Queries (by MRR)

### ID 29: "How to practice non-attachment while living in the world?"
- Category: liberation/moksha | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.47, Bhagavad Gita 3.19, Bhagavad Gita 5.7, Bhagavad Gita 12.12
- Latency: 4097ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 25.29 (score=0.293)
     Text: Kausalya, the excellent woman, provided. The preceptor, according to t...
  2. [Ramayana] Ramayana ayodhyakanda 25.28 (score=0.000)
     Text: She offered oblations according to the prescribed manner for the auspi...
  3. [Ramayana] Ramayana ayodhyakanda 25.30 (score=0.000)
     Text: With the remnants of the offerings, she prepared an external offering....
  4. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.40 (score=0.281)
     Text: From cleanliness there comes indifference towards body and nonattachme...
  5. [Patanjali Yoga Sutras] Patanjali Yoga Sutras 2.39 (score=0.000)
     Text: On becoming steady in non-possessiveness, there arises the knowledge o...

### ID 43: "शिव जी की पूजा कैसे करें?"
- Category: devotion | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Somnath (Gujarat), Rig Veda 7.59.12, Atharva Veda 11.2.1
- Latency: 4984ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 12.6 (score=1.165)
     Text: 12.6 But to those who worship Me, renouncing all actions in Me, regard...
  2. [Bhagavad Gita] Bhagavad Gita 12.5 (score=0.000)
     Text: 12.5 Greater is their trouble whose minds are set on the unmanifested;...
  3. [Bhagavad Gita] Bhagavad Gita 12.7 (score=0.000)
     Text: 12.7 To those whose minds are set on Me, O Arjuna, verily I become ere...
  4. [Bhagavad Gita] Bhagavad Gita 18.75 (score=1.159)
     Text: 18.75 Through the grace of Vyasa I have heard this supreme and most se...
  5. [Bhagavad Gita] Bhagavad Gita 18.74 (score=0.000)
     Text: 18.74 Sanjaya said  Thus I have heard this wonderful dialogue between ...

### ID 44: "भगवद गीता में आत्मा के बारे में क्या कहा गया है?"
- Category: soul/atman | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.17, Bhagavad Gita 2.18, Bhagavad Gita 2.19, Bhagavad Gita 2.20
- Latency: 4387ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1 2.56 (score=0.943)
     Text: पर्वॊक्तं भगवद गीता पर्व भीस्म वधस ततः
दरॊणाभिषेकः पर्वॊक्तं संशप्तक व...
  2. [Mahabharata] Mahabharata 1 2.55 (score=0.000)
     Text: जम्बू खण्ड विनिर्माणं पर्वॊक्तं तदनन्तरम
भूमिपर्व ततॊ जञेयं दवीपविस्तर...
  3. [Mahabharata] Mahabharata 1 2.57 (score=0.000)
     Text: अभिमन्युवधः पर्व परतिज्ञा पर्व चॊच्यते
जयद्रथवधः पर्व घटॊत्कच वधस ततः...
  4. [Ramayana] Ramayana sundarakanda 28.3 (score=0.939)
     Text: सत्यं बतेदं प्रवदन्ति लोके नाकालमृत्युर्भवतीति सन्तः ।यत्राहमेवं परिभर...
  5. [Ramayana] Ramayana sundarakanda 28.2 (score=0.000)
     Text: सा राक्षसीमध्यगता च भीरुर्वाग्भिर्भृशं रावणतर्जिता च ।कान्तारमध्ये विज...

### ID 51: "योग सूत्र में यम और नियम क्या हैं?"
- Category: yoga | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.30, Patanjali Yoga Sutras 2.31, Patanjali Yoga Sutras 2.32, Patanjali Yoga Sutras 2.35
- Latency: 3888ms
- Retrieved (7 docs):
  1. [Bhagavad Gita] Bhagavad Gita 6.21 (score=1.089)
     Text: 6.21 When he (the Yogi) feels that Infinite Bliss which can be grasped...
  2. [Bhagavad Gita] Bhagavad Gita 6.22 (score=0.000)
     Text: 6.22 Which, having obtained, he thinks there is no other gain superior...
  3. [Ramayana] Ramayana ayodhyakanda 16.24 (score=1.086)
     Text: पूर्वाम् दिशम् वज्रधरो दक्षिणाम् पातु ते यमः ।वरुणः पश्चिमामाशाम् धनेश...
  4. [Ramayana] Ramayana ayodhyakanda 16.23 (score=0.000)
     Text: दीक्षितम् व्रतसम्पन्नम् वराजिनधरम् शुचिम् ।कुरङ्गपाणिम् च पश्यन्ती त्व...
  5. [Ramayana] Ramayana ayodhyakanda 16.25 (score=0.000)
     Text: अथ सीतामनुज्ञाप्य कृतकौतुकमगLअः ।निश्चक्राम सुमन्त्रेण सह रामो निवेशना...

### ID 52: "आयुर्वेद में तीन दोष क्या हैं?"
- Category: ayurveda | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Atharva Veda 1.12.1, Atharva Veda 6.44.1, Rig Veda 10.97.1, Rig Veda 10.97.12
- Latency: 3524ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 35.17 (score=0.947)
     Text: त्रिस्थिरस्त्रिप्रलम्बश्च त्रिसमस्त्रिषु चोन्नतः ।त्रिताम्रस्त्रिषु च ...
  2. [Ramayana] Ramayana sundarakanda 35.16 (score=0.000)
     Text: दुन्दुभिस्वननिर्घोषः स्निग्धवर्णः प्रतापवान् ।समः समविभक्ताङ्गो वर्णं ...
  3. [Ramayana] Ramayana sundarakanda 35.18 (score=0.000)
     Text: त्रिवलीवांस्त्र्यवनतश्चतुर्व्यङ्गस्त्रिशीर्षवान् ।चतुष्कलश्चतुर्लेखश्च...
  4. [Mahabharata] Mahabharata 1 2.17 (score=0.945)
     Text: तरयॊ गुल्मा गणॊ नाम वाहिनी तु गणास तरयः
समृतास तिस्रस तु वाहिन्यः पृतन...
  5. [Mahabharata] Mahabharata 1 2.16 (score=0.000)
     Text: पत्तिं तु तरिगुणाम एताम आहुः सेनामुखं बुधाः
तरीणि सेनामुखान्य एकॊ गुल्...

### ID 53: "मृत्यु के बाद क्या होता है?"
- Category: death | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.22, Bhagavad Gita 8.5, Bhagavad Gita 8.6, Bhagavad Gita 15.8
- Latency: 4905ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.186 (score=1.092)
     Text: भवितव्यं तथा तच च नातः शॊचितुम अर्हसि
दैवं परज्ञा विशेषेण कॊ निवर्तितु...
  2. [Mahabharata] Mahabharata 1.185 (score=0.000)
     Text: निग्रहानुग्रहौ चापि विदितौ ते नराधिप
नात्यन्तम एवानुवृत्तिः शरूयते पुत...
  3. [Mahabharata] Mahabharata 1.187 (score=0.000)
     Text: विधातृविहितं मार्गं न कश चिद अतिवर्तते
कालमूलम इदं सर्वं भावाभावौ सुखा...
  4. [Ramayana] Ramayana sundarakanda 13.21 (score=1.090)
     Text: गमिष्यामि ततः को मे पुरुष अर्थो भविष्यति ।मम इदम् लन्घनम् व्यर्थम् साग...
  5. [Ramayana] Ramayana sundarakanda 13.20 (score=0.000)
     Text: भवेद् इति मतिम् भूयो हनुमान् प्रविचारयन् ।यदि सीताम् अदृष्ट्वा अहम् वा...

### ID 54: "भारत के प्रसिद्ध मंदिर कौन से हैं?"
- Category: temple | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Temple: Kashi Vishwanath (Uttar Pradesh), Temple: Tirupati Balaji (Andhra Pradesh), Temple: Jagannath (Odisha), Temple: Meenakshi (Tamil Nadu), Temple: Somnath (Gujarat)
- Latency: 5064ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 109.31 (score=0.940)
     Text: सत्यं च धर्मं च पराक्रमं च भूतानुकम्पां प्रियवादिताञ्च ।द्विजातिदेवाति...
  2. [Ramayana] Ramayana ayodhyakanda 109.30 (score=0.000)
     Text: अमृष्यमाण: पुनरुग्रतेजा निशम्य तन्नास्तिकवाक्यहेतुम् ।अथाब्रवीत्तं नृप...
  3. [Ramayana] Ramayana ayodhyakanda 109.36 (score=0.939)
     Text: धर्मे रता: सत्पुरुषै: समेतास्तेजस्विनो दानगुणप्रधाना: ।अहिंसका वीतमलाश...
  4. [Ramayana] Ramayana ayodhyakanda 109.35 (score=0.000)
     Text: त्वत्तो जना: पूर्वतरे वराश्च शुभानि कर्माणि बहूनि चक्रु: ।जित्वा सदेमं...
  5. [Ramayana] Ramayana ayodhyakanda 109.37 (score=0.000)
     Text: इति ब्रुवन्तं वचनं सरोषं रामं महात्मानमदीनसत्त्वम् ।उवाच तथ्यं पुनरास्...

### ID 55: "भगवान से प्रेम कैसे करें?"
- Category: love | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 9.29, Bhagavad Gita 12.14, Bhagavad Gita 18.65, Bhagavad Gita 18.55
- Latency: 5808ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 11.8 (score=1.090)
     Text: रत अभिरत सम्सुप्तम् ददर्श हरि यूथपः ।तासाम् मध्ये महा बाहुः शुशुभे राक...
  2. [Ramayana] Ramayana sundarakanda 11.7 (score=0.000)
     Text: रूप सम्ल्लाप शीलेन युक्त गीत अर्थ भाषिणा ।देश काल अभियुक्तेन युक्त वाक...
  3. [Ramayana] Ramayana sundarakanda 11.9 (score=0.000)
     Text: गोष्ठे महति मुख्यानाम् गवाम् मध्ये यथा वृषः ।स राक्षस इन्द्रः शुशुभे त...
  4. [Ramayana] Ramayana sundarakanda 35.2 (score=1.088)
     Text: क्व ते रामेण संसर्गः कथं जानासि लक्ष्मणम् ।वानराणां नराणां च कथमासीत् ...
  5. [Ramayana] Ramayana sundarakanda 35.1 (score=0.000)
     Text: तां तु रामकथां श्रुत्वा वैदेही वानरार्षभात् ।उवाच वचनं सान्त्वमिदं मधु...

### ID 59: "स्वस्थ जीवन के लिए वैदिक उपाय"
- Category: health | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Atharva Veda 2.3.1, Rig Veda 10.97.1, Bhagavad Gita 6.17, Bhagavad Gita 17.8
- Latency: 6631ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 109.19 (score=0.928)
     Text: प्रत्यगात्ममिमं धर्मं सत्यं पश्याम्यहं स्वयम् ।भार: सत्पुरुषाचीर्णस्तद...
  2. [Ramayana] Ramayana ayodhyakanda 109.18 (score=0.000)
     Text: The tumultuous sound vibrated throughout the sky and the earth, shatte...
  3. [Ramayana] Ramayana ayodhyakanda 109.20 (score=0.000)
     Text: क्षात्ऺत्रं धर्ममहं त्यक्ष्ये ह्यधर्मं धर्मसंहितम् ।क्षुद्रैर्नृशंसैर्...
  4. [Ramayana] Ramayana ayodhyakanda 109.31 (score=0.927)
     Text: सत्यं च धर्मं च पराक्रमं च भूतानुकम्पां प्रियवादिताञ्च ।द्विजातिदेवाति...
  5. [Ramayana] Ramayana ayodhyakanda 109.30 (score=0.000)
     Text: अमृष्यमाण: पुनरुग्रतेजा निशम्य तन्नास्तिकवाक्यहेतुम् ।अथाब्रवीत्तं नृप...

### ID 71: "parivar mein pyaar aur shanti kaise laaye"
- Category: family | Language: transliterated | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.9, Bhagavad Gita 13.8, Rig Veda 10.191.2, Rig Veda 10.191.4
- Latency: 4426ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 95.16 (score=0.321)
     Text: Translation: "And Lakshmana, the virtuous one, is steadfast in my comm...
  2. [Ramayana] Ramayana ayodhyakanda 95.15 (score=0.000)
     Text: Translation: "O lady, always consider this mountain as Ayodhya, like t...
  3. [Ramayana] Ramayana ayodhyakanda 95.17 (score=0.000)
     Text: Translation: "Touching the water at the three junctures of the day, ea...
  4. [Ramayana] Ramayana yudhhakanda 30.18 (score=0.319)
     Text: तथात्र प्रतिपत्स्यामि ज्ञात्वा तेषाम् बल अबलम् ।अवश्यम् बल सम्ख्यानम् ...
  5. [Ramayana] Ramayana yudhhakanda 30.17 (score=0.000)
     Text: कीदृशाः किम् प्रभावाः च वानरा ये दुरासदाः ।कस्य पुत्राः च पौत्राः च तत...

### ID 84: "How do I stop overthinking everything?"
- Category: anxiety | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 6.35, Bhagavad Gita 2.66, Patanjali Yoga Sutras 1.2
- Latency: 4869ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 25.29 (score=0.292)
     Text: Kausalya, the excellent woman, provided. The preceptor, according to t...
  2. [Ramayana] Ramayana ayodhyakanda 25.28 (score=0.000)
     Text: She offered oblations according to the prescribed manner for the auspi...
  3. [Ramayana] Ramayana ayodhyakanda 25.30 (score=0.000)
     Text: With the remnants of the offerings, she prepared an external offering....
  4. [Ramayana] Ramayana ayodhyakanda 9.19 (score=0.276)
     Text: Because of my affection for you, this story is held in my mind. Stop a...
  5. [Ramayana] Ramayana ayodhyakanda 9.18 (score=0.000)
     Text: The great-souled king said, "So be it." I was unaware, O Devi, but you...

### ID 159: "सूर्य नमस्कार कैसे करें?"
- Category: procedural | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Patanjali Yoga Sutras 2.46
- Latency: 4066ms
- Retrieved (7 docs):
  1. [Mahabharata] Mahabharata 1.129 (score=1.080)
     Text: यदाश्रौषं शुक्रसूर्यौ च युक्तौ; कौन्तेयानाम अनुलॊमौ जयाय
नित्यं चास्मा...
  2. [Mahabharata] Mahabharata 1.128 (score=0.000)
     Text: यदाश्रौषं शांतनवे शयाने; पानीयार्थे चॊदितेनार्जुनेन
भूमिं भित्त्वा तर्...
  3. [Mahabharata] Mahabharata 1.130 (score=0.000)
     Text: यदा दरॊणॊ विविधान अस्त्रमार्गान; विदर्शयन समरे चित्रयॊधी
न पाण्डवाञ शर...
  4. [Ramayana] Ramayana sundarakanda 35.2 (score=1.076)
     Text: क्व ते रामेण संसर्गः कथं जानासि लक्ष्मणम् ।वानराणां नराणां च कथमासीत् ...
  5. [Ramayana] Ramayana sundarakanda 35.1 (score=0.000)
     Text: तां तु रामकथां श्रुत्वा वैदेही वानरार्षभात् ।उवाच वचनं सान्त्वमिदं मधु...

### ID 185: "grief"
- Category: edge_short | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.13
- Latency: 3524ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 62.5 (score=0.295)
     Text: The lord, tormented by that grief and by the grief of Rama, the great ...
  2. [Ramayana] Ramayana ayodhyakanda 62.4 (score=0.000)
     Text: As he was thinking, the evil deed he had done in the past, unknowingly...
  3. [Ramayana] Ramayana ayodhyakanda 62.6 (score=0.000)
     Text: Burning with sorrows, the king, with trembling hands folded in supplic...
  4. [Ramayana] Ramayana ayodhyakanda 21.47 (score=0.286)
     Text: "O Mother, restrain your grief in your heart; do not sorrow. I will re...
  5. [Ramayana] Ramayana ayodhyakanda 21.46 (score=0.000)
     Text: "Having fulfilled my vow, I shall return to this city from the forest,...

### ID 186: "I have been going through a very difficult phase in my life where I lost my father recently and I am also facing problems at work and my relationship with my wife is not good and I don't know what to do and sometimes I feel like giving up on everything because nothing seems to be working out in my favor"
- Category: edge_long | Language: en | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.47, Bhagavad Gita 18.66
- Latency: 4580ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana sundarakanda 15.50 (score=0.288)
     Text: स्त्री प्रनष्टा इति कारुण्याद् आश्रिता इति आनृशम्स्यतः ।पत्नी नष्टा इत...
  2. [Ramayana] Ramayana sundarakanda 15.49 (score=0.000)
     Text: इयम् सा यत् कृते रामः चतुर्भिः परितप्यते ।कारुण्येन आनृशम्स्येन शोकेन ...
  3. [Ramayana] Ramayana sundarakanda 15.51 (score=0.000)
     Text: अस्या देव्या यथा रूपम् अन्ग प्रत्यन्ग सौष्ठवम् ।रामस्य च यथा रूपम् तस्...
  4. [Ramayana] Ramayana ayodhyakanda 64.67 (score=0.288)
     Text: What could be more sorrowful than this, that as my life wanes, I do no...
  5. [Ramayana] Ramayana ayodhyakanda 64.66 (score=0.000)
     Text: I cannot see you with my eyes; my memory is failing. These messengers ...

### ID 187: "मैं एक बहुत कठिन दौर से गुज़र रहा हूँ जहाँ मेरे पिताजी का हाल ही में निधन हो गया है और मेरी नौकरी में भी समस्याएं हैं और मेरा परिवार भी बिखर रहा है और मुझे कोई रास्ता नहीं सूझ रहा कि मैं क्या करूँ क्योंकि सब कुछ गलत हो रहा है"
- Category: edge_long | Language: hi | Match: scripture_level
- MRR: 0.000 | Hit@3: No | Hit@7: No | NDCG@3: 0.000
- Ground truth: Bhagavad Gita 2.11, Bhagavad Gita 2.47, Bhagavad Gita 18.66
- Latency: 5382ms
- Retrieved (7 docs):
  1. [Ramayana] Ramayana ayodhyakanda 109.31 (score=1.083)
     Text: सत्यं च धर्मं च पराक्रमं च भूतानुकम्पां प्रियवादिताञ्च ।द्विजातिदेवाति...
  2. [Ramayana] Ramayana ayodhyakanda 109.30 (score=0.000)
     Text: अमृष्यमाण: पुनरुग्रतेजा निशम्य तन्नास्तिकवाक्यहेतुम् ।अथाब्रवीत्तं नृप...
  3. [Ramayana] Ramayana ayodhyakanda 109.32 (score=0.000)
     Text: तेनैवमाज्ञाय यथावदर्थमेकोदयं सम्प्रतिपद्य विप्रा: ।धर्मं चरन्त: सकलं य...
  4. [Ramayana] Ramayana sundarakanda 28.3 (score=1.083)
     Text: सत्यं बतेदं प्रवदन्ति लोके नाकालमृत्युर्भवतीति सन्तः ।यत्राहमेवं परिभर...
  5. [Ramayana] Ramayana sundarakanda 28.2 (score=0.000)
     Text: सा राक्षसीमध्यगता च भीरुर्वाग्भिर्भृशं रावणतर्जिता च ।कान्तारमध्ये विज...
