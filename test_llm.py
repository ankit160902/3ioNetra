
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.llm.service import get_llm_service
from backend.models.session import ConversationPhase

async def test_llm():
    load_dotenv()
    service = get_llm_service()
    if not service.available:
        print("LLM Service not available (API Key missing?)")
        return

    print("Testing LLM Response...")
    try:
        response = await service.generate_response(
            query="hi",
            conversation_history=[],
            phase=ConversationPhase.LISTENING
        )
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())
