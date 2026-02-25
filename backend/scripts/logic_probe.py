import asyncio
import os
import sys
import json
from typing import List, Dict, Any

# Add backend directory to sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.intent_agent import get_intent_agent
from services.companion_engine import get_companion_engine
from models.session import ConversationPhase

scenarios = [
    # 💼 Career, Purpose & Finance
    {"id": 1, "name": "The Burnout", "message": "I'm a 35-year-old manager, and even though I have a good salary, I feel completely hollow. I need some mental peace and maybe something to help me stay grounded daily.", "expected_domain": "career", "should_recommend": True},
    {"id": 2, "name": "Job Loss Anxiety", "message": "I just got laid off today. I'm 45, I have a family to support, and I'm terrified of what everyone will think. I feel paralyzed.", "expected_domain": "family", "should_recommend": False},
    {"id": 3, "name": "Ethical Dilemma", "message": "My boss asked me to overlook a small financial irregularity today. I'm 28 and really need this job, but it feels so wrong. What does Dharma say?", "expected_domain": "career", "should_recommend": False},
    {"id": 4, "name": "The Career Pivot", "message": "I'm 30, thinking of leaving my stable corporate job to pursue a creative passion, but the fear of 'empty hands' is stopping me.", "expected_domain": "career", "should_recommend": False},
    {"id": 5, "name": "Office Stress", "message": "My desk job gives me constant headaches. Do you have anything natural like oils or a small idol for my workspace to keep me calm?", "expected_domain": "health", "should_recommend": True},
    {"id": 6, "name": "The Modern Monk", "message": "How do I balance a high-pressure corporate life with my spiritual values without appearing 'weird' to my peers?", "expected_domain": "career", "should_recommend": False},
    {"id": 7, "name": "Ethical Investing", "message": "How can I align my wealth and investments with Dharmic values?", "expected_domain": "career", "should_recommend": False},
    {"id": 8, "name": "First Job Anxiety", "message": "Just started my first job and the culture is so toxic. How do I handle this without quitting?", "expected_domain": "career", "should_recommend": False},
    {"id": 9, "name": "Stability vs Peace", "message": "I'm 50, I have financial stability but I can't sleep at night. My mind won't stop racing.", "expected_domain": "health", "should_recommend": True},

    # ❤️ Relationships, Family & Soul
    {"id": 10, "name": "Recent Grief (Spouse)", "message": "I lost my husband of 40 years last month. The house is so quiet now, it feels unbearable. I just want to know if his soul is at peace.", "expected_domain": "family", "should_recommend": True},
    {"id": 11, "name": "Spousal Conflict", "message": "I feel disconnected from my wife. We are growing in different directions. How do I find peace without separation?", "expected_domain": "relationships", "should_recommend": False},
    {"id": 12, "name": "Parenting Crisis", "message": "I lost my temper with my child today and I feel like a failure. How do I rebuild my patience? Do you have any tools to help me stay calm?", "expected_domain": "family", "should_recommend": True},
    {"id": 13, "name": "Loneliness in City", "message": "I moved to this city for work and I feel so invisible and disconnected from my culture.", "expected_domain": "relationships", "should_recommend": False},
    {"id": 14, "name": "Grief (Parent)", "message": "My mother passed away. What rituals or items can I use to honor her memory and find some peace?", "expected_domain": "family", "should_recommend": True},
    {"id": 15, "name": "Breakup Recovery", "message": "I'm 27 and my heart is broken. I feel like I've lost my worth. Help me find inner strength.", "expected_domain": "relationships", "should_recommend": True},
    {"id": 16, "name": "Caring for Elderly", "message": "I'm 52, caring for my aging parents and I'm exhausted. I need strength to keep going.", "expected_domain": "family", "should_recommend": False},
    {"id": 17, "name": "Marriage Prep", "message": "Getting married next month. Any auspicious guidance or items I should have for our new home?", "expected_domain": "relationships", "should_recommend": True},
    {"id": 18, "name": "Sibling Rivalry", "message": "I'm 21 and I feel so much jealousy towards my brother. It's eating me up.", "expected_domain": "family", "should_recommend": False},
    {"id": 19, "name": "Distance Relationship", "message": "My partner is far away. How do we maintain a spiritual bond despite the distance?", "expected_domain": "relationships", "should_recommend": False},

    # 🧘 Spiritual Growth & Practice
    {"id": 20, "name": "Absolute Beginner", "message": "I want to start a spiritual journey but I have no idea where to begin. What's the first step and what items do I need?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 21, "name": "Deity Pull (Shiva)", "message": "I feel a strong pull to Lord Shiva. How do I start worshipping him and what do I need for my altar?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 22, "name": "Ritual Inquiry", "message": "What is the importance of Satyanarayan Pooja and what items are needed for it?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 23, "name": "Meditation Setup", "message": "I need a proper asana and beads for my daily meditation. What do you recommend?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 24, "name": "Festival Preparedness", "message": "I'm missing some items for my Ganesh Chaturthi pooja. Can you help me find them?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 25, "name": "Intellectual Seeker", "message": "I want to understand the deep meaning of Karma as explained in the Gita.", "expected_domain": "spiritual", "should_recommend": False},
    {"id": 26, "name": "Yoga Journey", "message": "I want to move beyond physical yoga to the spiritual side. How do I start?", "expected_domain": "spiritual", "should_recommend": False},
    {"id": 27, "name": "Pilgrimage Planning", "message": "I'm 55 and planning a trip to Kashi. What should I prepare for?", "expected_domain": "spiritual", "should_recommend": False},

    # 🌓 Emotional & Existential
    {"id": 28, "name": "Vague Anxiety", "message": "I have this constant heaviness in my chest. I need peace and something to keep my environment calm.", "expected_domain": "health", "should_recommend": True},
    {"id": 29, "name": "Anger with World", "message": "I'm so angry at how the world is today. It's making me cynical.", "expected_domain": "spiritual", "should_recommend": False},
    {"id": 30, "name": "Gratitude Practice", "message": "I've forgotten how to be thankful for my life. How do I reset?", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 31, "name": "Who am I?", "message": "I am 18 and I feel like I have no identity. What do the scriptures say?", "expected_domain": "spiritual", "should_recommend": False},
    {"id": 32, "name": "Fear of Death", "message": "I am 80 and I think about death every day. Give me some solace.", "expected_domain": "spiritual", "should_recommend": True},
    {"id": 33, "name": "Promotion Thanks", "message": "I got a promotion! I want to offer thanks. What ritual or item should I use?", "expected_domain": "career", "should_recommend": True},
    {"id": 34, "name": "Creative Block", "message": "I'm a writer and I've been blocked for months. Help me seek wisdom from Saraswati.", "expected_domain": "career", "should_recommend": True},
    {"id": 35, "name": "General Wellness", "message": "Just checking in, Mitra. How should I spend my evening in a Dharmic way?", "expected_domain": "spiritual", "should_recommend": False},
]

async def run_logic_probe():
    intent_agent = get_intent_agent()
    
    print(f"{'='*100}")
    print(f"{'ID':<4} | {'SCENARIO':<25} | {'DOMAIN':<12} | {'INTENT':<18} | {'PROD?':<6} | {'STATUS'}")
    print(f"{'='*100}")
    
    passed = 0
    total = len(scenarios)
    
    for s in sorted(scenarios, key=lambda x: x['id']):
        try:
            # Add a small delay to avoid rate limiting (429)
            await asyncio.sleep(1.5)
            
            analysis = await intent_agent.analyze_intent(s['message'])
            
            domain_ok = True
            rec_domain = analysis.get('life_domain', '').lower()
            if 'expected_domain' in s:
                # Career burnout can be career or spiritual
                # Fear of death can be health or spiritual
                allowed_domains = [s['expected_domain'].lower()]
                if s['expected_domain'].lower() == "career": allowed_domains.append("finance")
                if s['name'] == "The Burnout": allowed_domains.append("spiritual")
                if s['name'] == "Fear of Death": allowed_domains.append("health")
                # Grief is both family and spiritual
                if "Grief" in s['name']: allowed_domains.append("spiritual")
                
                domain_ok = rec_domain in allowed_domains
                
            rec_ok = True
            if 'should_recommend' in s:
                rec_ok = analysis.get('recommend_products') == s['should_recommend']
            
            status = "✅ PASS" if (domain_ok and rec_ok) else "❌ FAIL"
            if status == "✅ PASS": passed += 1
            
            print(f"{s['id']:<4} | {s['name']:<25} | {rec_domain:<12} | {analysis.get('intent', '???'):<18} | {str(analysis.get('recommend_products')):<6} | {status}")
            
            if status == "❌ FAIL":
                if not domain_ok: print(f"    -> Domain mismatch: got {rec_domain}, expected {s.get('expected_domain')}")
                if not rec_ok: print(f"    -> Recommend mismatch: got {analysis.get('recommend_products')}, expected {s.get('should_recommend')}")
                
        except Exception as e:
            print(f"{s['id']:<4} | {s['name']:<25} | ERROR: {str(e)}")
            if "429" in str(e):
                print("    -> Rate limit exceeded. Waiting 5 seconds before retry...")
                await asyncio.sleep(5)

    print(f"{'='*100}")
    print(f"RESULTS: {passed}/{total} Scenarios Passed Logical Validation")
    print(f"{'='*100}")

if __name__ == "__main__":
    asyncio.run(run_logic_probe())
