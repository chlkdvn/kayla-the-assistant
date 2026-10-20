"""Application composition: create and connect Kayla's independent modules."""

from kayla.ai.openai_chat import OpenAIChat
from kayla.config.settings import ConfigurationError, Settings
from kayla.conversation.session import ConversationSession
from kayla.prompts.kayla_personality import build_kayla_instructions


def build_conversation(settings: Settings) -> ConversationSession:
    """Build a conversation session from explicit application settings."""
    if not settings.openai_api_key:
        raise ConfigurationError(
            "Text chat runs on OpenAI, which needs OPENAI_API_KEY in your .env. "
            "For the free Gemini voice mode instead, run:  uv run kayla-realtime"
        )
    gateway = OpenAIChat(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        instructions=build_kayla_instructions(settings.robot_name),
    )
    return ConversationSession(gateway=gateway)
