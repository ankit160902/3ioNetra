#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced citation explanations and personalization
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from llm.service import get_llm_service
from models.memory_context import ConversationMemory, UserStory


async def test_personalized_response():
    """
    Test the enhanced citation system with user profile
    """
    print("=" * 80)
    print("ENHANCED CITATION & PERSONALIZATION TEST")
    print("=" * 80)
    print()
    
    # Initialize LLM service
    llm = get_llm_service()
    
    if not llm.available:
        print("❌ LLM service not available. Please check GEMINI_API_KEY.")
        return
    
    print("✅ LLM service initialized")
    print()
    
    # Create a sample user profile
    user_profile = {
        'name': 'Rahul',
        'age_group': '25-34',
        'profession': 'Software Engineer',
        'gender': 'Male'
    }
    
    # Create sample context docs (simulating RAG retrieval)
    context_docs = [
        {
            'scripture': 'Bhagavad Gita',
            'reference': 'Chapter 14, Verse 23',
            'text': 'परहर्षः परीतिर आनन्दः साम्यं सवस्थात्म चित्तता अकस्माद यदि वा कस्माद वर्तते सात्त्विकॊ गुणः',
            'meaning': 'Joy, compassion, bliss, equanimity, and mental stability - whether arising spontaneously or from external causes - are the marks of the sattvic (pure) quality.',
            'score': 0.92
        },
        {
            'scripture': 'Mahabharata',
            'reference': '239.23',
            'text': 'उदासीनवद आसीनम गुणैर यॊ न विचाल्यते',
            'meaning': 'One who sits like an indifferent witness, not affected by the qualities (gunas), remains undisturbed.',
            'score': 0.87
        }
    ]
    
    # Sample conversation history
    conversation_history = [
        {
            'role': 'user',
            'content': 'I feel overwhelmed with work and struggling to maintain balance'
        },
        {
            'role': 'assistant',
            'content': "I hear that you're feeling stretched thin. Tell me more about what's happening at work."
        },
        {
            'role': 'user',
            'content': 'Long hours, constant deadlines, and I barely have time for my family'
        }
    ]
    
    # Current user query
    query = "How can I find peace in this chaos?"
    
    print("TEST SCENARIO:")
    print("-" * 80)
    print(f"User Profile: {user_profile}")
    print(f"Query: {query}")
    print(f"Available Verses: {len(context_docs)}")
    print()
    print("=" * 80)
    print("GENERATING RESPONSE...")
    print("=" * 80)
    print()
    
    # Generate response with personalization
    response = await llm.generate_response(
        query=query,
        context_docs=context_docs,
        language="en",
        conversation_history=conversation_history,
        user_id="test_user",
        user_profile=user_profile
    )
    
    print("RESPONSE:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    print()
    
    # Analysis
    print("ANALYSIS:")
    print("-" * 80)
    
    checks = {
        'Uses user name': user_profile['name'].lower() in response.lower(),
        'References profession': user_profile['profession'].lower() in response.lower() or 'engineer' in response.lower(),
        'Mentions scripture': any(doc['scripture'].lower() in response.lower() for doc in context_docs),
        'Provides explanation': len(response) > 200 and ('means' in response.lower() or 'teaching' in response.lower()),
        'Actionable advice': any(word in response.lower() for word in ['can', 'practice', 'try', 'apply', 'begin']),
        'No bibliography style': not response.strip().endswith('Citations:')
    }
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    print("-" * 80)
    print()
    
    total_passed = sum(checks.values())
    total_checks = len(checks)
    
    print(f"RESULT: {total_passed}/{total_checks} checks passed")
    
    if total_passed == total_checks:
        print("🎉 All personalization features working correctly!")
    elif total_passed >= total_checks * 0.7:
        print("⚠️  Most features working, some improvements needed")
    else:
        print("❌ Personalization needs attention")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_personalized_response())
