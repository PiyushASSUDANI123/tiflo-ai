import asyncio
import aiohttp
import os
from dotenv import load_dotenv
load_dotenv("/Users/piyush/Documents/AI/BACKEND/.env")
async def test():
    key = os.getenv("OPENROUTER_API_KEY")
    async with aiohttp.ClientSession() as s:
        async with s.post("https://openrouter.ai/api/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": "cognitivecomputations/dolphin3.0-r1-mistral-24b:free", "messages": [{"role": "user", "content": "hi"}]}) as r:
            print(r.status)
            print(await r.text())
asyncio.run(test())
