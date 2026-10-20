# Kayla wake word ("attention gate")

## What it does

Realtime mode used to connect the microphone straight to the cloud and answer
anything it heard. The attention gate puts a tiny, always-on, **local** listener
in front of it so Kayla only engages when you address it:

- Say a **wake phrase** like **"Kayla, wake up"** (any of `KAYLA_WAKE_PHRASES_WAKE`)
  and Kayla wakes for a full conversation that stays awake.
- Say just **"Kayla"** on its own for a **quick one-off** — Kayla answers, then
  sleeps again after a short pause (`KAYLA_WAKE_QUICK_SLEEP_SECONDS`, default 15s).
- Say a **sleep phrase** like **"Kayla, at ease"** (any of `KAYLA_WAKE_PHRASES_SLEEP`)
  to send it back to sleep right away.
- If Kayla is awake but hears no speech for ~90 seconds, it sleeps on its own.

You can list several wake and sleep phrases (comma-separated) so any of them
works, and change the spoken replies with `KAYLA_WAKE_GREETING` / `KAYLA_WAKE_FAREWELL`.

While asleep, the wake-word model runs entirely on your computer and streams
**nothing** to OpenAI. There is no cloud cost and nothing to react to until you
wake it — the whole point of the gate.

```
            "Kayla, pay attention"
   ┌────────────────────────────────▶ AWAKE  (realtime conversation)
ASLEEP                                  │
   ▲                                    │
   └── "Kayla, at ease"  OR  ~90s quiet ──┘
```

## Why a separate local listener (and not the model itself)

To make the cloud model listen for a phrase, you would have to stream every
sound in the room to it continuously. That costs money on every bit of speech it
processes and means it hears everything. The local detector is a tiny model that
recognizes only your phrase, runs for free on your machine, and opens the cloud
connection **only** once it hears you. Doorman in front, expert in the back room.

The detector lives behind a `WakeWordDetector` interface
(`src/kayla/wake/contracts.py`), so backends are interchangeable. Two ship today,
selected with `KAYLA_WAKE_BACKEND`:

| Backend | Account? | Setup | Notes |
| --- | --- | --- | --- |
| **`vosk`** (default) | **None** | Download a ~50 MB model | Free and offline; any phrase works by matching the local transcript |
| `porcupine` | Free Picovoice account | Trained `.ppn` files | Very accurate, lightweight keyword spotting |

## Setup — Vosk (default, no account)

1. Download a model from <https://alphacephei.com/vosk/models> (the small English
   model `vosk-model-small-en-us` is a good start, ~50 MB) and unzip it.

2. Point `.env` at the unzipped folder:

   ```text
   KAYLA_WAKE_BACKEND=vosk
   KAYLA_WAKE_VOSK_MODEL_PATH=/absolute/path/to/vosk-model-small-en-us-0.15
   ```

3. Install dependencies and run:

   ```bash
   uv sync --extra dev --extra voice
   uv run kayla-realtime
   ```

Vosk transcribes locally and Kayla watches the transcript for "pay attention" and
"at ease" — no training, and the audio never leaves your machine.

## Setup — Porcupine (optional, very accurate)

1. Create a free account at the Picovoice Console and copy your **AccessKey**
   into `.env`, and switch the backend:

   ```text
   KAYLA_WAKE_BACKEND=porcupine
   KAYLA_WAKE_ACCESS_KEY=your-picovoice-access-key
   ```

2. In the Picovoice Console, create two custom wake phrases for the **Linux**
   platform: `Kayla pay attention` and `Kayla at ease`. Download the two `.ppn`
   files and point the env vars at them:

   ```text
   KAYLA_WAKE_KEYWORD_ATTENTION_PATH=/absolute/path/to/Kayla-pay-attention_linux.ppn
   KAYLA_WAKE_KEYWORD_AT_EASE_PATH=/absolute/path/to/Kayla-at-ease_linux.ppn
   ```

If a required value for the selected backend is missing, `kayla-realtime` stops at
startup with a clear message instead of failing mid-conversation.

## Configuration

```text
KAYLA_WAKE_ENABLED=true            # set false to run realtime without the gate
KAYLA_WAKE_BACKEND=vosk            # vosk (no account) or porcupine
KAYLA_WAKE_AUTO_SLEEP_SECONDS=90   # silence before auto-sleep; 0 disables auto-sleep
KAYLA_WAKE_GREETING=I'm listening. # spoken on wake (leave blank for silence)
KAYLA_WAKE_FAREWELL=Standing by.   # spoken on sleep
KAYLA_WAKE_SENSITIVITY=0.5         # porcupine only: 0-1, higher triggers more easily
```

## Known boundaries

- **Echo:** without acoustic echo cancellation, Kayla's own speaker could be heard
  by the wake detector. Use headphones during development, as realtime mode
  already recommends.
- **Vosk accuracy** depends on the model size. The small English model is fast
  and light; switch to a larger model from the same page if it mishears the
  phrases in a noisy room.
- **Custom `.ppn` files** generated on Picovoice's free tier may need to be
  re-downloaded periodically. If recognition stops working after a while,
  regenerate the keyword files in the Console.
- If a realtime session ends on its own (for example the platform session-length
  limit), Kayla returns to sleep on the next auto-sleep tick rather than instantly.
- The gate currently wraps realtime mode only. Push-to-talk (`kayla-voice`) is
  unchanged.
```
