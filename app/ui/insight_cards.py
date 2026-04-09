from __future__ import annotations

from typing import Any, Dict

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class SignalChip(QLabel):
    """Compact badge used to present one reasoning signal in a stable format."""

    _PALETTES: Dict[str, tuple[str, str, str]] = {
        "strong": ("#14532d", "#dcfce7", "#86efac"),
        "moderate": ("#92400e", "#fffbeb", "#fcd34d"),
        "weak": ("#991b1b", "#fef2f2", "#fca5a5"),
        "active": ("#1e3a8a", "#dbeafe", "#93c5fd"),
        "upcoming": ("#7c2d12", "#ffedd5", "#fdba74"),
        "dormant": ("#475569", "#f1f5f9", "#cbd5e1"),
        "amplifying": ("#065f46", "#d1fae5", "#6ee7b7"),
        "neutral": ("#334155", "#f8fafc", "#cbd5e1"),
        "suppressing": ("#9a3412", "#fff7ed", "#fdba74"),
        "high": ("#14532d", "#dcfce7", "#86efac"),
        "medium": ("#92400e", "#fffbeb", "#fcd34d"),
        "low": ("#991b1b", "#fef2f2", "#fca5a5"),
        "unknown": ("#334155", "#f8fafc", "#cbd5e1"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "font-size: 10px; font-weight: 600; border-radius: 10px; padding: 2px 8px;"
        )

    def set_chip(self, text: str, tone: str) -> None:
        normalized_tone = str(tone or "unknown").strip().lower() or "unknown"
        color, background, border = self._PALETTES.get(
            normalized_tone, self._PALETTES["unknown"]
        )
        self.setText(str(text or "").strip())
        self.setStyleSheet(
            f"font-size: 10px; font-weight: 600; border-radius: 10px; "
            f"padding: 2px 8px; color: {color}; background: {background}; border: 1px solid {border};"
        )


class ReasoningSignalRow(QWidget):
    """Renders Strength, Activation, Transit, and Concordance in one readable row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.strength_chip = SignalChip()
        self.activation_chip = SignalChip()
        self.transit_chip = SignalChip()
        self.concordance_chip = SignalChip()

        layout.addWidget(self.strength_chip)
        layout.addWidget(self.activation_chip)
        layout.addWidget(self.transit_chip)
        layout.addWidget(self.concordance_chip)
        layout.addStretch(1)
        self.setLayout(layout)

    def set_signals(
        self,
        *,
        strength_text: str,
        strength_tone: str,
        activation_text: str,
        activation_tone: str,
        transit_text: str,
        transit_tone: str,
        concordance_text: str,
        concordance_tone: str,
    ) -> None:
        self.strength_chip.set_chip(strength_text, strength_tone)
        self.activation_chip.set_chip(activation_text, activation_tone)
        self.transit_chip.set_chip(transit_text, transit_tone)
        self.concordance_chip.set_chip(concordance_text, concordance_tone)

    @staticmethod
    def normalize_label(value: Any, mapping: Dict[str, str], default: str) -> str:
        normalized = str(value or "").strip().lower()
        return mapping.get(normalized, default)
