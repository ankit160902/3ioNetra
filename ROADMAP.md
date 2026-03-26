# 3ioNetra — Product Roadmap

## Context
GitaGPT has 35M+ users, 10 avatars, WhatsApp bot, voice I/O in 22 languages, community features, video avatars, and a subscription model. 3ioNetra has superior RAG, empathetic conversation, multi-scripture sources, safety protocol, panchang, and e-commerce — but lacks engagement loops and multi-modal features. This roadmap closes every gap while preserving 3ioNetra's unfair advantages.

---

## Phase 1: Multi-Modal (Weeks 1-4) — Match GitaGPT's Strengths

### 1.1 Voice Input (Speech-to-Text)
- Use Whisper API or Google Speech-to-Text for Hindi/English/regional
- User records voice → STT → existing CompanionEngine → TTS response
- Works on web/mobile
- **Files:** New `backend/services/stt_service.py`, update `backend/routers/chat.py`

### 1.2 Regional Languages (10 minimum)
- Hindi, English, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Punjabi, Malayalam
- Gemini 2.5 Flash already supports all these natively
- The prompt already says "mirror the user's language" — just need STT/TTS in regional languages
- Use Google Cloud TTS (supports all 10) to replace gTTS
- **Files:** Update `backend/services/tts_service.py`

### 1.3 Multiple Avatar Personas
- Add deity-specific personas alongside Mitra: Krishna, Shiva, Hanuman, Durga, Ganesha
- Each avatar = different system_instruction in YAML (tone, mantras, stories, personality)
- User selects avatar or system auto-selects based on preferred_deity
- Mitra remains default — avatars are opt-in
- **Files:** New YAML files in `backend/prompts/`, update `backend/llm/service.py` to load per-avatar prompts

### 1.4 AI Avatar Video (Stretch Goal)
- Use D-ID, HeyGen, or Synthesia API for talking-head video responses
- Generate short (10-15s) avatar clips for key guidance moments
- Expensive per-clip — gate behind paid tier
- **Files:** New `backend/services/avatar_video_service.py`

---

## Phase 2: Engagement & Retention (Weeks 5-8) — Surpass GitaGPT

### 2.1 Daily Sadhana System
- **Morning Darshan:** Push notification with today's panchang + shloka + deity image
- **Daily Shloka:** Contextual verse based on user's life area (not random — use domain compass)
- **Evening Reflection:** "How was your day? Did you try the practice?" prompt
- **Weekly Digest:** Summary of practices tried, emotional arc, spiritual growth
- Scheduled via cron/Cloud Scheduler → push notification
- **Files:** New `backend/services/daily_sadhana_service.py`, new `backend/routers/notifications.py`

### 2.2 Spiritual Growth Tracker
- Track: practices completed, mantras chanted, temples visited, consecutive days active
- Visual progress: "Your Sadhana Streak: 14 days" with flame icon
- Milestone badges: "Completed 108 mantras", "7-day meditation streak"
- Stored in MongoDB per user
- **Files:** New `backend/services/growth_tracker.py`, new `backend/models/growth.py`

### 2.3 Guided Meditation Library
- 10-15 pre-recorded guided meditations (5-20 min each)
- Categories: anxiety, sleep, focus, grief, morning, evening
- Generated via high-quality TTS or recorded by real practitioners
- Streamed from cloud storage (GCS/S3)
- **Files:** New `backend/routers/meditation.py`, cloud storage for audio files

### 2.4 Festival Calendar & Reminders
- Auto-detect upcoming festivals from panchang service
- Push notifications: "Tomorrow is Maha Shivaratri — here's how to observe it"
- Festival-specific rituals, mantras, and significance auto-generated
- **Files:** Enhance `backend/services/panchang_service.py`

---

## Phase 3: Community (Weeks 9-12) — GitaGPT's Moat, Replicated Better

### 3.1 Satsang Rooms (Live Audio)
- Live audio rooms (like Twitter Spaces / Clubhouse)
- Topics: relationships, career, grief, spiritual practice
- Use Agora.io or LiveKit for real-time audio
- Scheduled satsangs + spontaneous rooms
- **Files:** New `backend/services/satsang_service.py`, frontend components

### 3.2 Anonymous Peer Support
- Users share experiences anonymously, others respond with support
- Karma points for helping others
- Moderated by AI (safety validator) + human moderators
- **Files:** New `backend/routers/community.py`, new `backend/models/community.py`

### 3.3 Human Guru Sessions
- Partner with verified spiritual teachers / pandits
- Paid 1-on-1 video sessions (15-30 min) via Zoom/Google Meet
- Revenue share model (70/30)
- **Files:** New `backend/services/guru_booking_service.py`

### 3.4 Seekers Leaderboard
- Points for: daily login, practice completion, helping others, satsang participation
- Weekly/monthly leaderboard
- Non-competitive framing: "Top Seekers This Week" not "Winners"
- **Files:** New `backend/services/leaderboard_service.py`

---

## Phase 4: Deepening the Moat (Ongoing) — Things GitaGPT Can't Easily Copy

### 4.1 Multi-Scripture Expansion
- Add: Upanishads, Devi Mahatmya, Narada Bhakti Sutras, Vivekachudamani, Ashtavakra Gita
- Ingest via existing `scripts/ingest_all_data.py` pipeline
- More scripture = richer, more diverse guidance

### 4.2 Temple Network Integration
- Partner with temples for: live darshan links, prasad delivery, puja booking
- "Book a Satyanarayan Puja at [temple] for ₹501" — full e-commerce flow
- Location-based temple recommendations using user's GPS

### 4.3 Astrology / Kundli Integration
- User provides DOB/time/place → generate basic kundli
- Integrate with panchang for daily predictions
- "Based on your Vrishabha rashi and today's Rohini nakshatra, this is a good day for..."

### 4.4 Family Spiritual Dashboard
- Family plan: parents + children accounts linked
- Parents can see children's spiritual journey (opt-in)
- Joint family puja reminders, shared satsang

### 4.5 Offline Mode
- Cache recent conversations, daily shloka, meditation audio for offline access
- Critical for rural India with spotty connectivity

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Voice Input (STT) | 8/10 | Medium | **P0** |
| Regional Languages (10) | 8/10 | Low (Gemini native) | **P0** |
| Daily Sadhana System | 8/10 | Low | **P1** |
| Multiple Avatars | 7/10 | Medium | **P1** |
| Growth Tracker | 6/10 | Medium | **P2** |
| Guided Meditations | 6/10 | Medium | **P2** |
| Festival Reminders | 6/10 | Low | **P2** |
| Satsang Rooms | 7/10 | High | **P2** |
| Human Guru Sessions | 6/10 | Medium | **P2** |
| AI Avatar Video | 5/10 | High | **P3** |
| Peer Support | 5/10 | Medium | **P3** |
| Leaderboard | 4/10 | Low | **P3** |
| Temple Integration | 8/10 | High | **P3** |
| Astrology/Kundli | 7/10 | High | **P3** |

---

## Summary

**Already winning:** RAG depth, empathetic conversation, safety protocol, panchang, e-commerce, multi-scripture

**Build NOW (P0):** Voice input, regional languages

**Build next (P1):** Daily sadhana, multiple avatars

**Build later (P2-P3):** Community, meditations, guru sessions, temple integration

**Strategy:** GitaGPT is wide but shallow (10 avatars, but each is basic Q&A). 3ioNetra is deep but narrow. Go wide on multi-modal and engagement while keeping the depth advantage that GitaGPT can't easily replicate.
