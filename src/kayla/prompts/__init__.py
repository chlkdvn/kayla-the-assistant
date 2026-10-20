"""Version-controlled prompts that define Kayla's behavior."""

from kayla.prompts.kayla_personality import (
    build_kayla_instructions,
    build_kayla_realtime_instructions,
)

__all__ = ["build_kayla_instructions", "build_kayla_realtime_instructions"]
