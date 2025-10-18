import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

DOMAIN_FILE_PATH = os.getenv("DOMAIN_FILE_PATH")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LlamaParse configuration
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
