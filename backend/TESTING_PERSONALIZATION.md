# Testing User Data Personalization

## Issue Identified

The user reported that the bot was saying "[User Name]" instead of the actual name. This happened because:

1. **Old sessions** created before the code changes don't have user data
2. User data was only populated on **new session creation**, not on existing sessions

## Fix Applied

**Changed behavior from:**
- ❌ Only populate user data when creating a NEW session

**To:**
- ✅ **ALWAYS refresh user data on EVERY conversation request**

This means even if you're using an old session ID, the user information will be loaded fresh from the authenticated user object on each message.

## Code Changes

### File: `main.py` (Line 553-593)

**Before:**
```python
if query.session_id:
    session = await session_manager.get_session(query.session_id)
else:
    session = await session_manager.create_session(...)
    # User data populated ONLY here for new sessions
    if user:
        session.memory.user_name = user.get('name', '')
        # ... etc
```

**After:**
```python
if query.session_id:
    session = await session_manager.get_session(query.session_id)
else:
    session = await session_manager.create_session(...)

# ALWAYS refresh user data (moved outside the else block)
if user:
    session.memory.user_id = user.get('id', '')
    session.memory.user_name = user.get('name', '')
    session.memory.user_email = user.get('email', '')
    session.memory.user_phone = user.get('phone', '')
    session.memory.user_dob = user.get('dob', '')
    session.memory.user_created_at = user.get('created_at', '')
    
    story = session.memory.story
    story.age_group = user.get('age_group')
    story.gender = user.get('gender')
    story.profession = user.get('profession')
```

### File: `llm/service.py` (Line 226-273)

Added debug logging to track what user data is being passed:
```python
if user_profile:
    logger.info(f"Building prompt with user_profile: {user_profile}")
    # ... build profile text ...
    logger.info(f"Generated profile section with {len(profile_parts)} fields")
else:
    logger.warning("No user_profile provided to prompt builder")
```

## How to Test

### Step 1: Start Fresh (Backend should be running)
The backend is already running on port 8080 with auto-reload enabled.

### Step 2: Login to Your Account
1. Go to the frontend (should be running on your local dev server)
2. Login with your credentials (e.g., ankitripathi1609@gmail.com)
3. Your user data should be loaded:
   - Name: Ankit Tripathi
   - Age: 23
   - Age Group: young_adult
   - Profession: professional
   - Gender: male
   - DOB: 2002-09-16
   - Phone: 9136742031

### Step 3: Start a Conversation
Send a message like:
```
"Hello, I'm feeling stressed about work"
```

### Step 4: Check the Response
The bot should now:
- ✅ Address you by name: "Ankit," or "Ankit Tripathi,"
- ✅ Reference your profession if relevant
- ✅ Use age-appropriate language for a 23-year-old young professional

### Step 5: Verify in Logs
Check the backend logs (terminal running uvicorn) for:
```
INFO: Session [session_id]: Refreshed user data (id=..., name=Ankit Tripathi, age_group=young_adult)
INFO: Building prompt with user_profile: {'name': 'Ankit Tripathi', 'age_group': 'young_adult', ...}
INFO: Generated profile section with 6 fields
```

### Step 6: Test with Existing Session
If you have an old session ID:
1. Continue the conversation (don't create a new session)
2. Send another message
3. The bot should STILL use your name correctly
4. This proves the fix works for existing sessions too

## Expected Behavior Examples

### ❌ Before Fix:
```
User: "What's my name?"
Bot: "Your name is [User Name]. Is there something..."
```

### ✅ After Fix:
```
User: "What's my name?"
Bot: "Your name is Ankit Tripathi. As a young professional..."
```

### ✅ Personalized Example:
```
User: "I'm stressed about work deadlines"
Bot: "Ankit, I understand. At 23, navigating your professional 
career can feel overwhelming at times. The pressure to prove 
yourself in the workplace is real..."
```

## Troubleshooting

### If the bot still doesn't use your name:

1. **Check Authentication**: Make sure you're logged in
   - Look for the JWT token in browser localStorage
   - Endpoint: `GET /api/auth/verify` should return your user data

2. **Check Backend Logs**: Look for:
   - `"Refreshed user data"` message with your name
   - `"Building prompt with user_profile"` with your data
   - Any warnings like `"No user_profile provided"`

3. **Clear Session**: Delete your current session and start fresh
   - This forces a new session creation
   - Endpoint: `DELETE /api/session/{session_id}`

4. **Check User Data in MongoDB**:
   ```python
   # Your data should be in the users collection
   {
     "id": "65d5c5d356f1baf54b83772b",
     "name": "Ankit Tripathi",
     "email": "ankitripathi1609@gmail.com",
     ...
   }
   ```

## Technical Details

### Data Flow on Every Request:

```
1. User sends message to /api/conversation
   ↓
2. JWT token validated → user object loaded
   ↓
3. Session retrieved (existing or new)
   ↓
4. **NEW**: User data refreshed in session.memory
   ↓
5. Response composer builds user_profile dict
   ↓
6. LLM service receives user_profile
   ↓
7. Prompt includes "WHO YOU ARE SPEAKING TO" section
   ↓
8. Gemini generates personalized response
```

### Files Involved:
- ✅ `main.py` - Always refresh user data
- ✅ `models/memory_context.py` - Store user_dob
- ✅ `services/response_composer.py` - Build complete profile
- ✅ `llm/service.py` - Display profile in prompt + logging

## Next Steps

After confirming this works:
1. Remove or reduce debug logging if too verbose
2. Consider caching user profile to avoid repeated dict building
3. Add user preferences (favorite scriptures, language, etc.)
4. Track personalization effectiveness in analytics

## Quick Verification Command

Check your current user data:
```bash
curl -X GET "http://localhost:8080/api/auth/verify" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

This should return your complete profile including name, profession, etc.
