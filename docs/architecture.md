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

The same boundary now owns **whole-laptop awareness and control**:

- `system/monitor.py` — `SystemMonitor`, real RAM/CPU/load/battery via `psutil`
  plus the open-window list via `wmctrl -l -x`; `describe` produces the numbers
  the model must read instead of guessing.
- `system/apps.py` — `DesktopApps`, launch any installed desktop app by fuzzy
  name through the desktop launcher (`.desktop` registry).
- `system/windowctl.py` — `WindowControl`, gracefully close or raise windows by
  app/title words with `wmctrl`.
- `system/tiler.py` — `WindowTiler`, tile visible windows into 2/3/4/6 slots on
  the work area read from `wmctrl -d`.
- `system/focus.py` — `FocusMode`, silence/restore GNOME notifications with
  `gsettings`, remembering the previous values.
- `system/performance.py` — `PerformanceMode`, switch power profiles through
  `powerprofilesctl`.
- `system/session_exit.py` — `close_calling_terminal`: the shell-ancestor walk
  that lets the `kayla` pop-out command close the terminal it was typed in
  (never killing pid 1, never closing an unsaved editor).

These are enabled together with `KAYLA_SYSTEM_TOOLS_ENABLED` (default *true*)
and each tool degrades to a spoken "X is not installed" when a helper is
missing. See `docs/system.md` for the per-tool detail.

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

## The orb boundary

`orb/` is Kayla's floating 3D presence: a small always-on-top pygame-ce window
with a software-rendered particle orb, a message band, and tap-able choice
chips. It replaces the 2D face in realtime mode (`face/` remains intact for the
forced-off case).

- `orb/state.py` — pure `OrbState`, energy mapping, slot/snap geometry and
  position persistence (no pygame imports needed for the logic).
- `orb/render.py` — the renderer: fibonacci-sphere rings, glowing core,
  message/question band layout.
- `orb/app.py` — the window process: event loop, drag, snap, protocol server
  (`handle_line`, `handle_connection`) and the two-step `ask` flow.
- `orb/client.py` — `OrbClient`: the brain's half of the line protocol.
- `orb/window.py` — `open_orb_window`: start detached, connect the client.

Ownership rules: everything touching the window (moving, focusing) happens on
the window thread through queued actions; the protocol is plain lines on
127.0.0.1; SIGINT/SIGTERM are handled explicitly because SDL swallows them. See
`docs/orb.md` for the full protocol and lifecycle.

The realtime session's startup chips ride this channel: on first connect the
session asks "How should we start?" over the orb and applies Work mode,
focus mode, or the performance profile locally - no model turn needed.

## The devices boundary

`devices/bridge.py` is the LAN bridge between Kayla and a paired phone:
pair-code exchange, per-device tokens, a persisted command queue
(`focus_on`/`focus_off`), acknowledgements, and one-line notes. The phone -
not Kayla - performs Focus changes through its own Shortcut, polling
`GET /commands`; commands therefore apply at the phone's next check-in, which
the instructions make Kayla admit. The bridge starts with realtime mode
(`KAYLA_DEVICES_*`) and never blocks anything else when it cannot bind. See
`docs/devices.md` for the shortcut recipe.

## The boot boundary

`setup/boot.py` installs autostart for the user session (no root): a systemd
user unit that starts the realtime session with the graphical session, and a
desktop entry so "kayla" in GNOME search raises her orb. Installer commands are
runner-injected for tests; `--install`, `--remove`, `--status` drive it.

## Interfaces boundary

`interfaces/cli.py` is the pop-out front door: bare `kayla` spawns the
detached realtime brain, focuses an already-running orb instead of making a
twin, then closes the calling terminal via `system/session_exit.py`.
`kayla --chat` keeps the classic typed conversation; `interfaces/realtime_cli.py`
only renders status and transcripts for the voice session.

## Milestones

1. Text chat on the computer. **Complete.**
2. Push-to-talk microphone and speaker flow. **Complete.**
3. Natural realtime voice conversation. **Complete.**
4. Wake-word attention gate and on-screen face. **Complete.**
5. Floating orb pop-out, laptop awareness and control, phone focus bridge,
   boot autostart. **Complete.**
6. Raspberry Pi deployment.
