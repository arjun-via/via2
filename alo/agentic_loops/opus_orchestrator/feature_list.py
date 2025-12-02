"""
=============================================================================
SCRIPT NAME: feature_list.py
=============================================================================

Feature List for incremental task execution.
Based on Anthropic's agent harness research.

Key insight: Use JSON to prevent models from modifying specifications.
"It is unacceptable to remove or edit tests because this could lead
to missing or buggy functionality."

INPUT FILES:
- None (data structure)

OUTPUT FILES:
- None (in-memory)

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
Provides an immutable feature list data structure for tracking incremental
feature implementation. Features can only have their status changed, not
their requirements or tests.

DEPENDENCIES:
- json (standard library)
- datetime (standard library)

=============================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import json
from datetime import datetime


class FeatureStatus(Enum):
    """Status of a feature in the execution pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Feature:
    """
    A single feature to implement.

    Attributes:
        id: Unique identifier (e.g., "F1", "F2")
        description: What this feature does
        status: Current status (pending, in_progress, completed, failed)
        tests: List of tests that must pass for this feature
        constraints: Feature-specific constraints
        assigned_model: Model assigned to implement this feature
        attempts: Number of implementation attempts
        last_error: Error message from last failed attempt
    """
    id: str
    description: str
    status: FeatureStatus = FeatureStatus.PENDING
    tests: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    assigned_model: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "tests": self.tests,
            "constraints": self.constraints,
            "assigned_model": self.assigned_model,
            "attempts": self.attempts,
            "last_error": self.last_error
        }


@dataclass
class FeatureList:
    """
    Immutable feature list for task execution.

    INVARIANT: Features can only have their STATUS changed.
    Descriptions and tests are IMMUTABLE once created.

    This is a key Anthropic insight: models will try to modify tests
    to make them pass. By using JSON and enforcing immutability,
    we prevent this failure mode.

    Attributes:
        task_id: Unique identifier for the overall task
        task_description: What the task should accomplish
        features: List of features to implement
        global_constraints: Constraints that apply to all features
        checkpoints: Git commit checkpoints after successful features
    """
    task_id: str
    task_description: str
    features: List[Feature]
    global_constraints: List[str] = field(default_factory=list)
    checkpoints: List[Dict] = field(default_factory=list)

    # This is the key Anthropic insight - enforce immutability
    INVARIANT = "NEVER remove or modify feature requirements or tests"

    def get_next_pending(self) -> Optional[Feature]:
        """
        Get the next pending feature to work on.

        Returns:
            The first pending feature, or None if all complete/failed
        """
        for feature in self.features:
            if feature.status == FeatureStatus.PENDING:
                return feature
        return None

    def mark_in_progress(self, feature_id: str) -> None:
        """
        Mark a feature as in progress.

        Args:
            feature_id: ID of the feature to update
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.IN_PROGRESS
                feature.attempts += 1
                return

    def mark_completed(self, feature_id: str) -> None:
        """
        Mark a feature as completed.

        Args:
            feature_id: ID of the feature to update
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.COMPLETED
                return

    def mark_failed(self, feature_id: str, error: str) -> None:
        """
        Mark a feature as failed with error message.

        Args:
            feature_id: ID of the feature to update
            error: Error message describing the failure
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.FAILED
                feature.last_error = error
                return

    def all_completed(self) -> bool:
        """
        Check if all features are completed.

        Returns:
            True if all features have status COMPLETED
        """
        return all(f.status == FeatureStatus.COMPLETED for f in self.features)

    def any_failed(self) -> bool:
        """
        Check if any features have failed.

        Returns:
            True if any feature has status FAILED
        """
        return any(f.status == FeatureStatus.FAILED for f in self.features)

    def get_progress(self) -> Dict[str, int]:
        """
        Get progress summary.

        Returns:
            Dict with completed, pending, failed, in_progress counts
        """
        return {
            "completed": len([f for f in self.features if f.status == FeatureStatus.COMPLETED]),
            "pending": len([f for f in self.features if f.status == FeatureStatus.PENDING]),
            "failed": len([f for f in self.features if f.status == FeatureStatus.FAILED]),
            "in_progress": len([f for f in self.features if f.status == FeatureStatus.IN_PROGRESS]),
            "total": len(self.features)
        }

    def add_checkpoint(self, feature_id: str, git_commit: str) -> None:
        """
        Record a checkpoint after successful feature completion.

        Args:
            feature_id: ID of the completed feature
            git_commit: Git commit hash for recovery
        """
        self.checkpoints.append({
            "feature_id": feature_id,
            "git_commit": git_commit,
            "timestamp": datetime.now().isoformat()
        })

    def to_json(self) -> str:
        """
        Export as JSON (prevents model modification).

        JSON format is intentional - models have harder time
        modifying JSON than Markdown, reducing the risk of
        requirement/test modifications.

        Returns:
            JSON string representation
        """
        return json.dumps({
            "task_id": self.task_id,
            "task_description": self.task_description,
            "invariant": self.INVARIANT,
            "features": [f.to_dict() for f in self.features],
            "global_constraints": self.global_constraints,
            "checkpoints": self.checkpoints,
            "progress": self.get_progress()
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "FeatureList":
        """
        Load from JSON.

        Args:
            json_str: JSON string to parse

        Returns:
            FeatureList instance
        """
        data = json.loads(json_str)
        features = [
            Feature(
                id=f["id"],
                description=f["description"],
                status=FeatureStatus(f["status"]),
                tests=f.get("tests", []),
                constraints=f.get("constraints", []),
                assigned_model=f.get("assigned_model"),
                attempts=f.get("attempts", 0),
                last_error=f.get("last_error")
            )
            for f in data["features"]
        ]
        return cls(
            task_id=data["task_id"],
            task_description=data["task_description"],
            features=features,
            global_constraints=data.get("global_constraints", []),
            checkpoints=data.get("checkpoints", [])
        )

    @classmethod
    def from_plan(cls, plan_data: dict) -> "FeatureList":
        """
        Create FeatureList from Opus planning output.

        Args:
            plan_data: Dict from Opus strategic planner

        Returns:
            FeatureList instance ready for execution
        """
        features = [
            Feature(
                id=f["id"],
                description=f["description"],
                tests=f.get("tests", []),
                constraints=f.get("constraints", []),
                assigned_model=f.get("assigned_model")
            )
            for f in plan_data.get("features", [])
        ]

        return cls(
            task_id=plan_data.get("task_id", "task_001"),
            task_description=plan_data.get("task_description", ""),
            features=features,
            global_constraints=plan_data.get("global_constraints", [])
        )
