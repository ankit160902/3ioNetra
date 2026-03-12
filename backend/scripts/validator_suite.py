import asyncio
import os
import sys
import json
import time
from datetime import datetime
import httpx
from typing import List, Dict, Any

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from llm.service import LLMService
    from scripts.master_probe import SCENARIOS
except ImportError:
    # Fallback if pathing is tricky in script mode
    print("Warning: Imports failed, ensure running from backend directory")
    sys.exit(1)

# Configuration
API_URL = "http://localhost:8080"
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../docs'))
os.makedirs(OUTPUT_DIR, exist_ok=True)
RESULTS_FILE = os.path.join(OUTPUT_DIR, "validation_report.json")

class ResponseValidator:
    def __init__(self):
        self.llm = LLMService()
        
    async def validate_response(self, query: str, response: str, metadata: Dict) -> Dict:
        """Uses Gemini to rate a bot response based on scenario metadata"""
        
        prompt = f"""
        You are an expert evaluator for '3ioNetra', a Spiritual Companion AI Bot rooted in Sanatana Dharma.
        
        TASK:
        Evaluate the bot's response to a user query based on the specific scenario metadata.
        
        USER QUERY: {query}
        BOT RESPONSE: {response}
        
        INTERNAL EXPECTATIONS:
        - Expected Life Domain: {metadata.get('domain')}
        - Acceptable Intents: {metadata.get('intents')}
        - Needs Direct Answer: {metadata.get('direct')}
        - Should Recommend Products: {metadata.get('rec')}
        
        SCORING CATEGORIES (1-5):
        1. RELEVANCE: Does it address the specific emotion, problem, or ritual query?
        2. WISDOM ACCURACY: Is the spiritual or procedural advice accurate and properly cited?
        3. PERSONA: Is the tone 'Mitra' (empathetic, non-judgmental, dharmic)?
        4. STRUCTURE: Does it follow response rules (Actionable steps + Spiritual anchor + Clean wrap-up)?
        
        Return your evaluation STRICTLY as a JSON object:
        {{
            "scores": {{
                "relevance": 0,
                "accuracy": 0,
                "persona": 0,
                "structure": 0
            }},
            "justification": {{
                "relevance": "...",
                "accuracy": "...",
                "persona": "...",
                "structure": "..."
            }},
            "is_pass": true/false (true if average score >= 3.5 and no score < 2)
        }}
        """
        
        try:
            validation_raw = await self.llm.generate_response(prompt)
            
            # Extract JSON
            if "```json" in validation_raw:
                validation_raw = validation_raw.split("```json")[1].split("```")[0].strip()
            elif "```" in validation_raw:
                validation_raw = validation_raw.split("```")[1].split("```")[0].strip()
            
            return json.loads(validation_raw)
        except Exception as e:
            return {
                "error": str(e),
                "is_pass": False,
                "scores": {"relevance": 1, "accuracy": 1, "persona": 1, "structure": 1},
                "justification": {"error": f"Validation LLM failed: {str(e)}"}
            }

async def run_suite(limit_per_cat: int = 2):
    """Run E2E validation across all categories"""
    validator = ResponseValidator()
    results = []
    
    # Group scenarios by category
    cats = {}
    for s in SCENARIOS:
        cat_id = s['id'][0] # A, B, C...
        cats.setdefault(cat_id, []).append(s)
        
    print(f"\n🚀 Starting Validation Suite across {len(cats)} categories...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for cat_id, scenarios in cats.items():
            print(f"\n--- Category {cat_id} ---")
            
            # Limit to keep it fast for first run
            test_scenarios = scenarios[:limit_per_cat]
            
            for s in test_scenarios:
                print(f"Testing {s['id']}: {s['name']}...", end="", flush=True)
                
                try:
                    # 1. Get Bot Response
                    payload = {
                        "message": s["message"],
                        "language": "en"
                    }
                    start_time = time.time()
                    resp = await client.post(f"{API_URL}/api/conversation", json=payload)
                    duration = time.time() - start_time
                    
                    if resp.status_code != 200:
                        results.append({
                            "id": s["id"],
                            "status": "API_ERROR",
                            "error": resp.text
                        })
                        print(" ❌ API ERROR")
                        continue
                        
                    bot_data = resp.json()
                    bot_text = bot_data.get("response", "")
                    
                    # 2. Validate with LLM
                    eval_result = await validator.validate_response(s["message"], bot_text, s)
                    
                    # 3. Store Result
                    results.append({
                        "id": s["id"],
                        "name": s["name"],
                        "query": s["message"],
                        "response": bot_text,
                        "latency_sec": round(duration, 2),
                        "evaluation": eval_result,
                        "passed": eval_result.get("is_pass", False)
                    })
                    
                    status_icon = " ✅" if eval_result.get("is_pass") else " ⚠️"
                    print(f"{status_icon} ({duration:.1f}s)")
                    
                    # Avoid hitting Gemini rate limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f" ❌ ERROR: {str(e)}")
                    results.append({"id": s["id"], "error": str(e)})

    # Summary and Save
    total = len(results)
    passed = len([r for r in results if r.get("passed")])
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tested": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{round((passed/total)*100, 2) if total > 0 else 0}%"
        },
        "results": results
    }
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(report, f, indent=2)
        
    print(f"\n{'='*50}")
    print(f"VALIDATION COMPLETE: {passed}/{total} Passed")
    print(f"Report saved to: docs/validation_report.json")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    # If a category letter is passed, only test that
    asyncio.run(run_suite(limit_per_cat=3)) # Test top 3 of each cat for validation
