import json
import time
import requests
from pathlib import Path

# ======================================================
# CONFIGURATION
# ======================================================

API_KEY = "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"

MODEL = "moonshotai/kimi-k2.6"

INPUT_FILE = Path(
    r"data\netherlands\tudelft\programs\0001\pdf\source\evidence\pdf_evidence_chunks.json"
)

OUTPUT_DIR = Path("kimi_test_output")
OUTPUT_DIR.mkdir(exist_ok=True)

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ======================================================
# LOAD JSON
# ======================================================

with INPUT_FILE.open("r", encoding="utf-8") as f:
    evidence = json.load(f)

chunks = evidence["chunks"]

print(f"Found {len(chunks)} chunks")

# ======================================================
# SYSTEM PROMPT
# ======================================================

SYSTEM_PROMPT = """
You are an expert university information extraction system.

Extract every factual piece of information.

Return ONLY valid JSON.

{
  "facts":[
    {
      "category":"",
      "field":"",
      "value":"",
      "confidence":1.0
    }
  ]
}
"""

# ======================================================
# LOOP
# ======================================================

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

for chunk in chunks:

    chunk_id = chunk["chunk_id"]
    text = chunk["content"]

    print(f"\nProcessing {chunk_id}")

    # payload = {
    #     "model": MODEL,
    #     "messages": [
    #         {
    #             "role": "system",
    #             "content": SYSTEM_PROMPT,
    #         },
    #         {
    #             "role": "user",
    #             "content": text,
    #         },
    #     ],
    #     "temperature": 0,
    #     "top_p": 1,
    #     "max_tokens": 16384,
    #     "stream": False,
    # }

    payload = {
        "model": "moonshotai/kimi-k2.6",
        "messages": [
            {
                "role": "user",
                "content": "Say hello."
            }
        ],
        "max_tokens": 50,
    }

    try:

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=600,
        )

        print("Status:", response.status_code)

        result = response.json()

        output_file = OUTPUT_DIR / f"{chunk_id}.json"

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        if "choices" in result:

            print(result["choices"][0]["message"]["content"][:500])

        else:

            print(result)

    except Exception as e:

        print(f"FAILED: {e}")

    time.sleep(1)

print("\nDone.")


# import requests

# API_KEY = "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"

# response = requests.get(
#     "https://integrate.api.nvidia.com/v1/models",
#     headers={
#         "Authorization": f"Bearer {API_KEY}"
#     }
# )

# print(response.status_code)
# print(response.text)

# payload = {
#     "model": "moonshotai/kimi-k2.6",
#     "messages": [
#         {
#             "role": "user",
#             "content": "Say hello."
#         }
#     ],
#     "max_tokens": 50,
# }