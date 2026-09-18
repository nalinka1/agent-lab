from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

r = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "say ok"}],
)
print(r.choices[0].message.content)
print(r.usage)
