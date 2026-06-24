"""
=============================================================================
ThirdLine — API Server Runner
=============================================================================

FILE: scripts/run_api.py

HOW TO RUN:
    python scripts/run_api.py
    Then open: http://localhost:8000/docs
=============================================================================
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

import uvicorn

if __name__ == "__main__":
    print("\nThirdLine API starting...")
    print("  API:  http://localhost:8000")
    print("  Docs: http://localhost:8000/docs\n")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
