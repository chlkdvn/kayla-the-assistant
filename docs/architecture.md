# Kayla architecture

## The main idea

Kayla is a software assistant running on one computer:

```text
Human
  |
  v
Computer
  microphone -> Python -> AI -> Python -> speaker
                           |
                           v
                    validated action
                           |
                           v
            browser, terminal, keyboard, camera

## Current request flow

The original text milestone follows this path:

```text
Terminal UI
    -> ConversationSession
        -> ChatGateway contract
            -> GroqChat implementation
                -> Groq chat-completions API (OpenAI-compatible SDK)
```

The return journey carries one value:

- `text`: the answer displayed to the user.

`ConversationSession` remembers the whole conversation as local turns and replays
them on each request. It does not know anything about HTTP, SDK objects, or
microphones.

## Responsibilities

### Configuration

`config/settings.py` loads environment variables and rejects missing required
values early. Secret values never belong in source code.

### Prompts

`prompts/kayla_personality.py` contains Kayla's behavioral instructions. Keeping the
prompt in code gives it normal review and test coverage. The prompt is sent on
every request because API-level instructions apply only to the current response.

### AI provider

`ai/gateway.py` defines the small contract the application needs: accept the
turn history and return an answer. `ai/groq_chat.py` is the only module that
knows the OpenAI SDK, pointed at Groq's compatible endpoint.

### Conversation

`conversation/session.py` owns multi-turn state. Because it depends on the
gateway contract instead of a provider directly, tests can use a fake provider and
future AI providers can be added without changing the session.

### Interface

`interfaces/cli.py` owns typed terminal input and output.
`interfaces/voice_cli.py` owns push-to-talk prompts. Microphone code remains in
the voice package rather than being mixed into either interface or the AI code.

### Application wiring

`app.py` creates the typed-chat objects. `voice/app.py` constructs voice-only
dependencies. Keeping construction at these boundaries makes dependencies
visible and prevents modules from secretly creating each other.

### Computer actions

`system/` contains the operating-system adapters that open browser pages, run
short shell commands, launch long-running commands in a separate terminal, and
type into the field the user has focused. It also maps spoken left/right swipes
to Niri's native column-navigation actions, with fixed `Super+Left` and
`Super+Right` shortcuts as the fallback on other desktops. Realtime conversation
logic calls these adapters through injected objects; it does not depend on
subprocess or desktop-tool details.

Continuous typing mode remains inside the Realtime boundary. The model only starts
the mode; after that, `realtime/dictation.py` converts completed transcripts into
text plus the allowlisted Enter/exit controls. The session temporarily disables
automatic model responses, avoids saving dictated content to memory, and sends
text through the keyboard adapter until the user exits the mode.

Browser opening is enabled separately because it is lower risk. Shell, terminal,
and keyboard actions share the explicit `KAYLA_SHELL_ENABLED` opt-in. Keyboard text
is passed as a subprocess argument rather than through a shell, and the user must
choose the destination by focusing a field first. See `docs/system.md` for setup
and the remaining risks of model-selected computer actions.

## Current voice boundary

The first voice milestone is a chained push-to-talk workflow:

```text
microphone.py
    -> groq_transcriber.py
        -> existing ConversationSession
            -> groq_speech.py
                -> speaker.py
```

`voice/contracts.py` defines the small data types and interfaces shared by those
stages. `voice/workflow.py` runs transcription, conversation, and speech
generation in order. Long replies are split to fit Groq's 200-character
speech-generation limit and reassembled before playback.
`interfaces/voice_cli.py` owns only the terminal prompts
that start and stop microphone capture.

Push-to-talk was chosen because every stage is visible and independently
testable. It also reuses the existing conversation state and remains available
as a diagnostic fallback.

## Current Realtime boundary

The low-latency path is a separate speech-to-speech architecture:

```text
StreamingMicrophone
    -> persistent Gemini Live session
        -> streaming model audio
            -> PcmPlaybackBuffer
                -> StreamingSpeaker
```

`realtime/options.py` owns the tool schemas and turn-detection timing.
`realtime/audio.py` owns local PCM capture, buffering, and playback.
`realtime/gemini_session.py` owns the live-session event loop and interruption
state. `interfaces/realtime_cli.py` only renders
human-readable status and transcripts.

`realtime/echo_cancel.py` owns the optional PipeWire WebRTC echo-cancellation
route. It creates temporary virtual input/output nodes before audio streams open
and restores the previous defaults afterward. Failure degrades to half-duplex, so
speaker echo cannot become an uncontrolled conversation loop.

Audio is sent while the user is still talking. Gemini's automatic activity
detection commits the turn after a short silence, and the model starts its
streaming response by itself - output audio is played as it arrives rather than
waiting for a complete file. Long-term memory reaches the model through the
`remember`/`recall` tools, with auto-capture storing each transcript
automatically.

### Behaviour modes

Spoken commands ('shut up', 'standby', 'speak', 'be serious', 'be playful', 'be
helpful', 'work') map to a `set_mode` tool in `realtime/modes.py`. The quiet modes
are enforced locally: the session swallows each muted turn's audio at the
session boundary - so no words escape until a resume word is heard. The
CURRENT MODE directive returned by `set_mode` tells the model how to behave;
tone modes change her style, quiet modes pair the directive with local silence.

When a user speaks during Kayla's answer, the local buffer discards audio that
was not played and the session reports that Kayla stopped to listen. Because the
model hears the interruption itself - it is a single full-duplex session - its
next response already reflects what the user actually heard.

## Milestones

1. Text chat on the computer. **Complete.**
2. Push-to-talk microphone and speaker flow. **Complete.**
3. Natural realtime voice conversation. **Complete.**
4. Wake-word attention gate and on-screen face. **Complete.**
5. Raspberry Pi deployment.
