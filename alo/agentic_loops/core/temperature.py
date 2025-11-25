"""
=============================================================================
SCRIPT NAME: temperature.py
=============================================================================

Temperature configuration for ALO agents.

Different agent roles benefit from different temperature settings:

- CONTEXT (0.0): Deterministic file selection. We want consistent, reproducible
  identification of relevant files. No creativity needed.

- REPRO (0.0): Accurate code generation. Reproduction scripts must be syntactically
  correct and precisely test the described behavior.

- ENGINEERING (0.3): Moderate creativity. Bug fixes sometimes require creative
  solutions, but too much randomness produces inconsistent patches.

- REVIEW (0.0): Strict binary decisions. Reviews must be consistent and
  deterministic. PASS or FAIL should not depend on random sampling.

VERSION: 1.0
LAST UPDATED: 2025-01-24
=============================================================================
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TemperatureConfig:
    """Recommended temperatures for each agent role.

    Attributes:
        context: Temperature for context/file identification (default: 0.0)
        repro: Temperature for reproduction script generation (default: 0.0)
        engineering: Temperature for patch generation (default: 0.3)
        review: Temperature for patch review decisions (default: 0.0)
    """
    context: float = 0.0
    repro: float = 0.0
    engineering: float = 0.3
    review: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            "context": self.context,
            "repro": self.repro,
            "engineering": self.engineering,
            "review": self.review,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "TemperatureConfig":
        """Create from dictionary."""
        return cls(
            context=d.get("context", 0.0),
            repro=d.get("repro", 0.0),
            engineering=d.get("engineering", 0.3),
            review=d.get("review", 0.0),
        )

    @classmethod
    def all_zero(cls) -> "TemperatureConfig":
        """All temperatures at zero (fully deterministic)."""
        return cls(context=0.0, repro=0.0, engineering=0.0, review=0.0)

    @classmethod
    def creative(cls) -> "TemperatureConfig":
        """Higher temperatures for more creative solutions."""
        return cls(context=0.0, repro=0.1, engineering=0.5, review=0.0)


# Default recommended temperatures
RECOMMENDED_TEMPERATURES: Dict[str, float] = {
    "context": 0.0,      # Deterministic file selection
    "repro": 0.0,        # Accurate code generation
    "engineering": 0.3,  # Moderate creativity for fixes
    "review": 0.0,       # Strict pass/fail decisions
}


# Rationale for each temperature setting
TEMPERATURE_RATIONALE: Dict[str, str] = {
    "context": (
        "Temperature 0.0: Context identification requires deterministic, "
        "reproducible file selection. We want the same files identified "
        "for the same issue every time."
    ),
    "repro": (
        "Temperature 0.0: Reproduction scripts must be syntactically correct "
        "and precisely test the described behavior. Random variation in code "
        "generation leads to broken scripts."
    ),
    "engineering": (
        "Temperature 0.3: Bug fixes sometimes require creative solutions. "
        "A moderate temperature allows exploration of different fix approaches "
        "while maintaining code quality. Too high (>0.5) produces erratic patches."
    ),
    "review": (
        "Temperature 0.0: Code review decisions must be consistent and "
        "deterministic. A patch should receive the same verdict every time. "
        "Any randomness here would make the review unreliable."
    ),
}


def get_recommended_temperature(agent_role: str) -> float:
    """Get the recommended temperature for an agent role.

    Args:
        agent_role: One of 'context', 'repro', 'engineering', 'review'

    Returns:
        Recommended temperature (0.0 to 1.0)

    Raises:
        KeyError: If agent_role is not recognized
    """
    if agent_role not in RECOMMENDED_TEMPERATURES:
        raise KeyError(
            f"Unknown agent role: {agent_role}. "
            f"Valid roles: {list(RECOMMENDED_TEMPERATURES.keys())}"
        )
    return RECOMMENDED_TEMPERATURES[agent_role]


def get_temperature_from_config(
    model_config: Dict,
    agent_role: str,
    use_recommended: bool = True,
) -> float:
    """Get temperature from model config, falling back to recommended.

    Args:
        model_config: Model configuration dict (may contain 'temperature' key)
        agent_role: The agent role for fallback recommendations
        use_recommended: If True and no config temp, use recommended.
                        If False and no config temp, use 0.0.

    Returns:
        Temperature value (0.0 to 1.0)
    """
    # Check if config has explicit temperature
    if "temperature" in model_config:
        return float(model_config["temperature"])

    # Fall back to recommended or zero
    if use_recommended and agent_role in RECOMMENDED_TEMPERATURES:
        return RECOMMENDED_TEMPERATURES[agent_role]

    return 0.0


def validate_temperature(temperature: float, agent_role: Optional[str] = None) -> float:
    """Validate and clamp temperature to valid range.

    Args:
        temperature: Temperature value to validate
        agent_role: Optional role for warning about non-recommended values

    Returns:
        Validated temperature (clamped to 0.0-2.0 range)
    """
    # Clamp to valid range (most APIs accept 0-2)
    clamped = max(0.0, min(2.0, temperature))

    return clamped
