# Kayla Realtime voice guide

## Why this mode is faster

The push-to-talk pipeline waits for three separate remote jobs: transcription,
text reasoning, and speech generation. It also waits for complete recordings and
complete generated WAV files.

Realtime mode keeps one Gemini Live connection open and streams in both
directions:

```text
microphone PCM -> Gemini Live session -> streaming PCM -> speaker buffer
```

The server receives audio while you are speaking. Its activity detection ends
the turn, and the model answers on its own - Kayla plays the first returned audio
chunks without waiting for the full response.

## Run it

```bash
uv sync --extra dev --extra voice
uv run kayla-realtime
```

There is no record button. Speak naturally after `Live connection ready`
appears. Pause when finished, then Kayla answers. Speak again to interrupt. Press
`Ctrl+C` to close the microphone, speaker, and session cleanly.

## Echo cancellation options

Half-duplex (the default, `KAYLA_REALTIME_HALF_DUPLEX=true`) mutes the
microphone while Kayla speaks, which stops her hearing her own echo but means you
cannot interrupt by voice - only `Ctrl+C` or a gesture ends her turn:

```text
KAYLA_AUDIO_INPUT_DEVICE=pulse
KAYLA_AUDIO_OUTPUT_DEVICE=pulse
KAYLA_REALTIME_HALF_DUPLEX=true
```

For headphones, or a room where you want to barge in by voice, use full-duplex
plus this computer's PipeWire WebRTC echo canceller:

```text
KAYLA_REALTIME_HALF_DUPLEX=false
KAYLA_REALTIME_ECHO_CANCEL=true
```

At session startup, Kayla creates temporary `kayla_echo_cancel_source` and
`kayla_echo_cancel_sink` nodes, makes them the Pulse/PipeWire defaults, then restores
the previous defaults when the session closes. If AEC cannot start, Kayla
automatically falls back to half-duplex rather than risking a feedback loop.
Headphones remain the most reliable option in a very loud room.

## Module responsibilities

### `realtime/options.py`

Holds the tool schemas Kayla exposes to the model (`look`, `set_vision`,
`see_screen`, `remember`, `recall`, `set_mode`, typing mode, feelings) and the
turn-detection timing (`vad_silence_ms`) the session configures.

### `realtime/audio.py`

`StreamingMicrophone` captures one-channel signed 16-bit PCM in 20 ms blocks at
16 kHz (Gemini Live's input rate). The async session sends those blocks without
constructing a WAV file.

`PcmPlaybackBuffer` receives model audio from the session and feeds
the sounddevice callback. The buffer also measures how much of the current answer
was handed to the speaker.

`StreamingSpeaker` requests 20 ms of sound at a time. If the session has not
provided speech yet, it outputs silence rather than blocking the audio thread.
Output audio is 24 kHz PCM (Gemini Live's output rate).

### `realtime/echo_cancel.py`

Temporarily routes the microphone and speaker through PipeWire's WebRTC AEC nodes.
This concern stays outside PCM buffering and restores the user's previous audio
defaults on shutdown.

### `realtime/gemini_session.py`

Maintains the persistent Gemini Live connection and reacts to typed events:

- `speech_started` / `user_transcript`: the user's words streaming in - the
  first word barges in on playback.
- `assistant_speaking` / `assistant_transcript`: model audio is playing, and the
  completed answer text.
- `interrupted`: Gemini stopped the response because the user spoke.
- tool calls: Kayla runs a local tool (`look`, `remember`, `set_mode`, ...) and
  returns the result, sometimes with an attached camera or screen image.
- `connected` / `error`: reconnect notices and recoverable problems.

It also owns the typing-mode state switch. The model calls `start_type_mode` once;
the session then keeps transcription active while disabling automatic AI
responses. Completed transcripts go directly to the keyboard adapter until the
local parser hears `stop typing` or another exit phrase.

### `interfaces/realtime_cli.py`

Prints connection state, listening/thinking markers, transcripts, errors, and the
AI-voice disclosure. It does not know about Base64, PCM, SDK messages, or buffers.

## Automatic turn detection

Kayla uses Gemini's automatic activity detection. It identifies speech by audio
activity and ends a turn after 450 ms of silence by default. This is a
compromise: shorter silence feels faster but may cut off a thoughtful pause;
longer silence feels patient but slower.

Tune it in `.env`:

```text
KAYLA_REALTIME_VAD_SILENCE_MS=450
```

Try `350` ms for a snappier conversation or `600` ms if Kayla interrupts pauses
too eagerly.

The model responds automatically when activity detection commits the turn -
there is no separate manual response start. Microphone audio keeps flowing while
Kayla speaks only in full-duplex mode (see the echo-cancellation options above);
in the default half-duplex mode the mic is muted during her speech, and typing
mode similarly keeps transcription alive without a model response.

## Model choice

The default is:

```text
KAYLA_GEMINI_REALTIME_MODEL=gemini-3.1-flash-live-preview
KAYLA_GEMINI_VOICE=Leda
```

Set `GEMINI_API_KEY` in `.env` (free key from
<https://aistudio.google.com/apikey>). Available voices: Puck, Charon, Kore,
Fenrir, Aoede, Leda, Orus, Zephyr. `KAYLA_GEMINI_AFFECTIVE_DIALOG=true` enables
voice-tone notes so Kayla can hear how you sound, not only what you say.

## Interruption process

When you speak during Kayla's playback:

1. In full-duplex, Gemini hears you and cancels its own response - the
   `interrupted` event fires. In half-duplex the mic is muted, so interruption
   happens only through the local controls.
2. The local PCM buffer immediately drops chunks that have not played.
3. Kayla stops lip-sync and reports "Kayla stopped to listen."

Because the model is one full-duplex session that hears your interruption
itself, its next response already reflects what you actually heard - no manual
context truncation is needed.

## Known boundaries

- Network latency still affects responsiveness.
- Realtime audio costs differ from the chained text pipeline.
- Long-term memory is reached through the `remember`/`recall` tools when Kayla
  uses them, plus automatic capture of each transcript.
- Sessions have a platform duration limit. Restart the command if a long-running
  development session closes.
