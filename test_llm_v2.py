
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path and set CWD to backend so .env is found naturally if needed, 
# but here we load it manually.
load_dotenv('backend/.env')

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.llm.service import get_llm_service
from backend.models.session import ConversationPhase

async def test_llm():
    service = get_llm_service()
    if not service.available:
        print(f"LLM Service not available. Key: {service.api_key[:5] if service.api_key else 'None'}...")
        return

    print("Testing LLM Response (gemini-1.5-flash)...")
    try:
        response = await service.generate_response(
            query="Namaste",
            conversation_history=[],
            phase=ConversationPhase.LISTENING
        )
        print(f"Response: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm())
