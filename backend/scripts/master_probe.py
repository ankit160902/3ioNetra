"""
master_probe.py — 3ioNetra Master Logic Validation Suite (100+ Scenarios)
Tests: intent, life_domain, needs_direct_answer, recommend_products
"""
import asyncio, os, sys, json, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.intent_agent import get_intent_agent

# ---------------------------------------------------------------------
# SCENARIO FORMAT
# {id, name, message, domain, direct, rec, intents[]}
# domain    : expected life_domain (None = any)
# direct    : expected needs_direct_answer (None = any)
# rec       : expected recommend_products (None = any)
# intents   : list of acceptable intent strings
# ---------------------------------------------------------------------
SCENARIOS = [

    # ═══════════════════════════════════════════════════════════════
    # A. CAREER & WORKPLACE (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "A01", "name": "The Burnout",       "message": "I'm a 35-yr manager. Good salary but feel hollow. Need peace and something for daily grounding.", "domain": ["career","spiritual"], "direct": None, "rec": True,  "intents": ["SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},
    {"id": "A02", "name": "Job Loss Fear",     "message": "Got laid off today. Family to support. Feel paralyzed by fear.", "domain": ["career","family"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "A03", "name": "Ethical Dilemma",   "message": "Boss asked me to overlook a financial issue. Need this job but conscience hurts. What does Dharma say?", "domain": ["career"], "direct": None, "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "A04", "name": "Career Change Fear","message": "Thinking of leaving corporate for creative work. Terrified of failing.", "domain": ["career"], "direct": False, "rec": False, "intents": ["SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},
    {"id": "A05", "name": "Office Desk Bundle","message": "My desk job gives me headaches. Any oils or small idols for my workspace to keep me calm?", "domain": ["health","career"], "direct": False, "rec": True,  "intents": ["PRODUCT_SEARCH","SEEKING_GUIDANCE"]},
    {"id": "A06", "name": "Modern Monk",       "message": "How do I balance corporate stress with spiritual values without seeming weird to colleagues?", "domain": ["career"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE"]},
    {"id": "A07", "name": "Dharmic Finance",   "message": "How can I align my investments and wealth with Dharmic values?", "domain": ["career","finance"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "A08", "name": "Toxic First Job",   "message": "Just started my first job and the culture is toxic. How do I handle this without quitting?", "domain": ["career"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE"]},
    {"id": "A09", "name": "Sleep vs Money",    "message": "I'm 50, financially stable, but I can't sleep at night. Mind races constantly. Need peace toolkit.", "domain": ["health"], "direct": False, "rec": True,  "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "A10", "name": "Promotion Prayer",  "message": "I got a promotion! I want to offer thanks. What ritual or puja item should I use?", "domain": ["career","spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},

    # ═══════════════════════════════════════════════════════════════
    # B. FAMILY & PARENTING (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "B01", "name": "Spouse Grief",      "message": "Lost my husband of 40 years last month. House is unbearably quiet. Is his soul at peace?", "domain": ["family","spiritual"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "B02", "name": "Parenting Anger",   "message": "Lost my temper with my child again. Do you have any tools to help me stay calm as a parent?", "domain": ["family"], "direct": False, "rec": True,  "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "B03", "name": "Parent's Death",    "message": "My mother passed away. What rituals or items can I use to honor her memory?", "domain": ["family","spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "B04", "name": "Elder Care Fatigue","message": "I'm 52, caring for aging parents and I'm exhausted. I need strength to continue.", "domain": ["family","health"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "B05", "name": "Sibling Jealousy",  "message": "I'm 21 and feel intense jealousy towards my brother. It's eating me. What does Dharma say about this?", "domain": ["family"], "direct": None, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "B06", "name": "Teaching Values",   "message": "I want to teach my 10-year-old son Hindu values in a fun, modern way. How do I start?", "domain": ["family","spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "B07", "name": "Child Study Puja",  "message": "My daughter has important board exams. What puja can I do to bless her with focus and success?", "domain": ["family","spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "B08", "name": "Newborn Ritual",    "message": "We just had our first baby. What are the traditional spiritual rituals to do in the first month?", "domain": ["family","spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "B09", "name": "Family Distance",   "message": "My parents are in another city. I miss them. How can I stay spiritually connected to them daily?", "domain": ["family","relationships"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE"]},
    {"id": "B10", "name": "Fighting Parents",  "message": "My parents fight constantly. As a child, I am powerless but it's affecting my mental peace.", "domain": ["family"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # C. RELATIONSHIPS (8 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "C01", "name": "Spousal Disconnect","message": "I feel disconnected from my wife. We're growing apart. How do I find peace without separation?", "domain": ["relationships"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "C02", "name": "Breakup Healing",   "message": "I'm 27, my heart is broken. I've lost my sense of self-worth. Help me find inner strength.", "domain": ["relationships"], "direct": False, "rec": None,  "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "C03", "name": "City Loneliness",   "message": "Moved to a new city for work. Feel invisible and disconnected from my culture and people.", "domain": ["relationships"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "C04", "name": "Marriage Prep",     "message": "Getting married next month. What auspicious guidance or items should I have for the new home?", "domain": ["relationships","spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "C05", "name": "Long Distance Bond","message": "My partner is far away. How can we maintain a spiritual and emotional bond across the distance?", "domain": ["relationships"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE"]},
    {"id": "C06", "name": "Toxic Friendship",  "message": "My best friend has become manipulative and energy-draining. What should I do spiritually?", "domain": ["relationships"], "direct": False, "rec": False, "intents": ["SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},
    {"id": "C07", "name": "Forgiveness Path",  "message": "I was deeply hurt by someone I trusted. I struggle to forgive. What does Dharma say about forgiving?", "domain": ["relationships","spiritual"], "direct": False, "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "C08", "name": "Grief Breakup Gift","message": "Going through a breakup. What crystals, incense or spiritual items can help me heal?", "domain": ["relationships"], "direct": False, "rec": True,  "intents": ["PRODUCT_SEARCH","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # D. SPIRITUAL PRACTICE (12 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "D01", "name": "Beginner Start",    "message": "I know nothing about spirituality but want to start a journey. What are the first steps and items I need?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D02", "name": "Shiva Pull",        "message": "I feel a strong pull to Lord Shiva. How do I start worshipping him and what items do I need for my altar?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D03", "name": "Satyanarayan Puja", "message": "What is the importance of Satyanarayan Pooja and what items are needed to perform it?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D04", "name": "Mala for Chanting", "message": "I want to start chanting 'Om Namah Shivaya'. Which mala is best and where can I find one?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","ASKING_INFO"]},
    {"id": "D05", "name": "Diwali Items",      "message": "I'm missing some items for my Ganesh Chaturthi pooja. Can you help me find them?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","SEEKING_GUIDANCE"]},
    {"id": "D06", "name": "Gita Deep Dive",    "message": "I want to understand the profound meaning of Karma as explained in the Bhagavad Gita.", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D07", "name": "Beyond Asana Yoga", "message": "I want to move beyond the physical aspects of yoga into the spiritual dimension. How do I start?", "domain": ["spiritual","health"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "D08", "name": "Kashi Pilgrimage",  "message": "I'm planning a trip to Kashi (Varanasi). What should I spiritually prepare for?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D09", "name": "Altar Setup",       "message": "I want to set up a small puja corner at home. What items do I need and how should I arrange them?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","PRODUCT_SEARCH","SEEKING_GUIDANCE"]},
    {"id": "D10", "name": "Vishnu Puja",       "message": "I want to do Vishnu Puja at home every Thursday. What is the correct procedure and what items are required?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "D11", "name": "Rudraksha Query",   "message": "Which Rudraksha is best for reducing anxiety and stress? Where can I buy a genuine one?", "domain": ["spiritual","health"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","ASKING_INFO"]},
    {"id": "D12", "name": "Mantra for Students","message": "Which mantra should a student chant daily before studying for focus and memory?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # E. EMOTIONAL & EXISTENTIAL (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "E01", "name": "Chest Heaviness",   "message": "I have this constant heaviness in my chest. I need peace and something to calm my environment.", "domain": ["health"], "direct": False, "rec": True,  "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "E02", "name": "World Anger",       "message": "I am so angry at how corrupt the world is. Making me cynical about everything.", "domain": ["spiritual"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "E03", "name": "Gratitude Reset",   "message": "I've become ungrateful and forgotten life's blessings. How do I reset my mindset?", "domain": ["spiritual"], "direct": True,  "rec": None,  "intents": ["SEEKING_GUIDANCE"]},
    {"id": "E04", "name": "Who Am I?",         "message": "I'm 18 and I feel like I have no identity. What do the scriptures say about the true self?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "E05", "name": "Fear of Death",     "message": "I am 80. I think about death every day. Give me some solace from the scriptures.", "domain": ["spiritual"], "direct": False, "rec": False, "intents": ["SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},
    {"id": "E06", "name": "Creative Block",    "message": "I'm a writer and I've been blocked for months. Can I seek wisdom and blessings from Goddess Saraswati?", "domain": ["career","spiritual"], "direct": None, "rec": None,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "E07", "name": "Sunday Self-care",  "message": "Just checking in Mitra. How should I spend my Sunday in a Dharmic way?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE"]},
    {"id": "E08", "name": "Depression Spiral", "message": "I feel completely hopeless. Nothing matters to me anymore. I'm sinking into darkness.", "domain": ["health"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "E09", "name": "Panic Attacks",     "message": "I'm having panic attacks before important events. What yogic or spiritual technique can help?", "domain": ["health","spiritual"], "direct": True,  "rec": None,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "E10", "name": "Anger Management",  "message": "I lose my temper very fast. My anger is ruining relationships. What can spirituality offer me?", "domain": ["spiritual","relationships"], "direct": True,  "rec": None,  "intents": ["SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # F. HEALTH, DIET & AYURVEDA (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "F01", "name": "Sattvic Diet Day",  "message": "I want to switch to a Sattvic diet. Give me a complete eating routine for the whole day.", "domain": ["health"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F02", "name": "Dharmic Weight",    "message": "Trying to lose weight while staying spiritually aligned. Suggest a Dharmic meal plan for today.", "domain": ["health"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F03", "name": "Ekadashi Fasting",  "message": "I want to observe Ekadashi fast. How should I plan my meals the day before, during, and after?", "domain": ["health","spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "F04", "name": "Ayurveda Detox",    "message": "I feel heavy and toxic. Give me a one-day Ayurvedic detox plan with herbs or products.", "domain": ["health"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F05", "name": "Cancer Diet",       "message": "My father is undergoing cancer treatment. What Sattvic or Ayurvedic foods can support his recovery?", "domain": ["health","family"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "F06", "name": "Morning Energy",    "message": "I feel lethargic every morning. Give me a 20-minute yoga routine to stay active throughout the day.", "domain": ["health"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F07", "name": "Student Yoga",      "message": "I'm a student with poor concentration. Plan me a daily yoga and pranayama routine to improve focus.", "domain": ["health","spiritual"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F08", "name": "Bedtime Yoga",      "message": "I can't sleep due to work stress. Give me a bedtime yoga routine to relax my mind and body.", "domain": ["health"], "direct": True,  "rec": None,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "F09", "name": "Desk Stretches",    "message": "I sit at a desk for 8 hours. Give me stretches I can do at my chair every two hours.", "domain": ["health"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "F10", "name": "Holistic Sunday",   "message": "I want to dedicate Sunday to self-care. Plan a full day with Yoga, Sattvic Diet, and Meditation.", "domain": ["health","spiritual"], "direct": True,  "rec": False, "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},

    # ═══════════════════════════════════════════════════════════════
    # G. PUJA & RITUAL PLANNING (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "G01", "name": "Daily Ganesha",     "message": "Plan me a step-by-step 15-minute morning puja for Lord Ganesha to do daily.", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "G02", "name": "Business Puja",     "message": "Starting a new business. Which puja should I do and how can I perform it at home, step by step?", "domain": ["career","spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G03", "name": "Shiva Abhishekam",  "message": "I want to do a Shiva Abhishekam at home today. What items do I need and what are the exact steps?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","PRODUCT_SEARCH"]},
    {"id": "G04", "name": "Evening Aarti",     "message": "Help me plan a peaceful evening aarti routine for my family. What mantras should we chant?", "domain": ["spiritual","family"], "direct": True,  "rec": True,  "intents": ["SEEKING_GUIDANCE","ASKING_INFO"]},
    {"id": "G05", "name": "Altar Reset",       "message": "I've moved my puja altar to a new location. How do I dharmically re-energize and consecrate the space?", "domain": ["spiritual"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G06", "name": "Navratri Prep",     "message": "Navratri is coming. What are the nine days' rituals and what items do I need for each day?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G07", "name": "New Home Puja",     "message": "Moving into a new home next week. What is the Vastu Puja or Griha Pravesh ritual and what items are needed?", "domain": ["spiritual","family"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G08", "name": "Saraswati Puja",    "message": "I want to do Saraswati Puja for my art studio. What is the procedure and what do I need?", "domain": ["spiritual","career"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G09", "name": "Shanti Havan",      "message": "I want to do a small Shanti Havan at home for peace. What items are needed and who should officiate?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "G10", "name": "Daily Tulsi Puja",  "message": "How should I perform Tulsi Puja every evening? What are the steps and offerings?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # H. ASTROLOGY & VEDIC WISDOM (8 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "H01", "name": "Kundali Query",     "message": "What can my Kundali tell me about my career and marriage prospects?", "domain": ["spiritual","career"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "H02", "name": "Shani Dasha",       "message": "I am going through Shani Mahadasha and things have been tough. What remedies can help?", "domain": ["spiritual"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "H03", "name": "Panchang Today",    "message": "What is today's Panchang? Is it an auspicious day to start a new project?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_PANCHANG","ASKING_INFO"]},
    {"id": "H04", "name": "Lucky Gemstone",    "message": "Which gemstone is lucky for me? I'm a Scorpio with Mangal in the 7th house.", "domain": ["spiritual"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE","PRODUCT_SEARCH"]},
    {"id": "H05", "name": "Muhurta for Travel","message": "I'm planning a long journey. Can you suggest an auspicious muhurta for departing?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","ASKING_PANCHANG","SEEKING_GUIDANCE"]},
    {"id": "H06", "name": "Rahu Remedies",     "message": "Experiencing Rahu Kaal effects in my life. What are the remedies and items I should get?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "H07", "name": "Astro Career Boost","message": "Astrologically, how can I strengthen Jupiter in my chart to boost my career?", "domain": ["spiritual","career"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "H08", "name": "Sade Sati Impact",  "message": "My Sade Sati started last year. My life feels stuck. What should I do spiritually?", "domain": ["spiritual"], "direct": True,  "rec": None,  "intents": ["ASKING_INFO","SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},

    # ═══════════════════════════════════════════════════════════════
    # I. CRISIS & URGENT SUPPORT (7 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "I01", "name": "Suicidal Thoughts", "message": "I don't want to live anymore. Everything feels pointless. I'm exhausted.", "domain": ["health"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION"]},
    {"id": "I02", "name": "Panic Attack Now",  "message": "I'm having a panic attack right now. I can't breathe properly. Help me.", "domain": ["health"], "direct": True,  "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "I03", "name": "Financial Ruin",    "message": "I've lost everything in the stock market crash. I'm bankrupt. I don't know what to do next.", "domain": ["finance","career"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "I04", "name": "Sudden Death News", "message": "My brother just died in an accident. I don't know how to process this.", "domain": ["family"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION"]},
    {"id": "I05", "name": "Abuse Survivor",    "message": "I escaped an abusive relationship. I'm physically safe but spiritually and emotionally shattered.", "domain": ["relationships","health"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "I06", "name": "Medical Diagnosis", "message": "Just diagnosed with a serious illness. I'm terrified. How do I hold onto faith?", "domain": ["health"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},
    {"id": "I07", "name": "Divorce Crisis",    "message": "My marriage is ending. I feel like I've failed completely as a person.", "domain": ["relationships"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # J. PRODUCT SEARCHES (5 scenarios — must be PRODUCT_SEARCH)
    # ═══════════════════════════════════════════════════════════════
    {"id": "J01", "name": "Buy Rudraksha",     "message": "Where can I buy a genuine certified 5 Mukhi Rudraksha mala from your store?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH"]},
    {"id": "J02", "name": "Buy Gomati Chakra", "message": "I need Gomati Chakra for wealth and prosperity. Where can I get an authentic one?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","ASKING_INFO"]},
    {"id": "J03", "name": "Buy Dhoop Sticks",  "message": "I want to buy some high-quality natural dhoop sticks or incense for my daily puja.", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH"]},
    {"id": "J04", "name": "Vastu Yantra",      "message": "Which Vastu Yantra should I place for harmony at home and where can I get one?", "domain": ["spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","ASKING_INFO"]},
    {"id": "J05", "name": "Buy Yoga Mat",      "message": "I need an eco-friendly yoga mat and meditation cushion. Do you have any recommendations?", "domain": ["health","spiritual"], "direct": True,  "rec": True,  "intents": ["PRODUCT_SEARCH","SEEKING_GUIDANCE"]},

    # ═══════════════════════════════════════════════════════════════
    # K. CONVERSATIONAL & EDGE CASES (10 scenarios)
    # ═══════════════════════════════════════════════════════════════
    {"id": "K01", "name": "Simple Greeting",   "message": "Namaste Mitra!", "domain": None, "direct": False, "rec": False, "intents": ["GREETING"]},
    {"id": "K02", "name": "Ending Session",    "message": "Thank you for your guidance today. I feel much better. Goodbye.", "domain": None, "direct": False, "rec": False, "intents": ["CLOSURE"]},
    {"id": "K03", "name": "Ambiguous Mood",    "message": "I don't even know how I feel today. Just... blank.", "domain": ["health","spiritual"], "direct": False, "rec": False, "intents": ["EXPRESSING_EMOTION","OTHER"]},
    {"id": "K04", "name": "Philosophical Q",   "message": "Is the concept of God in Hinduism Personal or Impersonal? What is Brahman?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO"]},
    {"id": "K05", "name": "Reincarnation Q",   "message": "How does Karma determine the next life? What scriptures explain this best?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "K06", "name": "Weather & Fast",    "message": "It's a Monday. Should I fast for Shiva today? What are the rules?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "K07", "name": "Corporate Ethics",  "message": "My company is pressuring me to cut quality corners. Dharmic response?", "domain": ["career"], "direct": False, "rec": False, "intents": ["SEEKING_GUIDANCE","EXPRESSING_EMOTION"]},
    {"id": "K08", "name": "Dream Meaning",     "message": "I had a dream about Lord Vishnu handing me a lotus. What does this mean?", "domain": ["spiritual"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "K09", "name": "Vegan Hindu",       "message": "Can I follow a strict vegan lifestyle and still observe all Hindu festivals and rituals properly?", "domain": ["spiritual","health"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
    {"id": "K10", "name": "Astrology Skeptic", "message": "I don't really believe in astrology. But my family is pressuring me. What's the Dharmic view?", "domain": ["spiritual","family"], "direct": True,  "rec": False, "intents": ["ASKING_INFO","SEEKING_GUIDANCE"]},
]

# ─────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────
async def run():
    agent = get_intent_agent()
    categories = {}
    passed = failed = 0

    print(f"\n{'═'*110}")
    print(f"  3ioNetra Master Logic Probe  —  {len(SCENARIOS)} Scenarios")
    print(f"{'═'*110}")
    print(f"{'ID':<5} | {'SCENARIO':<25} | {'DOMAIN':<14} | {'INTENT':<18} | {'DIRECT':<7} | {'PROD':<6} | STATUS")
    print(f"{'─'*110}")

    for s in SCENARIOS:
        await asyncio.sleep(1.2)
        cat = s["id"][0]
        categories.setdefault(cat, {"passed": 0, "total": 0})
        categories[cat]["total"] += 1

        try:
            r = await agent.analyze_intent(s["message"])
            got_domain  = r.get("life_domain","").lower()
            got_intent  = r.get("intent","")
            got_direct  = r.get("needs_direct_answer")
            got_rec     = r.get("recommend_products")

            domain_ok  = (s["domain"] is None) or (got_domain in [d.lower() for d in s["domain"]])
            intent_ok  = got_intent in s["intents"]
            direct_ok  = (s["direct"] is None) or (got_direct == s["direct"])
            rec_ok     = (s["rec"]    is None) or (got_rec    == s["rec"])

            ok = domain_ok and intent_ok and direct_ok and rec_ok
            status = "✅" if ok else "❌"
            if ok:
                passed += 1
                categories[cat]["passed"] += 1
            else:
                failed += 1

            print(f"{s['id']:<5} | {s['name']:<25} | {got_domain:<14} | {got_intent:<18} | {str(got_direct):<7} | {str(got_rec):<6} | {status}")
            if not ok:
                if not domain_ok:  print(f"       ↳ Domain : got '{got_domain}', expected one of {s['domain']}")
                if not intent_ok:  print(f"       ↳ Intent : got '{got_intent}', expected one of {s['intents']}")
                if not direct_ok:  print(f"       ↳ Direct : got {got_direct}, expected {s['direct']}")
                if not rec_ok:     print(f"       ↳ Rec    : got {got_rec}, expected {s['rec']}")

        except Exception as e:
            print(f"{s['id']:<5} | {s['name']:<25} | ERROR: {str(e)[:55]}")
            failed += 1
            if "429" in str(e):
                await asyncio.sleep(8)

    total = passed + failed
    pct   = int(100 * passed / total) if total else 0

    print(f"\n{'═'*110}")
    print(f"  CATEGORY BREAKDOWN:")
    cats = {"A":"Career","B":"Family","C":"Relationships","D":"Spiritual","E":"Emotional",
            "F":"Health/Diet","G":"Puja","H":"Astrology","I":"Crisis","J":"Products","K":"Edge Cases"}
    for k, v in sorted(categories.items()):
        bar = "█" * v["passed"] + "░" * (v["total"]-v["passed"])
        print(f"  {k} ({cats.get(k,'?'):<14}): {v['passed']:>2}/{v['total']} [{bar}]")

    print(f"\n  ✅ TOTAL: {passed}/{total}  ({pct}% Pass Rate)")
    print(f"{'═'*110}\n")

if __name__ == "__main__":
    asyncio.run(run())
