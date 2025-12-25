"""
Entry point for the Search Engine API.
This file allows running the app directly with uvicorn.

Usage:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
from backend.main import app

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
