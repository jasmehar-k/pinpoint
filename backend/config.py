import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
PEOPLE_PATH = REPO_ROOT / "people.json"
FIXTURES_DIR = REPO_ROOT / "fixtures"

load_dotenv(REPO_ROOT / ".env")

MODE = os.getenv("PINPOINT_MODE", "seeded")
DATABASE_URL = os.getenv("DATABASE_URL", "")
