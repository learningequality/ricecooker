"""
Curriculum-related classes for structured educational content.

This module provides classes for representing curriculum concepts like
learning objectives, which can be associated with lessons and assessment
questions.
"""

import uuid

# Fixed namespace for generating deterministic learning objective UUIDs.
# Same text will always produce the same UUID.
LEARNING_OBJECTIVE_NAMESPACE = uuid.UUID("b5e3f3e8-9c7a-4d6b-8f2e-1a5c9d8e7f6b")


class LearningObjective:
    """
    Represents a learning objective that can be associated with lessons and questions.

    The ID is deterministically generated from the text using UUID5, so identical
    text always produces the same ID. This prevents accidental duplicates.

    Attributes:
        text (str): Human-readable description of the learning objective.
        id (str): Deterministic UUID5 generated from the text.
        metadata (dict): Optional metadata associated with the objective.
    """

    def __init__(self, text, metadata=None):
        """Create a new LearningObjective with deterministic UUID5 from text."""
        if not text or not text.strip():
            raise ValueError("LearningObjective text must be non-empty")
        self.text = text
        self.id = uuid.uuid5(LEARNING_OBJECTIVE_NAMESPACE, text).hex
        self.metadata = metadata or {}

    def to_dict(self):
        """Serialize the learning objective for inclusion in channel data."""
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
        }
