import httpx
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")
print("Key starts with:", key[:10] if key else "None")
print("Key length:", len(key) if key else 0)

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {key}",
    "HTTP-Referer": "https://github.com/smuggypusss/Version-Constrained-API-Specification-Engine",
    "X-Title": "VCASE Engine",
    "Content-Type": "application/json"
}
payload = {
    "model": "deepseek/deepseek-v4-pro",
    "messages": [
        {"role": "user", "content": "say hi"}
    ]
}

resp = httpx.post(url, headers=headers, json=payload, timeout=10)
print("Status code:", resp.status_code)
print("Response:", resp.text)
