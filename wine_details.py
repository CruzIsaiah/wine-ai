import json
from typing import Any

from google import genai
from google.genai import types


def answer_wine_question(wine: dict[str, Any], question: str) -> str:
    client = genai.Client()
    prompt = f"""
You are a knowledgeable, approachable sommelier. Answer the user's question about this wine.

Catalog data:
{json.dumps(wine, ensure_ascii=False, default=str)}

Question: {question}

Use the catalog data as the source of truth for product-specific facts. You may use established
general wine knowledge to explain the grape, style, likely tasting experience, food pairing,
serving temperature, glassware, and similar educational topics. Do not invent awards, exact
production methods, critic scores, availability, or facts not supported by the data. If the
catalog does not contain enough information for a factual answer, say what is unknown.
Keep the response useful and conversational, with at most three short paragraphs.
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    if not response.text:
        raise ValueError("No wine detail response was generated.")
    return response.text.strip()
