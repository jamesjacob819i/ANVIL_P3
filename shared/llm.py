import os
import json
import asyncio
from typing import Optional, Any
from pydantic import BaseModel

from shared.tracing import trace

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

groq_client = None
gemini_client = None

if GROQ_API_KEY:
    try:
        from groq import AsyncGroq
        groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"[llm] Failed to init Groq: {e}")

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = genai
    except Exception as e:
        print(f"[llm] Failed to init Gemini: {e}")


@trace("llm_call", span_type="llm")
async def llm_call(
    system_prompt: str,
    user_prompt: str,
    response_model: Optional[type[BaseModel]] = None,
    temperature: float = 0.3,
    max_retries: int = 2,
) -> dict[str, Any]:
    if response_model:
        format_instruction = (
            f"\n\nYou MUST respond with valid JSON matching this schema:\n"
            f"{response_model.model_json_schema()}"
        )
    else:
        format_instruction = "\n\nRespond with valid JSON."

    messages = [
        {"role": "system", "content": system_prompt + format_instruction},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if groq_client:
                completion = await groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                text = completion.choices[0].message.content
            elif gemini_client:
                model = gemini_client.GenerativeModel(
                    "gemini-2.0-flash",
                    generation_config={
                        "temperature": temperature,
                        "response_mime_type": "application/json",
                    },
                )
                chat = model.start_chat()
                combined = f"{system_prompt}{format_instruction}\n\n{user_prompt}"
                response = chat.send_message(combined)
                text = response.text
            else:
                raise RuntimeError("No LLM configured. Set GROQ_API_KEY or GEMINI_API_KEY.")

            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            result = json.loads(text)

            if response_model:
                validated = response_model(**result)
                return validated.model_dump()
            return result

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"[llm] Attempt {attempt + 1} failed: {e}, retrying...")
                if "429" in str(e) or "quota" in str(e).lower():
                    print("[llm] Rate limit hit. Sleeping for 60s...")
                    await asyncio.sleep(60)
                else:
                    await asyncio.sleep(2)
                continue

    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")


@trace("llm_call_freeform", span_type="llm")
async def llm_call_freeform(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        if groq_client:
            completion = await groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=temperature,
            )
            return completion.choices[0].message.content
        elif gemini_client:
            model = gemini_client.GenerativeModel(
                "gemini-2.0-flash",
                generation_config={"temperature": temperature},
            )
            chat = model.start_chat()
            response = chat.send_message(f"{system_prompt}\n\n{user_prompt}")
            return response.text
        else:
            raise RuntimeError("No LLM configured. Set GROQ_API_KEY or GEMINI_API_KEY.")
    except Exception as e:
        return f"Error calling LLM: {e}"
