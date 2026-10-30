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
- `ai/`: provider interfaces and the Groq chat implementation only.
- `conversation/`: provider-independent conversation state and orchestration.
- `prompts/`: version-controlled instructions that shape Kayla's behavior.
- `interfaces/`: ways a human interacts with Kayla: the pop-out front door
  (`cli.py`, spawns the detached orb session and closes the calling terminal),
  the wake gate, and the voice CLIs. Typed chat remains `cli.run_chat` behind
  `kayla --chat`.
- `orb/`: the floating 3D orb — state math, renderer, window process (drag,
  snap, chip questions, line protocol on port 8766), client, and the shared
  `open_orb_window`. Window actions happen only on the window thread via
  queued moves. Dragging is handed to the window manager on X11
  (`orb/x11drag.py`, `_NET_WM_MOVERESIZE`) with a pure-math fallback, so the
  borderless window never buzzes; she is born borderless and auto-fits and
  clamps into the work area. It replaces the face in realtime mode.
- `face/`: the earlier 2D keyboard-free face window; untouched, kept working.
- `voice/`: microphone and speaker concerns for the chained voice path.
- `memory/`: local vector memory store and the local embedding model.
- `realtime/`: continuous PCM streaming (with speaker loudness taming:
  soft knee, ceiling, and `speaker_gain`), Gemini Live session state, tool
  catalogue (`options.py`), behaviour modes, and interruption handling. Keep it
  independent from the chained `voice/` fallback.
- `system/`: operating-system adapters: browser, shell, keyboard, launcher,
  plus laptop awareness and control (`monitor`, `apps`, `windowctl`, `tiler`,
  `focus`, `performance`) and `session_exit` (terminal self-close for the
  pop-out). Runner-injected for offline tests.
- `devices/`: the LAN bridge to a paired phone (pairing, command queue, acks,
  notes). The phone performs Focus changes itself at its next poll; Kayla only
  queues the demand.
- `setup/`: the setup wizard and the boot autostart installer (`boot.py`:
  systemd user unit + desktop entry, runner-injected).

## Secrets

- Never commit `.env` or an API key.
- Keep `GROQ_API_KEY` and `GEMINI_API_KEY` in the local environment or local
  `.env` file.
- Examples must use placeholders, never real credentials.

## Verification

After Python changes, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests must not call the live Groq or Gemini APIs. Use fakes at the `ChatGateway`
boundary. Voice tests must also fake transcription and speech generation. A live
voice smoke test may be run manually when the owner explicitly asks to test voice.
