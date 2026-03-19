# 3ioNetra Mitra — Panchang Integration Test Report

**Run:** 2026-03-18 10:56:23
**Target:** `http://localhost:8080`
**Total Cases:** 10
**Cases Passed:** 0 | **Cases Failed:** 10
**Total Checks:** 5 | **Passed:** 5 | **Failed:** 0 | **Errors:** 34
**Pass Rate:** 100.0%

---

## Current Panchang State

| Field | Value |
|-------|-------|
| Tithi | Amavasya |
| Nakshatra | Purva Bhadrapada |
| Yoga | Shubha |
| Karana | Chatushpada |
| Vaara | Wednesday |
| Special Day | Today is Amavasya (New Moon). A powerful time for ancestral prayers and inner reflection. |
| Is Special | True |

---

## Category Breakdown

| Category | Cases | Panchang Checks | Pass% |
|----------|-------|-----------------|-------|
| A: Direct Panchang Queries | 3 | 0/0 | N/A |
| B: Natural Weaving in Guidance | 3 | 0/0 | N/A |
| C: Special Day Awareness | 2 | 0/0 | N/A |
| D: No-Data-Dump / Restraint | 2 | 0/0 | N/A |

---

## Panchang Accuracy Failures

None! No hallucinated panchang values detected.

---

## Data Dump Violations

None! No raw panchang data dumps detected.

---

## Detailed Results

### A: Direct Panchang Queries

#### Case #1: Direct Tithi Query (Hindi) [FAIL]

**Turn 1**
- **User:** namaste
- **Bot (listening):** Namaste. It is good to connect with you.

Today is Amavasya, a day with a unique stillness to it. Since you feel a connection with Shiva, it is a powerful time for inner work.

Tonight, if you feel called, you could light a small diya and sit quietly for a few minutes, just being present with the darkness and the light.
- **Signals:** `{}`
  - [PASS] Response is non-empty: 321 chars
  - [PASS] No markdown formatting: clean
  - [PASS] No hollow/banned phrases: clean
  - [PASS] No product URLs in text: clean
  - [PASS] Response under 150 words: 61 words (limit 150)

**Turn 2**
- **User:** aaj ka tithi kya hai?
- **ERROR:** Server disconnected without sending a response.

**Turn 3**
- **User:** aur koi special din hai aaj?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #2: Direct Nakshatra Query [FAIL]

**Turn 1**
- **User:** namaste
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** aaj ka nakshatra kya hai? kya puja karni chahiye?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** is nakshatra mein kya karna shubh hai?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #3: Auspiciousness Query for Meditation [FAIL]

**Turn 1**
- **User:** hii
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** main meditation start karna chahti hoon. kya aaj ka din shubh hai?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** kitne baje karna chahiye?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

### B: Natural Weaving in Guidance

#### Case #4: Career Guidance — Natural Panchang Weaving [FAIL]

**Turn 1**
- **User:** namaste
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** job change karna hai but bahut confused hoon
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** 2 saal se growth nahi ho rahi. manager bhi supportive nahi hai
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 4**
- **User:** koi practice batao jo clarity de sake
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #5: Family Tension — Natural Panchang Weaving [FAIL]

**Turn 1**
- **User:** namaste
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** ghar mein bahut tension hai. pati se baat nahi ho rahi
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** lagta hai sab toot raha hai. bachche bhi pareshaan hain
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 4**
- **User:** kuch upay batao na. kya karu?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #6: Spiritual Growth — Natural Panchang Weaving [FAIL]

**Turn 1**
- **User:** pranam
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** retirement ke baad spiritual path pe aana chahta hoon
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** pehle bahut pooja karta tha. ab phir se shuru karna hai
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 4**
- **User:** koi mantra suggest karo jo daily kar sakun
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

### C: Special Day Awareness

#### Case #7: Special Day Inquiry [FAIL]

**Turn 1**
- **User:** namaste
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** aaj kuch vishesh hai kya? koi vrat ya pooja karni chahiye?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** acha, aur kya karna chahiye aaj?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #8: Timing Inquiry for New Practice [FAIL]

**Turn 1**
- **User:** namaste
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** koi naya practice start karna chahta hoon. kab shuru karu?
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** acha, aur koi mantra bhi batao
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

### D: No-Data-Dump / Restraint

#### Case #9: Friendship Breakdown — No Panchang Intrusion [FAIL]

**Turn 1**
- **User:** hey
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** best friend ne baat karna band kar diya
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** 15 saal ki dosti thi. ek din achanak sab khatam
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 4**
- **User:** bahut akela feel ho raha hai
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---

#### Case #10: Spousal Bereavement — No Panchang Intrusion [FAIL]

**Turn 1**
- **User:** pranam
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 2**
- **User:** patni ka dehant ho gaya
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 3**
- **User:** 40 saal ka saath tha. ab ghar soona lag raha hai
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

**Turn 4**
- **User:** ghar mein sannata hai. kisi se baat karne ka mann nahi
- **ERROR:** HTTP 500: {"detail":"RAG pipeline not available"}

---
