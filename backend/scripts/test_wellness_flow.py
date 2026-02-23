import asyncio
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.companion_engine import get_companion_engine
from services.context_synthesizer import get_context_synthesizer
from services.response_composer import get_response_composer
from models.session import SessionState, ConversationPhase
from rag.pipeline import RAGPipeline

async def test_wellness_flow():
    print("\n" + "="*50)
    print("🚀 TESTING WELLNESS CONVERSATION FLOW (FULL)")
    print("="*50)

    # Initialize components
    rag = RAGPipeline()
    await rag.initialize()
    
    engine = get_companion_engine()
    engine.set_rag_pipeline(rag)
    
    synthesizer = get_context_synthesizer()
    composer = get_response_composer()
    
    session = SessionState()
    
    # Simulate a wellness-related conversation
    messages = [
        "Namaste, I've been feeling very tired and my digestion is not good lately.",
        "I've tried some medicines but it keeps coming back. What should I do according to Ayurveda?",
        "Also, I feel very stressed at work and can't focus. Any yoga practices for this?"
    ]
    
    for i, msg in enumerate(messages):
        print(f"\n👤 User: {msg}")
        session.add_message("user", msg)
        session.turn_count += 1
        
        # 1. Companion Engine Process
        companion_reply, is_ready, _ = await engine.process_message(session, msg)
        
        if not is_ready:
            print(f"🤖 Bot (Listening): {companion_reply}")
            session.add_message("assistant", companion_reply)
        else:
            print(f"🤖 Bot (Ready!): Generating Guidance...")
            
            # 2. Guidance Generation (Simulating main.py logic)
            session.phase = ConversationPhase.GUIDANCE
            
            # Synthesize query
            session.dharmic_query = synthesizer.synthesize_from_memory(session)
            search_query = session.dharmic_query.build_search_query()
            print(f"   🔍 RAG Query: {search_query}")
            
            # Retrieve verses
            retrieved_docs = await rag.search(
                query=search_query,
                scripture_filter=None,
                language="en",
                top_k=5
            )
            print(f"   📚 Found {len(retrieved_docs)} relevant docs.")
            
            # Compose full response
            response_text = await composer.compose_with_memory(
                dharmic_query=session.dharmic_query,
                memory=session.memory,
                retrieved_verses=retrieved_docs,
                conversation_history=session.conversation_history,
                phase=ConversationPhase.GUIDANCE,
                original_query=msg
            )
            
            print(f"🤖 Bot (Guidance): {response_text}")
            session.add_message("assistant", response_text)
        
    print("\n" + "="*50)
    print("📈 FINAL STATE")
    print("="*50)
    print(f"Life Area: {session.memory.story.life_area}")
    print(f"Readiness: {session.memory_readiness:.2f}")

if __name__ == "__main__":
    asyncio.run(test_wellness_flow())
