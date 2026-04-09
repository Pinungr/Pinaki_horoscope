from datetime import datetime, timedelta, timezone
import logging
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List
from app.utils.logger import log_calculation_step
from core.engines.aspect_engine import calculate_aspects
from core.utils.chart_utils import extract_house, extract_planet_name, normalize_planet_name


logger = logging.getLogger(__name__)

class DashaEngine:
    """Calculates Vimshottari Mahadasha progression based on Moon's longitude."""

    _KNOWN_PLANETS = {
        "sun",
        "moon",
        "mars",
        "mercury",
        "jupiter",
        "venus",
        "saturn",
        "rahu",
        "ketu",
    }
    _SUPPORTIVE_HOUSES = {1, 4, 5, 7, 9, 10, 11}
    _CHALLENGING_HOUSES = {6, 8, 12}
    _DIGNITY_SCORE = {
        "exalted": 0.28,
        "own": 0.2,
        "friendly": 0.12,
        "neutral": 0.0,
        "enemy": -0.14,
        "debilitated": -0.24,
    }
    _FUNCTIONAL_ROLE_SCORE = {
        "yogakaraka": 0.24,
        "benefic": 0.18,
        "mild_benefic": 0.1,
        "neutral": 0.0,
        "mild_malefic": -0.1,
        "malefic": -0.2,
    }
    _ACTIVATION_BANDS = (
        (67.0, "high"),
        (40.0, "medium"),
        (0.0, "low"),
    )

    def __init__(self):
        # The exact order of Vimshottari Dasha Lords and their durations (years)
        self.dasha_sequence = [
            ("Ketu", 7),
            ("Venus", 20),
            ("Sun", 6),
            ("Moon", 10),
            ("Mars", 7),
            ("Rahu", 18),
            ("Jupiter", 16),
            ("Saturn", 19),
            ("Mercury", 17)
        ]
        
        # 13 degrees 20 minutes = 48000 arc-seconds
        self.NAKSHATRA_ARC_SEC = 48000
        self._total_years = sum(d for _, d in self.dasha_sequence)  # 120

    def calculate_dasha(self, moon_longitude: float, dob: str) -> List[Dict[str, str]]:
        """
        Calculates the Vimshottari Dasha timeline.
        dob format: 'YYYY-MM-DD'
        Returns list of sequential dicts: [{"planet": "Sun", "start": "2020-01-01", "end": "2026-01-01"}, ...]
        """
        log_calculation_step("dasha_calculation_started", moon_longitude=moon_longitude, dob=dob)
        
        # Normalize longitude
        moon_longitude = float(moon_longitude) % 360.0
        
        # 1. Convert to high-precision arc-seconds with epsilon-safe floor
        import math
        total_arc_sec = int(math.floor(moon_longitude * 3600 + 1e-6))
        
        # 2. Determine Nakshatra index (0 to 26)
        nakshatra_idx = total_arc_sec // self.NAKSHATRA_ARC_SEC
        nakshatra_idx = min(max(0, nakshatra_idx), 26) # Safety clamp
        
        # 3. Identify the starting Dasha block (repeats every 9)
        start_dasha_idx = nakshatra_idx % 9
        
        # 4. Calculate fraction passed through current Nakshatra using integer math
        arc_sec_passed = total_arc_sec % self.NAKSHATRA_ARC_SEC
        fraction_passed = arc_sec_passed / self.NAKSHATRA_ARC_SEC
        fraction_remaining = 1.0 - fraction_passed
        
        # 4. Starting planet and balance of duration at birth
        start_planet, total_years = self.dasha_sequence[start_dasha_idx]
        balance_years = total_years * fraction_remaining
        
        try:
            current_date = datetime.strptime(dob, "%Y-%m-%d")
        except ValueError:
            logger.warning("Invalid DOB '%s' received for dasha calculation. Falling back to UTC now.", dob)
            current_date = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC fallback (naive for consistency)
            
        timeline = []
        
        # Push the balance dasha first
        end_date = current_date + timedelta(days=balance_years * 365.2425)
        timeline.append({
            "planet": start_planet,
            "start": current_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        log_calculation_step("dasha_period_computed", planet=start_planet, start=timeline[-1]["start"], end=timeline[-1]["end"])
        current_date = end_date
        
        # 5. Populate the remainder of the 120-year lifespan cycle
        current_idx = (start_dasha_idx + 1) % 9
        # 8 more dashas guarantees full 120 year coverage from birth
        for _ in range(8):
            planet, duration_years = self.dasha_sequence[current_idx]
            end_date = current_date + timedelta(days=duration_years * 365.2425)
            timeline.append({
                "planet": planet,
                "start": current_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })
            log_calculation_step("dasha_period_computed", planet=planet, start=timeline[-1]["start"], end=timeline[-1]["end"])
            current_date = end_date
            current_idx = (current_idx + 1) % 9
            
        log_calculation_step("dasha_calculation_completed", periods=len(timeline))
        return timeline

    def calculate_dasha_with_antardashas(
        self, moon_longitude: float, dob: str
    ) -> List[Dict]:
        """
        Calculates the full Vimshottari Dasha timeline INCLUDING Antardasha
        (sub-period) breakdowns for every Mahadasha block.

        Each returned element contains a ``sub_periods`` list:

            {
                "planet": "Jupiter",
                "start": "2023-01-01",
                "end": "2039-01-01",
                "sub_periods": [
                    {"planet": "Jupiter", "antardasha": "Jupiter",
                     "start": "2023-01-01", "end": "2025-04-12"},
                    ...
                ]
            }

        Classical rule: duration of antardasha for planet B inside Mahadasha
        of planet A  =  (maha_duration_days * vimshottari_years_B / 120).
        """
        mahadashas = self.calculate_dasha(moon_longitude, dob)

        planet_years: Dict[str, int] = {p: y for p, y in self.dasha_sequence}
        sequence_names = [p for p, _ in self.dasha_sequence]

        result: List[Dict] = []
        for maha in mahadashas:
            maha_planet = maha["planet"]
            maha_start = datetime.strptime(maha["start"], "%Y-%m-%d")
            maha_end = datetime.strptime(maha["end"], "%Y-%m-%d")
            maha_duration_days = (maha_end - maha_start).days

            try:
                antar_start_idx = sequence_names.index(maha_planet)
            except ValueError:
                result.append(maha)
                continue

            sub_periods: List[Dict] = []
            antar_current = maha_start
            for offset in range(9):
                antar_idx = (antar_start_idx + offset) % 9
                antar_planet, antar_vimshottari = self.dasha_sequence[antar_idx]

                fraction = antar_vimshottari / self._total_years
                antar_days = maha_duration_days * fraction
                antar_end = antar_current + timedelta(days=antar_days)

                # Clamp last sub-period to Mahadasha boundary
                if offset == 8 or antar_end > maha_end:
                    antar_end = maha_end

                sub_periods.append({
                    "planet": maha_planet,
                    "antardasha": antar_planet,
                    "start": antar_current.strftime("%Y-%m-%d"),
                    "end": antar_end.strftime("%Y-%m-%d"),
                })
                antar_current = antar_end
                if antar_current >= maha_end:
                    break

            result.append({**maha, "sub_periods": sub_periods})

        log_calculation_step(
            "dasha_antardasha_completed",
            mahadashas=len(result),
            total_antardashas=sum(len(m.get("sub_periods", [])) for m in result),
        )
        return result

    def get_dasha_activation(
        self,
        chart: Any,
        current_dasha: Any,
        prediction_context: Any,
    ) -> Dict[str, Any]:
        """
        Computes a Dasha Activation Index (DAI) on a normalized 0-100 scale.

        Output:
        {
            "activation_score": 0.0..100.0,
            "activation_level": "high" | "medium" | "low",
            "contributing_factors": [
                {"factor": "...", "score": float, "evidence": [...]}
            ],
            "matched_planets": [...]
        }
        """
        context = prediction_context if isinstance(prediction_context, Mapping) else {}
        dasha = self._normalize_dasha_payload(current_dasha)
        mahadasha = dasha["mahadasha"]
        antardasha = dasha["antardasha"]

        if not mahadasha and not antardasha:
            return {
                "activation_score": 0.0,
                "activation_level": "low",
                "contributing_factors": [
                    {
                        "factor": "dasha_context",
                        "score": 0.0,
                        "evidence": ["No active Mahadasha/Antardasha context found."],
                    }
                ],
                "matched_planets": [],
            }

        relevant_houses = self._extract_houses(context)
        karakas = self._extract_planet_tokens(context.get("karakas"))
        yoga_planets = self._extract_planet_tokens(
            context.get("yoga_planets", context.get("key_planets", context.get("planets", [])))
        )
        yoga_strength = str(context.get("yoga_strength", context.get("strength", "medium"))).strip().lower()
        yoga_state = str(context.get("yoga_state", context.get("state", "strong"))).strip().lower()

        house_lord_details = self._normalize_house_lord_details(context.get("house_lord_details"))
        key_house_lords = self._extract_key_house_lords(relevant_houses, house_lord_details)
        functional_roles = self._normalize_functional_roles(context.get("functional_roles"))
        planet_strength = self._normalize_planet_strength(context.get("planet_strength"))

        factor_rows: list[dict[str, Any]] = []
        matched_planets: set[str] = set()

        relevance_score, relevance_evidence, relevance_matches = self._score_lord_relevance(
            mahadasha=mahadasha,
            antardasha=antardasha,
            key_house_lords=key_house_lords,
            karakas=karakas,
            yoga_planets=yoga_planets,
        )
        factor_rows.append(
            {
                "factor": "dasha_lord_relevance",
                "score": round(relevance_score, 2),
                "evidence": relevance_evidence,
            }
        )
        matched_planets.update(relevance_matches)

        condition_score, condition_avg, condition_evidence = self._score_lord_condition(
            mahadasha=mahadasha,
            antardasha=antardasha,
            house_lord_details=house_lord_details,
            functional_roles=functional_roles,
            planet_strength=planet_strength,
            fallback_strength=yoga_strength,
        )
        factor_rows.append(
            {
                "factor": "dasha_lord_condition",
                "score": round(condition_score, 2),
                "evidence": condition_evidence,
            }
        )

        yoga_score, yoga_evidence, yoga_matches = self._score_yoga_activation(
            mahadasha=mahadasha,
            antardasha=antardasha,
            yoga_planets=yoga_planets,
            yoga_strength=yoga_strength,
            yoga_state=yoga_state,
        )
        factor_rows.append(
            {
                "factor": "yoga_activation",
                "score": round(yoga_score, 2),
                "evidence": yoga_evidence,
            }
        )
        matched_planets.update(yoga_matches)

        connection_score, connection_evidence = self._score_planetary_connections(
            chart=chart,
            mahadasha=mahadasha,
            antardasha=antardasha,
            key_house_lords=key_house_lords,
        )
        factor_rows.append(
            {
                "factor": "planetary_connections",
                "score": round(connection_score, 2),
                "evidence": connection_evidence,
            }
        )

        raw_score = relevance_score + condition_score + yoga_score + connection_score
        adjusted_score = raw_score
        if condition_avg < 0.3 and raw_score > 0:
            adjusted_score *= 0.58
            factor_rows.append(
                {
                    "factor": "condition_dampening",
                    "score": round(adjusted_score - raw_score, 2),
                    "evidence": ["Weak dasha-lord condition dampens otherwise relevant activation."],
                }
            )
        elif condition_avg < 0.45 and raw_score > 0:
            adjusted_score *= 0.7
            factor_rows.append(
                {
                    "factor": "condition_dampening",
                    "score": round(adjusted_score - raw_score, 2),
                    "evidence": ["Moderately weak dasha-lord condition reduces activation support."],
                }
            )
        elif condition_avg > 0.75 and relevance_score >= 18.0:
            adjusted_score *= 1.08
            factor_rows.append(
                {
                    "factor": "condition_boost",
                    "score": round(adjusted_score - raw_score, 2),
                    "evidence": ["Strong dasha-lord condition amplifies relevance and yoga triggers."],
                }
            )

        activation_score = round(max(0.0, min(100.0, adjusted_score)), 2)
        activation_level = self._activation_level(activation_score)

        return {
            "activation_score": activation_score,
            "activation_level": activation_level,
            "contributing_factors": factor_rows,
            "matched_planets": sorted(matched_planets),
        }

    @staticmethod
    def _normalize_dasha_payload(current_dasha: Any) -> Dict[str, str]:
        payload = current_dasha if isinstance(current_dasha, Mapping) else {}
        mahadasha = normalize_planet_name(payload.get("mahadasha", payload.get("planet")))
        antardasha = normalize_planet_name(payload.get("antardasha"))
        return {
            "mahadasha": mahadasha,
            "antardasha": antardasha,
        }

    @staticmethod
    def _extract_houses(context: Mapping[str, Any]) -> list[int]:
        houses: list[int] = []
        raw_values = context.get("relevant_houses")
        if raw_values is None:
            raw_values = context.get("houses", context.get("house"))
        if not isinstance(raw_values, (list, tuple, set)):
            raw_values = [raw_values]
        for raw_house in raw_values:
            try:
                house = int(raw_house)
            except (TypeError, ValueError):
                continue
            if 1 <= house <= 12 and house not in houses:
                houses.append(house)
        return houses

    def _extract_planet_tokens(self, raw_planets: Any) -> list[str]:
        if not isinstance(raw_planets, (list, tuple, set)):
            raw_planets = [raw_planets]
        planets: list[str] = []
        for raw_planet in raw_planets:
            planet = normalize_planet_name(raw_planet)
            if planet and planet in self._KNOWN_PLANETS and planet not in planets:
                planets.append(planet)
        return planets

    @staticmethod
    def _normalize_house_lord_details(raw_details: Any) -> Dict[int, Dict[str, Any]]:
        if not isinstance(raw_details, Mapping):
            return {}
        normalized: Dict[int, Dict[str, Any]] = {}
        for raw_house, raw_row in raw_details.items():
            try:
                house = int(raw_house)
            except (TypeError, ValueError):
                continue
            if not isinstance(raw_row, Mapping) or house < 1 or house > 12:
                continue
            normalized[house] = dict(raw_row)
        return normalized

    @staticmethod
    def _normalize_functional_roles(raw_roles: Any) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        if isinstance(raw_roles, Mapping):
            for raw_planet, raw_role in raw_roles.items():
                planet = normalize_planet_name(raw_planet)
                role = str(raw_role or "").strip().lower()
                if planet and role:
                    normalized[planet] = role
            return normalized

        if isinstance(raw_roles, (list, tuple, set)):
            for item in raw_roles:
                if not isinstance(item, Mapping):
                    continue
                planet = normalize_planet_name(item.get("planet"))
                role = str(item.get("role", "")).strip().lower()
                if planet and role:
                    normalized[planet] = role
        return normalized

    @staticmethod
    def _normalize_planet_strength(raw_strength: Any) -> Dict[str, Any]:
        if not isinstance(raw_strength, Mapping):
            return {}

        normalized: Dict[str, Any] = {}
        for raw_planet, payload in raw_strength.items():
            planet = normalize_planet_name(raw_planet)
            if not planet:
                continue
            normalized[planet] = payload
        return normalized

    @staticmethod
    def _extract_key_house_lords(
        relevant_houses: list[int],
        house_lord_details: Mapping[int, Dict[str, Any]],
    ) -> list[str]:
        lords: list[str] = []
        for house in relevant_houses:
            row = house_lord_details.get(house, {})
            lord = normalize_planet_name(row.get("lord")) if isinstance(row, Mapping) else ""
            if lord and lord not in lords:
                lords.append(lord)
        return lords

    def _score_lord_relevance(
        self,
        *,
        mahadasha: str,
        antardasha: str,
        key_house_lords: list[str],
        karakas: list[str],
        yoga_planets: list[str],
    ) -> tuple[float, list[str], set[str]]:
        score = 0.0
        evidence: list[str] = []
        matches: set[str] = set()

        def _add_match(lord: str, points: float, reason: str) -> None:
            nonlocal score
            if not lord:
                return
            score += points
            matches.add(lord)
            evidence.append(reason)

        if mahadasha and mahadasha in key_house_lords:
            _add_match(
                mahadasha,
                15.0,
                f"Current Mahadasha lord {mahadasha.capitalize()} rules a key relevant house.",
            )
        if antardasha and antardasha in key_house_lords:
            _add_match(
                antardasha,
                9.0,
                f"Current Antardasha lord {antardasha.capitalize()} rules a key relevant house.",
            )
        if mahadasha and mahadasha in karakas:
            _add_match(
                mahadasha,
                12.0,
                f"Current Mahadasha lord {mahadasha.capitalize()} is a karaka for this area.",
            )
        if antardasha and antardasha in karakas:
            _add_match(
                antardasha,
                7.0,
                f"Current Antardasha lord {antardasha.capitalize()} is a karaka for this area.",
            )
        if mahadasha and mahadasha in yoga_planets:
            _add_match(
                mahadasha,
                28.0,
                f"Current Mahadasha lord {mahadasha.capitalize()} directly participates in the promise/yoga.",
            )
        if antardasha and antardasha in yoga_planets:
            _add_match(
                antardasha,
                16.0,
                f"Current Antardasha lord {antardasha.capitalize()} directly participates in the promise/yoga.",
            )

        if not evidence:
            evidence.append("Current dasha lords have limited direct relevance to the promise context.")

        return min(45.0, score), evidence, matches

    def _score_lord_condition(
        self,
        *,
        mahadasha: str,
        antardasha: str,
        house_lord_details: Mapping[int, Dict[str, Any]],
        functional_roles: Mapping[str, str],
        planet_strength: Mapping[str, Any],
        fallback_strength: str,
    ) -> tuple[float, float, list[str]]:
        weighted_sum = 0.0
        total_weight = 0.0
        evidence: list[str] = []

        for lord, weight, label in (
            (mahadasha, 0.65, "Mahadasha"),
            (antardasha, 0.35, "Antardasha"),
        ):
            if not lord:
                continue
            condition_score, lord_evidence = self._condition_for_planet(
                lord=lord,
                house_lord_details=house_lord_details,
                functional_roles=functional_roles,
                planet_strength=planet_strength,
                fallback_strength=fallback_strength,
            )
            weighted_sum += condition_score * weight
            total_weight += weight
            evidence.append(
                f"{label} lord {lord.capitalize()} condition score={condition_score:.2f}."
            )
            evidence.extend(lord_evidence)

        if total_weight <= 0:
            return 0.0, 0.0, ["Dasha-lord condition could not be evaluated from available chart context."]

        average_score = max(0.0, min(1.0, weighted_sum / total_weight))
        return round(average_score * 30.0, 2), average_score, evidence

    def _condition_for_planet(
        self,
        *,
        lord: str,
        house_lord_details: Mapping[int, Dict[str, Any]],
        functional_roles: Mapping[str, str],
        planet_strength: Mapping[str, Any],
        fallback_strength: str,
    ) -> tuple[float, list[str]]:
        score = 0.5
        evidence: list[str] = []

        role = str(functional_roles.get(lord, "neutral")).strip().lower() or "neutral"
        score += self._FUNCTIONAL_ROLE_SCORE.get(role, 0.0)
        evidence.append(f"{lord.capitalize()} functional nature is {role}.")

        strength_value = self._extract_strength_value(planet_strength.get(lord), fallback_strength=fallback_strength)
        if strength_value is not None:
            score += (strength_value - 0.5) * 0.7
            evidence.append(f"{lord.capitalize()} strength contribution normalized to {strength_value:.2f}.")
            if strength_value < 0.35:
                score -= 0.22
                evidence.append(f"{lord.capitalize()} has weak strength, reducing activation reliability.")
            elif strength_value > 0.75:
                score += 0.08
                evidence.append(f"{lord.capitalize()} has strong strength, improving activation reliability.")

        diagnostics = self._find_planet_diagnostics(lord, house_lord_details)
        if diagnostics:
            dignity = str(diagnostics.get("dignity", "neutral")).strip().lower()
            score += self._DIGNITY_SCORE.get(dignity, 0.0)

            placement_house = diagnostics.get("placement_house")
            if placement_house in self._SUPPORTIVE_HOUSES:
                score += 0.18
            elif placement_house in self._CHALLENGING_HOUSES:
                score -= 0.2

            if diagnostics.get("is_afflicted"):
                score -= 0.18
                evidence.append(f"{lord.capitalize()} carries affliction flags in house-lord diagnostics.")

            if placement_house is not None:
                evidence.append(
                    f"{lord.capitalize()} is placed in house {placement_house} with {dignity} dignity."
                )
            else:
                evidence.append(f"{lord.capitalize()} dignity is {dignity}, placement unavailable.")

        score = max(0.0, min(1.0, score))
        return score, evidence

    @staticmethod
    def _find_planet_diagnostics(
        planet: str,
        house_lord_details: Mapping[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        for row in house_lord_details.values():
            if not isinstance(row, Mapping):
                continue
            if normalize_planet_name(row.get("lord")) != planet:
                continue
            placement = row.get("placement", {}) if isinstance(row.get("placement"), Mapping) else {}
            dignity = row.get("dignity", {}) if isinstance(row.get("dignity"), Mapping) else {}
            affliction = row.get("affliction_flags", {}) if isinstance(row.get("affliction_flags"), Mapping) else {}
            return {
                "placement_house": placement.get("house"),
                "dignity": dignity.get("classification", "neutral"),
                "is_afflicted": bool(affliction.get("is_afflicted")),
            }
        return {}

    @staticmethod
    def _extract_strength_value(raw_strength: Any, *, fallback_strength: str) -> float | None:
        if isinstance(raw_strength, Mapping):
            level = str(raw_strength.get("level", raw_strength.get("classification", ""))).strip().lower()
            if level in {"strong", "medium", "weak"}:
                return {"strong": 0.85, "medium": 0.55, "weak": 0.2}[level]

            for key in ("score", "total", "value"):
                value = raw_strength.get(key)
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if key == "total":
                    return max(0.0, min(1.0, (numeric - 120.0) / 300.0))
                return max(0.0, min(1.0, numeric / 100.0 if numeric > 1.0 else numeric))

        if isinstance(raw_strength, (int, float)):
            numeric = float(raw_strength)
            return max(0.0, min(1.0, numeric / 100.0 if numeric > 1.0 else numeric))

        fallback = str(fallback_strength or "").strip().lower()
        if fallback in {"strong", "medium", "weak"}:
            return {"strong": 0.8, "medium": 0.55, "weak": 0.25}[fallback]
        return None

    @staticmethod
    def _score_yoga_activation(
        *,
        mahadasha: str,
        antardasha: str,
        yoga_planets: list[str],
        yoga_strength: str,
        yoga_state: str,
    ) -> tuple[float, list[str], set[str]]:
        evidence: list[str] = []
        matches: set[str] = set()
        maha_match = bool(mahadasha and mahadasha in yoga_planets)
        antar_match = bool(antardasha and antardasha in yoga_planets)

        score = 0.0
        if maha_match and antar_match:
            score += 16.0
            evidence.append("Both Mahadasha and Antardasha lords are tied to the active promise/yoga.")
            matches.update({mahadasha, antardasha})
        elif maha_match:
            score += 12.0
            evidence.append("Mahadasha lord participates in the active promise/yoga.")
            matches.add(mahadasha)
        elif antar_match:
            score += 8.0
            evidence.append("Antardasha lord participates in the active promise/yoga.")
            matches.add(antardasha)
        else:
            evidence.append("Current dasha lords are not direct yoga participants.")

        strength_bonus = {"strong": 4.0, "medium": 2.0, "weak": 0.5}.get(yoga_strength, 1.0)
        if maha_match or antar_match:
            score += strength_bonus
            evidence.append(f"Yoga strength ({yoga_strength}) adds {strength_bonus:.1f} activation support.")

        if yoga_state in {"weak", "cancelled"}:
            score = max(0.0, score - 2.0)
            evidence.append("Yoga state is weak/cancelled, reducing dasha-driven activation.")

        return min(20.0, score), evidence, matches

    def _score_planetary_connections(
        self,
        *,
        chart: Any,
        mahadasha: str,
        antardasha: str,
        key_house_lords: list[str],
    ) -> tuple[float, list[str]]:
        if not key_house_lords:
            return 0.0, ["No relevant house lords available for connection analysis."]

        chart_rows = self._extract_chart_rows(chart)
        if not chart_rows:
            return 0.0, ["Planetary connection analysis unavailable due to missing chart placements."]

        aspects = calculate_aspects(chart_rows)
        aspect_pairs = {
            (
                normalize_planet_name(aspect.get("from_planet")),
                normalize_planet_name(aspect.get("to_planet")),
            )
            for aspect in aspects
            if isinstance(aspect, Mapping)
        }
        house_map = {
            normalize_planet_name(row.get("planet_name")): extract_house(row)
            for row in chart_rows
            if isinstance(row, Mapping)
        }

        score = 0.0
        evidence: list[str] = []

        for lord, label, weight in (
            (mahadasha, "Mahadasha", 1.0),
            (antardasha, "Antardasha", 0.55),
        ):
            if not lord:
                continue
            for target in key_house_lords:
                if not target or target == lord:
                    continue

                same_house = house_map.get(lord) is not None and house_map.get(lord) == house_map.get(target)
                has_aspect = (lord, target) in aspect_pairs or (target, lord) in aspect_pairs

                if same_house:
                    points = 4.5 * weight
                    score += points
                    evidence.append(
                        f"{label} lord {lord.capitalize()} is conjunct key house lord {target.capitalize()}."
                    )
                if has_aspect:
                    points = 3.2 * weight
                    score += points
                    evidence.append(
                        f"{label} lord {lord.capitalize()} forms a drishti link with key house lord {target.capitalize()}."
                    )

        if not evidence:
            evidence.append("No strong conjunction/aspect links found between dasha lords and key house lords.")

        return min(15.0, score), evidence

    def _extract_chart_rows(self, chart: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        placements = getattr(chart, "placements", None)
        if isinstance(placements, Mapping):
            for planet_name, placement in placements.items():
                planet = normalize_planet_name(getattr(placement, "planet", planet_name))
                house = extract_house(placement)
                if planet in self._KNOWN_PLANETS and house is not None:
                    rows.append({"planet_name": planet, "house": house})
            return rows

        if isinstance(chart, Mapping):
            if {"planet_name", "planet", "Planet"} & set(chart.keys()):
                candidate_rows: Iterable[Any] = [chart]
            else:
                candidate_rows = []
                for planet, payload in chart.items():
                    if isinstance(payload, Mapping):
                        row = dict(payload)
                        row.setdefault("planet_name", planet)
                        candidate_rows = [*candidate_rows, row]
                    else:
                        candidate_rows = [*candidate_rows, {"planet_name": planet, "house": extract_house(payload)}]
        elif isinstance(chart, Iterable) and not isinstance(chart, (str, bytes)):
            candidate_rows = chart
        else:
            candidate_rows = []

        for row in candidate_rows:
            planet = extract_planet_name(row)
            house = extract_house(row)
            if planet in self._KNOWN_PLANETS and house is not None:
                rows.append({"planet_name": planet, "house": house})
        return rows

    def _activation_level(self, score: float) -> str:
        for threshold, label in self._ACTIVATION_BANDS:
            if score >= threshold:
                return label
        return "low"
