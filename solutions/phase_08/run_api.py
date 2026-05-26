import sys
import uvicorn
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from akanga_core.app import AkangaApp
from akanga_core.server import create_app

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_api.py <vault_path> [db_path]")
        sys.exit(1)
    
    vault_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "akanga.db"
    
    akanga = AkangaApp(vault_path=vault_path, db_path=db_path)
    akanga.start_all()
    
    app = create_app(akanga)
    uvicorn.run(app, host="127.0.0.1", port=8000)
