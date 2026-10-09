r"""Explicit, opt-in live smoke checks. Never prints keys or upstream error bodies.

Run from the project root: .venv\Scripts\python.exe scripts/check_ai_providers.py
Missing model IDs are selected from the provider's live catalog for this check
only. The user's .env is never modified. OpenRouter discovery uses free models.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from backend.app.config import load_local_env
from backend.app import station


def check(provider):
    started = time.monotonic()
    key_env, model_env, endpoint = station.PROVIDERS[provider]
    key, model = os.getenv(key_env), os.getenv(model_env, "")
    result = {"provider": provider, "key_present": bool(key), "model": model,
              "catalog_status": None, "generation_status": None, "validated": False}
    if not key:
        return result
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5), trust_env=False, follow_redirects=False) as client:
            headers = {"x-goog-api-key": key} if provider == "gemini" else {"Authorization": "Bearer " + key}
            catalog_url = {"groq": "https://api.groq.com/openai/v1/models",
                           "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
                           "openrouter": "https://openrouter.ai/api/v1/key"}[provider]
            response = client.get(catalog_url, headers=headers)
            result["catalog_status"] = response.status_code
            response.raise_for_status()
            catalog = response.json()
            if not model and provider == "gemini":
                candidates = [m["name"].removeprefix("models/") for m in catalog.get("models", [])
                              if "generateContent" in m.get("supportedGenerationMethods", [])
                              and "flash" in m["name"] and not any(s in m["name"] for s in ["image", "tts", "live", "preview", "exp"])]
                candidates.sort(key=lambda m: (m != "gemini-flash-lite-latest", "lite" not in m, m))
                model = candidates[0] if candidates else ""
            if not model and provider == "openrouter":
                response = client.get("https://openrouter.ai/api/v1/models", headers=headers)
                response.raise_for_status()
                candidates = [m["id"] for m in response.json().get("data", [])
                              if m["id"].endswith(":free") and "response_format" in m.get("supported_parameters", [])
                              and "text" in m.get("architecture", {}).get("output_modalities", [])]
                candidates.sort(key=lambda m: ("gpt-oss-20b" not in m, m))
                model = candidates[0] if candidates else ""
            result["model"] = model
            result["model_from_catalog_for_test_only"] = not bool(os.getenv(model_env))
            if not model:
                result["error"] = "no_suitable_model_configured_or_discovered"
                return result
            prompt = 'Return only JSON: {"card_ids":["plate_block"]}. No other fields.'
            if provider == "gemini":
                url = endpoint + model + ":generateContent"
                body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 1024}}
            else:
                url = endpoint
                body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}, "max_tokens": 1024}
            response = client.post(url, headers=headers, json=body)
            result["generation_status"] = response.status_code
            response.raise_for_status()
            data = response.json()
            content = ("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                       if provider == "gemini" else data["choices"][0]["message"]["content"])
            result["validated"] = station.Selection.model_validate_json(content).card_ids == ["plate_block"]
    except httpx.HTTPStatusError:
        result["error"] = "provider_http_error"
    except httpx.HTTPError:
        result["error"] = "provider_network_or_timeout"
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        result["error"] = "invalid_provider_response"
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return result


if __name__ == "__main__":
    load_local_env()
    with ThreadPoolExecutor(max_workers=3) as pool:
        print(json.dumps(list(pool.map(check, station.PROVIDERS)), indent=2))
