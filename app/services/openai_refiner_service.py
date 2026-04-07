from __future__ import annotations

import json
import os
from typing import Any, Dict
from urllib import error, request

from app.services.app_settings_service import AppSettingsService


class OpenAIRefinerService:
    """Optional AI refinement layer for horoscope chat responses."""

    API_URL = "https://api.openai.com/v1/responses"

    def __init__(self, settings_service: AppSettingsService):
        self.settings_service = settings_service

    def is_enabled(self) -> bool:
        """Returns True when AI refinement is configured and enabled."""
        settings = self.settings_service.load()
        return bool(settings.get("ai_enabled")) and bool(self._get_api_key(settings))

    def refine_response(self, query: str, local_result: Dict[str, Any]) -> str:
        """
        Refines a local horoscope answer with OpenAI when enabled.

        Falls back by raising a RuntimeError on configuration/API failures so callers
        can keep the local response.
        """
        settings = self.settings_service.load()
        api_key = self._get_api_key(settings)
        if not settings.get("ai_enabled"):
            raise RuntimeError("AI enhancement is disabled.")
        if not api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        model = str(settings.get("openai_model") or "gpt-5-mini").strip() or "gpt-5-mini"
        prompt = self._build_prompt(query, local_result)
        payload = {
            "model": model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a warm, concise horoscope assistant. "
                                "Refine the local astrology answer using only the supplied context. "
                                "Do not invent facts or timing not present in the context. "
                                "If the context is limited, be transparent."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                },
            ],
        }

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.API_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=30) as response:
                response_json = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI API request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc.reason}") from exc

        refined_text = self._extract_text(response_json)
        if not refined_text:
            raise RuntimeError("OpenAI API returned an empty response.")
        return refined_text

    def _get_api_key(self, settings: Dict[str, Any]) -> str:
        """Resolves the API key from settings or environment."""
        return str(
            settings.get("openai_api_key")
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()

    def _build_prompt(self, query: str, local_result: Dict[str, Any]) -> str:
        """Formats structured local context for the Responses API."""
        data = local_result.get("data", {})
        context = {
            "query": query,
            "intent": local_result.get("intent", "general"),
            "local_response": local_result.get("response", ""),
            "prediction_summary": data.get("prediction_summary", ""),
            "confidence": data.get("confidence", ""),
            "timeline_hint": data.get("timeline_hint", ""),
            "matching_periods": data.get("matching_periods", []),
        }
        return (
            "Refine this horoscope answer into a clear, natural reply.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )

    def _extract_text(self, response_json: Dict[str, Any]) -> str:
        """Extracts response text from a Responses API payload."""
        if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
            return response_json["output_text"].strip()

        output_items = response_json.get("output", [])
        parts: list[str] = []
        for item in output_items:
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    text = str(content.get("text") or content.get("value") or "").strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts).strip()
