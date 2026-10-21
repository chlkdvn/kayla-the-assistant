# Kayla

Kayla is a conversational assistant project, built as a rival to JARVIS. Kayla
currently supports typed chat, inspectable push-to-talk voice, and low-latency
realtime speech on a computer, with a camera, screen vision, and an animated face.

Source history: this project originates from
[Abmichael01/kel](https://github.com/Abmichael01/kel).

## What works now

- A terminal conversation with Kayla.
- A push-to-talk microphone conversation with an AI-generated spoken reply.
- A continuous Realtime conversation with automatic turn detection and
  interruption, protected from speaker feedback by PipeWire WebRTC echo cancellation.
- Multi-turn context sent with every turn (Groq keeps no server-side state).
- Automatic vector-memory capture of each turn, plus `remember` / `recall`
  tools backed by a local embedding model.
- Optional browser, terminal, and focused-field typing actions in Realtime mode.
- Continuous voice-to-keyboard typing mode with spoken Enter and exit controls.
- Kayla's personality stored as a version-controlled prompt.
- Clear module boundaries so voice and hardware can be added without rewriting
  the conversation core.
- Unit tests that run without an API key or network request.

## Requirements

- `uv` for Python environment and dependency management.
- A free Google Gemini API key (realtime voice) and a free Groq API key (chat,
  push-to-talk voice, wake greetings).
- A microphone and speaker recognized by the operating system.
- PortAudio, which is already installed on this development computer.

The project supports Python 3.11 or newer. This computer is configured to use
Python 3.13 for the project.

## First-time setup

1. Install the project. `voice` is her brain/audio, `face` is the on-screen face
   (add `dev` if you'll run the tests):

   ```bash
   uv sync --extra voice --extra face
   ```

2. Run the setup wizard. It asks for your (free) Gemini and Groq keys, picks
   your audio, can download the wake model and writes your `.env`:

   ```bash
   uv run kayla-setup
   ```

   Prefer to do it by hand? Copy `.env.example` to `.env` and fill it in. `.env`
   is gitignored — never commit or share it. Both keys are **free**: Gemini
   serves her realtime voice, Groq serves chat, push-to-talk voice, and wake
   greetings. Long-term memory runs entirely on this machine (no key).

3. Start talking to her:

   ```bash
   uv run kayla-realtime
   ```

   `uv run kayla` is a typed-chat mode instead (also Groq, same key).

## Sharing Kayla with someone

She's built to run on a fresh machine gracefully: with no camera she just can't
see, and missing optional pieces (wake model, face) simply turn off. Hand a
friend the repo, have them run `uv run kayla-setup` for the two free keys, and
she's ready. The wizard defaults to safe settings — computer/shell control is
**off** until they explicitly turn it on. Everything below is Linux-oriented
(audio, `wtype` typing, Niri desktop actions, serial ports).

## Start voice mode

For the natural, low-latency mode, run:

```bash
uv run kayla-realtime
```

The connection stays open: simply speak, wait briefly after finishing, and Kayla
will answer as audio arrives. You can interrupt Kayla by speaking again. Press
`Ctrl+C` to stop. Use headphones so Kayla does not hear his own speaker output.

The older chained mode remains useful when debugging individual stages:

```bash
uv run kayla-voice
```

Then:

1. Press Enter to begin recording.
2. Speak into the microphone.
3. Press Enter again to stop recording.
4. Read the transcript and Kayla's response while the generated voice plays.

Use `/reset` to clear the conversation or `/exit` to stop. Headphones help avoid
Kayla's speaker output feeding back into the microphone.

If the wrong microphone or speaker is selected, list available devices:

```bash
uv run python -m sounddevice
```

Set `KAYLA_AUDIO_INPUT_DEVICE` or `KAYLA_AUDIO_OUTPUT_DEVICE` in `.env` to a device
name or number from that list. Leave them blank to use the system defaults.

## Voice instructions

While talking to Kayla in realtime voice mode, these exact words switch how she
behaves:

| You say | What changes |
| --- | --- |
| "shut up" / "be quiet" / "shush" | Total silence. Even questions get no answer — only a resume command below gets through. |
| "standby" / "wait" / "stand by" | Same hard silence; she stays idle at attention. |
| "speak" / "talk to me" | Back to normal conversation. |
| "be serious" | No jokes; precise, direct, focused. |
| "be playful" | Jokes, teasing, playful energy. |
| "be helpful" | Assistant-first: anticipates your next step, finishes the task. |
| "work" / "get to work" / "focus" | Strictly task-focused, minimal chatter. |

Helpful details:

- Quotes are just examples — the words work as bare commands too ("Kayla, shut up!").
- While quiet, only the command words pass through; ordinary sentences do nothing.
- These commands are separate from the wake word: say `"Kayla, pay attention"`
  first if she is asleep (`KAYLA_WAKE_PHRASES_SLEEP=at ease` puts her back to bed).
- Her feelings (face moods) respond to conversation as before; voice instructions
  only change how she talks and listens.

## What happens when you send a message

1. `interfaces/cli.py` reads text from the terminal.
2. `conversation/session.py` validates the message and appends it to the
   conversation history it keeps locally.
3. `ai/groq_chat.py` sends Kayla's instructions plus the whole history to Groq's
   chat-completions endpoint (OpenAI-compatible, so the OpenAI SDK talks to it).
4. The API returns Kayla's answer.
5. The session stores the exchange and the terminal prints the answer.

This separation mattered when voice was added: the new interface reused the AI
and conversation modules without changing their responsibilities.

## What happens during a voice turn

1. `voice/microphone.py` captures 16-bit microphone samples and creates a WAV.
2. `voice/groq_transcriber.py` turns that recording into text (Whisper on Groq).
3. The existing `ConversationSession` sends the text to Kayla's AI brain.
4. `voice/groq_speech.py` turns Kayla's text answer into an AI-generated WAV
   (long replies are chunked to fit Groq's 200-character TTS limit).
5. `voice/speaker.py` plays that WAV through the computer speaker.

Every intermediate result remains visible, which makes this first voice version
easier to learn and debug. See [the voice guide](docs/voice.md) for details.

## What happens during a realtime turn

1. The microphone continuously produces small 16 kHz PCM chunks.
2. `realtime/gemini_session.py` sends each chunk over one persistent Gemini Live
   session.
3. Server-side activity detection decides when you started and stopped talking.
4. Gemini responds directly with incremental PCM audio chunks.
5. `realtime/audio.py` places each chunk into the speaker buffer immediately.
6. If you speak during playback, unplayed audio is cleared and the unheard part
   of Kayla's answer is removed from conversation state.

See [the Realtime guide](docs/realtime.md) for the complete process and tuning
controls. See [the computer actions guide](docs/system.md) to let Kayla open pages,
run commands, or type into a field you focus.

## Project map

```text
.
├── AGENTS.md                  # Durable guidance for future AI coding agents
├── docs/
│   ├── architecture.md        # Detailed design and roadmap
│   ├── realtime.md            # Low-latency streaming and interruption
│   ├── system.md              # Browser, terminal, and focused-field actions
│   └── voice.md               # Push-to-talk flow and troubleshooting
├── src/kayla/
│   ├── ai/                    # AI contract and Groq implementation
│   ├── config/                # Environment-based settings
│   ├── conversation/          # Provider-independent session logic
│   ├── interfaces/            # Typed and voice terminal interfaces
│   ├── prompts/               # Kayla's personality and behavioral rules
│   ├── realtime/              # Gemini Live session and full-duplex PCM audio
│   ├── system/                # Browser, shell, terminal, and keyboard adapters
│   ├── voice/                 # Recording, transcription, speech, and playback
│   └── app.py                 # Connects the typed-chat modules
└── tests/                     # Offline unit tests
```

## Development checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

See [the architecture guide](docs/architecture.md) for the full design and the.
