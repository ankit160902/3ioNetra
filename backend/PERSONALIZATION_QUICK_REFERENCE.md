# Quick Reference: User Data in Prompts

## For Developers

### How User Data Flows to Prompts

1. **User Registration (main.py:820-828)**
```python
result = auth_service.register_user(
    name=request.name,
    email=request.email,
    password=request.password,
    phone=request.phone,
    gender=request.gender,
    dob=request.dob,
    profession=request.profession
)
```

2. **Data Storage (auth_service.py:128-143)**
- User document created in MongoDB
- Includes: id, name, email, phone, gender, dob, age, age_group, profession
- Password is hashed and salted

3. **Session Pre-population (main.py:553-590)**
- When user starts conversation, their data is loaded
- Session memory populated with user profile
- Available throughout the conversation

4. **Profile Building (response_composer.py:76-113)**
```python
profile = {
    'name': memory.user_name,
    'email': memory.user_email,
    'phone': memory.user_phone,
    'dob': memory.user_dob,
    'age_group': story.age_group,
    'gender': story.gender,
    'profession': story.profession,
    'primary_concern': story.primary_concern,
    'emotional_state': story.emotional_state,
    'life_area': story.life_area
}
```

5. **Prompt Generation (llm/service.py:223-265)**
```python
profile_text = """
======================================================================
WHO YOU ARE SPEAKING TO:
======================================================================
   • Their name is: Ankit Tripathi
   • Age group: young_adult
   • Date of birth: 2002-09-16
   • Profession: professional
   • Gender: male
   • Phone: 9136742031
======================================================================
"""
```

## What Gets Passed to the LLM

### Always Included (if available):
- ✅ Name
- ✅ Age group (teen, young_adult, middle_aged, senior)
- ✅ Date of birth
- ✅ Profession
- ✅ Gender
- ✅ Phone number

### Conversation Context (if detected):
- ✅ Primary concern
- ✅ Emotional state
- ✅ Life area
- ✅ Conversation history

## Example Prompt Structure

```
======================================================================
WHO YOU ARE SPEAKING TO:
======================================================================
   • Their name is: [USER_NAME]
   • Age group: [AGE_GROUP]
   • Date of birth: [DOB]
   • Profession: [PROFESSION]
   • Gender: [GENDER]
   • Phone: [PHONE]
   • What they've shared: [PRIMARY_CONCERN]
   • Current emotion: [EMOTIONAL_STATE]
   • Life area: [LIFE_AREA]
======================================================================

WHAT YOU KNOW SO FAR (FACTS):
======================================================================
• User is dealing with [primary_concern]
• They are currently feeling [emotional_state]
• This situation relates to their [life_area]
======================================================================

CONVERSATION FLOW:
======================================================================
[Last 12 messages of conversation history]
======================================================================

User's CURRENT message:
[User's latest message]

YOUR INSTRUCTIONS FOR THIS PHASE (listening/guidance):
======================================================================
[Phase-specific instructions]
======================================================================

VERSES AVAILABLE (Use ONLY if they naturally fit):
======================================================================
[Retrieved scripture verses with context]
======================================================================
```

## System Instruction Enhancement

The LLM is explicitly instructed to:
- **Use their name** when appropriate
- **Contextualize to their life** by weaving profession, age, etc. into responses
- **Make it deeply personal** by considering their life stage and circumstances

## Testing Checklist

- [ ] Register user with complete profile
- [ ] Login with credentials
- [ ] Start conversation
- [ ] Check if bot uses user's name
- [ ] Verify age-appropriate language
- [ ] Confirm profession-relevant examples
- [ ] Check gender-appropriate language
- [ ] Verify context persistence across messages

## Privacy Considerations

- Phone and email are in the prompt but typically NOT spoken in responses
- Only used for internal context
- No PII logged externally
- JWT tokens expire after 30 days
- Session memory cleared on TTL expiration

## Files Modified

1. `models/memory_context.py` - Added user_dob field
2. `main.py` - Pre-populate user_dob in session
3. `services/response_composer.py` - Include all user fields in profile
4. `llm/service.py` - Display user data in prompt + enhanced instructions

## Additional Notes

- Age is calculated automatically from DOB
- Age group is determined by age brackets
- User data persists in MongoDB
- Session data is temporary (in-memory with TTL)
- Profile is rebuilt for each LLM call
