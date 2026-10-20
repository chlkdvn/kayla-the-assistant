# Kayla project guidance

## Product intent

Kayla is a conversational assistant and software rival to JARVIS. During the first
phase, Kayla runs on a computer as a text-and-voice assistant with vision, computer
control, and an animated on-screen face.

## Working agreement with the owner

- Teach while building. Explain each important process in plain language and
  keep the documentation aligned with the code.
- Prefer small, understandable steps that can be run and verified before the
  next feature is added.
- Keep code modular. A module should have one clear responsibility.
- Group related code together, but do not place unrelated concerns in the same
  file or folder simply because it is convenient.
- Keep user interfaces, AI providers, conversation logic, voice I/O, and
  hardware communication separate.
- When an architectural decision changes, update `docs/architecture.md`.
- When setup or commands change, update `README.md`.

## Current module boundaries

- `config/`: environment variables and application settings only.
- `ai/`: provider interfaces and OpenAI API implementation only.
- `conversation/`: provider-independent conversation state and orchestration.
- `prompts/`: version-controlled instructions that shape Kayla's behavior.
- `interfaces/`: ways a human interacts with Kayla, beginning with the terminal.
- `voice/`: microphone and speaker concerns when voice is introduced.
- `realtime/`: continuous PCM streaming, Realtime API state, and interruption
  handling. Keep it independent from the chained `voice/` fallback.
## Secrets

- Never commit `.env` or an API key.
- Keep `OPENAI_API_KEY` in the local environment or local `.env` file.
- Examples must use placeholders, never real credentials.

## Verification

After Python changes, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests must not call the live OpenAI API. Use fakes at the `ChatGateway` boundary.
Voice tests must also fake transcription and speech generation. A live voice
smoke test may be run manually when the owner explicitly asks to test voice.
