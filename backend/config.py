import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.25"))
OLLAMA_CONTEXT_SIZE = int(os.getenv("OLLAMA_CONTEXT_SIZE", "8192"))
APP_PORT = int(os.getenv("APP_PORT", "8000"))

OPIK_API_KEY = os.getenv("OPIK_API_KEY", "")
OPIK_PROJECT_NAME = os.getenv("OPIK_PROJECT_NAME", "QA-Test-Generator")
