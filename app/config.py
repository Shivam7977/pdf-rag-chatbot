import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")