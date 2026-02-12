import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.panchang_service import get_panchang_service

def test_panchang():
    service = get_panchang_service()
    if not service.available:
        print("Panchang service not available. Check dependencies.")
        return

    # Use a few known dates or current date
    test_dates = [
        datetime.now(),
        datetime(2025, 2, 26), # Maha Shivaratri 2025 (approx)
    ]

    print("\n" + "="*80)
    print("🚀 STARTING PANCHANG VERIFICATION")
    print("="*80)

    for dt in test_dates:
        print(f"\n📅 Calculating for: {dt}")
        # Default IST
        result = service.get_panchang(dt)
        if "error" in result:
            print(f"  ❌ Error: {result['error']}")
        else:
            print(json.dumps(result, indent=2))
            special = service.get_special_day_info(result)
            if special:
                print(f"  ✨ Special: {special}")

    print("\n" + "="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_panchang()
