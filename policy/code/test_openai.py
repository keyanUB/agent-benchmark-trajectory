from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

client = OpenAI()

response = client.responses.create(
    model="gpt-4.1-mini",
    input="Explain why secure coding practices matter in AI-generated code."
)

print(response.output_text)