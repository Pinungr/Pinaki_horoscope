from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib import error, request

from app.services.app_settings_service import AppSettingsService


class OpenAIRefinerService:
    """Optional AI refinement layer for horoscope chat responses."""

    API_URL = "https://api.openai.com/v1/responses"
    SUPPORTED_TONES = {"professional", "friendly", "spiritual"}

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

    def refine_predictions(
        self,
        predictions: List[Dict[str, Any]],
        summary: Dict[str, Any] | None = None,
        *,
        tone: str = "professional",
    ) -> List[Dict[str, Any]]:
        """
        Refines aggregated prediction rows and appends `refined_text` to each item.

        The method preserves the existing structure and meaning. If AI is disabled
        or unavailable, it falls back to a deterministic local refinement.
        """
        normalized_tone = self._normalize_tone(tone)
        summary_payload = dict(summary or {})
        refined_rows: List[Dict[str, Any]] = []

        for prediction in predictions or []:
            if not isinstance(prediction, dict):
                continue
            row = dict(prediction)
            base_text = str(row.get("text", "")).strip()
            if not base_text:
                row["refined_text"] = ""
                refined_rows.append(row)
                continue

            refined_text = ""
            if self.is_enabled():
                try:
                    refined_text = self._refine_prediction_text_with_ai(
                        row,
                        summary_payload,
                        normalized_tone,
                    )
                except RuntimeError:
                    refined_text = ""

            if not refined_text:
                refined_text = self._fallback_refined_prediction_text(row, normalized_tone)

            refined_text = self._append_timing_sentence(
                refined_text,
                row.get("timing"),
                tone=normalized_tone,
            )
            row["refined_text"] = refined_text
            refined_rows.append(row)

        return refined_rows

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

    def _refine_prediction_text_with_ai(
        self,
        prediction: Dict[str, Any],
        summary: Dict[str, Any],
        tone: str,
    ) -> str:
        settings = self.settings_service.load()
        api_key = self._get_api_key(settings)
        if not api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        model = str(settings.get("openai_model") or "gpt-5-mini").strip() or "gpt-5-mini"
        prompt = self._build_prediction_refine_prompt(prediction, summary, tone)
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
                                "You are an expert Vedic astrology assistant. "
                                "Refine prediction language only. Keep the original meaning unchanged. "
                                "Return 2-3 sentences and include reasoning phrases like "
                                "'This is because', 'This indicates', and 'You may experience' naturally."
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
            raise RuntimeError("OpenAI API returned an empty prediction refinement.")
        return refined_text

    def _build_prediction_refine_prompt(
        self,
        prediction: Dict[str, Any],
        summary: Dict[str, Any],
        tone: str,
    ) -> str:
        context = {
            "tone": tone,
            "summary": summary,
            "prediction": {
                "yoga": prediction.get("yoga"),
                "area": prediction.get("area"),
                "strength": prediction.get("strength"),
                "score": prediction.get("score"),
                "text": prediction.get("text"),
                "timing": prediction.get("timing", {}),
            },
        }
        return (
            "Rewrite the prediction text into 2-3 sentences in astrologer tone.\n"
            "Do not change meaning, facts, or confidence level.\n"
            "Keep output plain text.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )

    def _fallback_refined_prediction_text(self, prediction: Dict[str, Any], tone: str) -> str:
        base_text = str(prediction.get("text", "")).strip()
        if not base_text:
            return ""

        area = str(prediction.get("area", "life areas")).strip() or "life areas"
        strength = str(prediction.get("strength", "medium")).strip().lower() or "medium"

        if tone == "friendly":
            lead = "This is because the chart pattern is clearly supportive."
            signal = f"This indicates momentum in {area} matters."
        elif tone == "spiritual":
            lead = "This is because your karmic pattern is activating this yoga."
            signal = f"This indicates a meaningful life lesson through {area}."
        else:
            lead = "This is because the planetary combination is astrologically significant."
            signal = f"This indicates notable effects in {area}."

        outcome = (
            "You may experience stronger and faster results."
            if strength == "strong"
            else "You may experience balanced and progressive outcomes."
            if strength == "medium"
            else "You may experience mild or delayed results initially."
        )

        parts = [base_text, lead, signal, outcome]
        return " ".join(part for part in parts if part).strip()

    def _normalize_tone(self, tone: str) -> str:
        normalized = str(tone or "professional").strip().lower() or "professional"
        if normalized not in self.SUPPORTED_TONES:
            return "professional"
        return normalized

    @staticmethod
    def _contains_timing_text(text: str) -> bool:
        normalized = str(text or "").strip().lower()
        return "mahadasha" in normalized or "antardasha" in normalized

    def _append_timing_sentence(self, text: str, timing: Any, tone: str = "professional") -> str:
        base = str(text or "").strip()
        if not base:
            return ""
        if self._contains_timing_text(base):
            return base

        line = self._build_timing_refinement_line(timing)
        if not line:
            return base

        adjusted = line
        if tone == "friendly":
            adjusted = adjusted.replace("This effect is especially pronounced", "You might really feel this")
        elif tone == "spiritual":
            adjusted = adjusted.replace("effect", "karmic influence")

        return f"{base} {adjusted}".strip()

    @staticmethod
    def _build_timing_refinement_line(timing: Any) -> str:
        if not isinstance(timing, dict):
            return ""

        mahadasha = str(timing.get("mahadasha") or "").strip()
        antardasha = str(timing.get("antardasha") or "").strip()
        relevance = str(timing.get("relevance") or "low").strip().lower() or "low"

        if not mahadasha and not antardasha:
            return ""

        if relevance == "high":
            if mahadasha and antardasha:
                return (
                    f"This effect is especially pronounced during your {mahadasha} Mahadasha, "
                    f"particularly in the {antardasha} phase."
                )
            if mahadasha:
                return f"This effect is especially pronounced during your {mahadasha} Mahadasha."
            return f"This effect is especially pronounced during your {antardasha} Antardasha."

        if relevance == "medium":
            if antardasha:
                if mahadasha:
                    return (
                        f"You may notice these results during your {antardasha} Antardasha "
                        f"within the {mahadasha} Mahadasha."
                    )
                return (
                    f"You may notice these results during your {antardasha} Antardasha."
                )
            if mahadasha:
                return f"You may notice these results during your {mahadasha} Mahadasha."
            return ""

        return ""

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
