"""Application composition: create and connect Kayla's independent modules."""

from kayla.ai.groq_chat import GroqChat
from kayla.config.settings import Settings
from kayla.conversation.session import ConversationSession
from kayla.prompts.kayla_personality import build_kayla_instructions


def build_conversation(settings: Settings) -> ConversationSession:
    """Build a conversation session from explicit application settings."""
    gateway = GroqChat(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.chat_model,
        instructions=build_kayla_instructions(settings.robot_name),
    )
    return ConversationSession(gateway=gateway)
