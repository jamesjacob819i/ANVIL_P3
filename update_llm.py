import re

with open("shared/llm.py", "r") as f:
    content = f.read()

# I will replace the llm_call retry logic to be more robust
new_logic = """
async def llm_call(
    system_prompt: str,
    user_prompt: str,
    response_model: Optional[type[BaseModel]] = None,
    temperature: float = 0.3,
    max_retries: int = 4,
) -> dict[str, Any]:
    if response_model:
        format_instruction = (
            f"\\n\\nYou MUST respond with valid JSON matching this schema:\\n"
            f"{response_model.model_json_schema()}"
        )
    else:
        format_instruction = "\\n\\nRespond with valid JSON."

    messages = [
        {"role": "system", "content": system_prompt + format_instruction},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    import random
    
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
                combined = f"{system_prompt}{format_instruction}\\n\\n{user_prompt}"
                response = chat.send_message(combined)
                text = response.text
            else:
                raise RuntimeError("No LLM configured. Set GROQ_API_KEY or GEMINI_API_KEY.")

            text = text.strip()
            if text.startswith("```"):
                text = text.split("\\n", 1)[-1]
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
                err_str = str(e).lower()
                print(f"[llm] Attempt {attempt + 1} failed: {e}, retrying...")
                if "429" in err_str or "quota" in err_str or "rate limit" in err_str:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"[llm] Rate limit hit. Sleeping for {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)
                elif "404" in err_str:
                    print(f"[llm] 404 Error encountered. Trying to recover by waiting 2s...")
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1 + random.uniform(0, 1))
                continue
            
    # If all attempts fail
    return {}

async def llm_call_freeform(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_retries: int = 4,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    import random
    
    for attempt in range(max_retries + 1):
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
                response = chat.send_message(f"{system_prompt}\\n\\n{user_prompt}")
                return response.text
            else:
                raise RuntimeError("No LLM configured. Set GROQ_API_KEY or GEMINI_API_KEY.")
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "rate limit" in err_str:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(1 + random.uniform(0, 1))
                continue
                
    return f"Error calling LLM after {max_retries + 1} attempts: {last_error}"
"""

# replace the functions
import re
new_content = re.sub(r"async def llm_call\(.*", new_logic, content, flags=re.DOTALL)
with open("shared/llm.py", "w") as f:
    f.write(new_content)
