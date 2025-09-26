from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

for m in client.models.list().data:
    print(m.id)