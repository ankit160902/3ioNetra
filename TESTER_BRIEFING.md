# 3ioNetra AI Spiritual Companion — Tester Briefing

## What is this product?

This is an AI spiritual companion rooted in Sanatan Dharma. The chatbot persona is called AI Spiritual Companion. Users talk to AI Spiritual Companion about life problems — stress, relationships, career confusion, grief, health anxiety, etc. — and AI Spiritual Companion responds with empathetic listening first, then gradually offers wisdom from Hindu scriptures (Bhagavad Gita, Upanishads, etc.), mantras, spiritual practices, and relevant product recommendations from the 3ioNetra store.

**Live URLs:**
- Link: https://3iomitra.vercel.app

---

## User Flow (End to End)

### 1. Registration (3-step form)
- **Step 1 — Basic Info:** Name, Email, Password (min 8 chars, must contain letter + number), Confirm Password
- **Step 2 — Profile Details:** Phone (min 10 digits), Gender, Date of Birth, Profession
- **Step 3 — Spiritual Profile (all optional):** Preferred Deity, Rashi, Gotra, Nakshatra, Favorite Temples, Past Purchases

### 2. Login
- Email + Password → receives auth token (valid 30 days)
- Token stored in browser localStorage


### 3. Start Conversation
- User lands on the chat screen after login
- A new session is auto-created with a welcome message from AI Spiritual Companion
- User types a message in the chat input

### 4. Conversation Phases (automatic, shown via phase indicator)
- **Listening** → AI Spiritual Companion greets, asks open-ended questions, builds rapport
- **Guidance** → Once AI Spiritual Companion understands the user's concern (after ~2-3 turns), it shares scripture verses, mantras, practices
- **Closure** → Wrap-up with a blessing

### 5. During Conversation
- AI Spiritual Companion may show **product recommendation cards** (e.g., rudraksha, incense) below its response — these are clickable and link to the 3ioNetra store
- AI Spiritual Companion may include a **Sanskrit verse** in `[VERSE]...[/VERSE]` tags
- User can use the **TTS button** to hear AI Spiritual Companion's response read aloud
- User can give **thumbs up/down feedback** on responses

### 6. Conversation History
- Logged-in users can view past conversations from the sidebar
- Conversations are auto-saved and can be resumed or deleted

### 7. Logout
- Clears token and returns to login screen

---

## Testing Objectives

### Functional Testing
1. **Registration flow** — Validate all 3 steps, field validations (email format, password rules, phone length), error messages
2. **Login/Logout** — Correct credentials work, wrong credentials show error, token persists across refresh, logout clears session
3. **Chat conversation** — Messages send and receive, streaming responses render correctly, no UI freezes
4. **Phase transitions** — AI Spiritual Companion starts in Listening, transitions to Guidance after sufficient context, eventually reaches Closure
5. **Scripture/Verse display** — Verses render properly with special formatting (not as raw tags)
6. **Product recommendations** — Cards appear contextually, images load, "buy" links open the store correctly
7. **Conversation history** — Past conversations load, display correctly, can be deleted
8. **Session management** — New session creation, session persistence across page refresh, session cleanup

### Response Quality Testing
1. **Empathy first** — AI Spiritual Companion should NOT jump to advice immediately; it should listen and acknowledge emotions first
2. **No hollow phrases** — Should never say "I hear you", "I understand", "everything happens for a reason"
3. **No markdown in responses** — Responses must be flowing sentences, no bullet points, no headers, no numbered lists
4. **Response length** — Should be 2-4 sentences (30-100 words), WhatsApp-style, not long essays
5. **Pivot on rejection** — If user rejects a suggestion, AI Spiritual Companion should offer an alternative, not just empathize
6. **Product mentions** — AI Spiritual Companion must NEVER mention products, shopping links, or "my3ionetra.com" in its text response (products appear as separate cards only)
7. **Safety/Crisis handling** — If user expresses suicidal thoughts or self-harm, AI Spiritual Companion must respond with compassion + helpline numbers (iCall, Vandrevala Foundation, NIMHANS), never spiritual-reframe active danger

### Language & Persona
1. AI Spiritual Companion should feel like a warm spiritual friend, not a therapist or generic chatbot
2. Hindi/Sanskrit terms should be contextually appropriate
3. Tone should be warm, not preachy or robotic

### Edge Cases
1. Empty messages / very long messages (max 2000 chars)
2. Rapid message sending (before previous response completes)
3. Session timeout behavior (sessions expire after 60 min of inactivity)
4. Network interruption mid-response (streaming SSE)
5. Multiple tabs / duplicate sessions
6. Special characters and emojis in user input

### Panchang Feature
- `/api/panchang/today` — Verify today's tithi, nakshatra, and special day info is accurate
- Ask AI Spiritual Companion about "aaj ka panchang" or "today's panchang" and verify it responds with correct data

---

## Key Test Accounts
> Ask the dev team for test credentials, or register a new account on the platform.

## Reporting
Flag issues with: **Page/Screen → Steps to Reproduce → Expected vs Actual → Screenshot/Recording**
