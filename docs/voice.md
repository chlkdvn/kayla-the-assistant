# Kayla voice guide

## Why the first version is push-to-talk

There are two common voice architectures:

- Speech-to-speech sends live audio directly to one realtime model. It feels
  natural and supports interruption, but the audio connection has more moving
  parts.
- A chained pipeline performs speech-to-text, text reasoning, and text-to-speech
  as visible stages.

Kayla began with the chained pipeline because it extends the working text brain,
makes mistakes easy to locate, and lets us inspect exactly what the microphone
heard. The faster `kayla-realtime` mode now exists alongside it; this chained mode
remains the best diagnostic path when one voice stage misbehaves.

## Run it

Install the optional voice dependencies once:

```bash
uv sync --extra dev --extra voice
```

Start the interface:

```bash
uv run kayla-voice
```

Press Enter, speak, and press Enter again. The terminal prints:

1. The transcription of your recording.
2. Kayla's text response.
3. Any microphone, API, or speaker error at the stage where it occurred.

The answer is also played through the current default speaker. The program
clearly discloses that this is an AI-generated voice.

## Stage-by-stage process

### 1. Microphone recording

`SoundDeviceMicrophone` opens the operating system's default recording device.
Audio arrives in small signed 16-bit chunks at 16 kHz. When recording stops, the
chunks are joined and wrapped in a WAV header.

The WAV header describes the sample rate, number of channels, and sample width.
Without it, the transcription service would receive raw numbers without enough
information to interpret them as sound.

### 2. Speech recognition

`GroqTranscriber` uploads the in-memory WAV to the configured Groq transcription
model. It returns text such as `Hello Kayla`. The recording is not written to the
project directory.

### 3. Conversation

The transcript is passed into the same `ConversationSession` used by typed chat.
That session keeps the whole conversation as local turns, so follow-up questions
remain part of the same conversation.

### 4. Speech generation

`GroqSpeechGenerator` sends Kayla's response text and the selected voice to
Groq's speech endpoint. Replies longer than Groq's 200-character input limit are
split into chunks and the WAVs are concatenated. It asks for WAV because WAV
avoids a separate MP3 decoder and is quick to play.

### 5. Speaker playback

`SoundDeviceSpeaker` reads the WAV header, converts the audio bytes into signed
16-bit samples, and sends them to the operating system's selected output device.
It waits for playback to finish before accepting another voice turn.

## Configuration

The active values are listed in the private local `.env` file:

```text
KAYLA_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
KAYLA_SPEECH_MODEL=gpt-4o-mini-tts
KAYLA_SPEECH_VOICE=marin
KAYLA_MICROPHONE_SAMPLE_RATE=16000
KAYLA_AUDIO_INPUT_DEVICE=
KAYLA_AUDIO_OUTPUT_DEVICE=
```

The device values are blank by default, which means the operating system chooses
the microphone and speaker.

## Troubleshooting

List every audio device Python can see:

```bash
uv run python -m sounddevice
```

If Kayla hears the wrong microphone, copy its name or number into
`KAYLA_AUDIO_INPUT_DEVICE`. Do the same with `KAYLA_AUDIO_OUTPUT_DEVICE` for speakers.

If the transcription contains Kayla's own reply, use headphones or move the
speaker farther from the microphone. Automatic echo cancellation belongs to a
later realtime version.

If the program reports an API model-access error, change the relevant model in
`.env` to one available to the API project attached to your key.
