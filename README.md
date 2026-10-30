# Kayla

Kayla is a conversational assistant project, built as a rival to JARVIS. Kayla
currently supports typed chat, inspectable push-to-talk voice, and low-latency
realtime speech on a computer, with a camera, screen vision, and a floating 3D
orb she controls herself.

Source history: this project originates from
[Abmichael01/kel](https://github.com/Abmichael01/kel).

## What works now

- A floating **orb pop-out**: type `kayla` in a terminal (or the GNOME
  Activities search) and her orb rises, the terminal closes, and she just
  hovers. Single instance: already running means focused, never duplicated.
- **Laptop ownership through speech**: what's open, RAM/CPU/battery, opening
  any installed app, closing windows, raising the last-used window
  ("bring chrome up"), splitting the screen into slots, laptop focus mode
  (notifications off), best-performance power profile.
- **Phone focus over Wi-Fi**: put a paired iPhone into Do-Not-Disturb through
  the LAN bridge ([the phone guide](docs/devices.md)) — honestly with a
  "applies at next check-in" caveat.
- **Autostart**: `uv run kayla-boot --install` runs her at login and makes
  `kayla` findable in the desktop search.
- A terminal conversation (`kayla --chat`) and a push-to-talk microphone
  conversation with an AI-generated spoken reply.
- A continuous Realtime conversation with automatic turn detection and
  interruption, protected from speaker feedback by PipeWire WebRTC echo cancellation.
- Multi-turn context sent with every turn (Groq keeps no server-side state).
- Automatic vector-memory capture of each turn, plus `remember` / `recall`
  tools backed by a local embedding model.
- Optional browser, terminal, and focused-field typing actions in Realtime mode.
- **Screen vision** in Realtime mode: she can read what is on your screen
  (on by default; `KAYLA_SCREEN_ENABLED=false` turns it off).
- Continuous voice-to-keyboard typing mode with spoken Enter and exit controls.
- "stop listening" silences her hearing exactly like "shut up";
  "listen again" brings her back ([the orb guide](docs/orb.md)).
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
   greetings. Long-term memory runs entirely on this machine (no key). Its first start
downloads the embedding model once into `~/.cache/kayla/embeddings` (about
100 MB — on a phone hotspot expect minutes — and never again after that, not
even across reboots). `KAYLA_MEMORY_ENABLED=false` skips it entirely.

3. Start talking to her:

   ```bash
   uv run kayla
   ```

   That's the pop-out front door: her orb rises, your terminal closes, and she
   just hovers over the desktop. Session log: `~/.cache/kayla/kayla.log`.

   ```bash
   uv run kayla-realtime   # voice + orb inside the terminal
   uv run kayla --chat     # the classic typed chat
   ```

4. Make her start herself (optional):

   ```bash
   uv run kayla-boot --install    # systemd user unit + desktop entry
   uv run kayla-boot --status     # verify what is installed
   ```

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
| "shut up" / "be quiet" / "shush" / "stop listening" | Total silence. Even questions get no answer — only a resume command below gets through. |
| "standby" / "wait" / "stand by" | Same hard silence; she stays idle at attention. |
| "speak" / "talk to me" / "listen again" | Back to normal conversation. |
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

## The floating orb

In realtime mode the 3D orb replaces the old face window: a floating
always-on-top window with orbiting particles for Kayla, a message band, and at
session start the choice chips — *Work mode / Focus mode / Best performance /
All good*. Tapping one applies it immediately. Grab her body and the window
manager drags her natively, so she glides instead of buzzing; on a small screen
she auto-fits and clamps herself into the usable desktop (a fixed fraction of
it, never covering everything). Drop her near an edge and she snaps to a slot
("move to the left side" words work too); positions persist across restarts.
Full protocol and lifecycle: [the orb guide](docs/orb.md).

Saying "stop listening" is a hard hush — she stops hearing until you tell her
"listen again" (both enforced locally, exactly like "shut up").

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
5. `realtime/audio.py` places each chunk into the speaker buffer immediately,
   bending loudness under a soft-limiter ceiling; `KAYLA_SPEAKER_GAIN`
   (default 0.8, range 0.05–2.0) scales the output if speakers crackle.
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
│   ├── devices.md             # Phone focus bridge + the iPhone shortcut recipe
│   ├── orb.md                 # The floating orb: look, protocol, lifecycle
│   ├── realtime.md            # Low-latency streaming and interruption
│   ├── system.md              # Pages, terminals, laptop control tools
│   └── voice.md               # Push-to-talk flow and troubleshooting
├── src/kayla/
│   ├── ai/                    # AI contract and Groq implementation
│   ├── config/                # Environment-based settings
│   ├── conversation/          # Provider-independent session logic
│   ├── devices/               # LAN bridge to the paired phone
│   ├── interfaces/            # Pop-out front door, wake gate, voice UIs
│   ├── orb/                   # Floating 3D orb: state, render, window, client
│   ├── prompts/               # Kayla's personality and behavioral rules
│   ├── realtime/              # Gemini Live session and full-duplex PCM audio
│   ├── setup/                 # Setup wizard and boot autostart installer
│   ├── system/                # Laptop adapters: monitor, apps, windows, ...
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

See [the architecture guide](docs/architecture.md) for the full design, and
[docs/orb.md](docs/orb.md) / [docs/devices.md](docs/devices.md) for how the orb
and the phone bridge work.
