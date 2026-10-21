# Kayla vision (camera)

Kayla can see through a camera during realtime conversations. It does **not** stream
video. Instead the realtime model has a `look` tool, and Kayla calls it on its own
whenever seeing would help — when you ask "what's this?", show it something, or it
needs to know what you're doing. Only at that moment is a single frame captured
and sent to the cloud; nothing is sent between looks.

## How it works

```text
You: "Kayla, what am I holding?"
  -> the model decides it needs to see and calls the look tool
  -> OpenCVCamera grabs ONE frame, downscaled + JPEG-encoded
  -> the frame rides back inside the tool's response as an attached image
  -> Kayla answers from what it sees ("looks like a Phillips screwdriver")
```

The same Gemini model that talks also sees — no separate vision model. A local
detector (YOLO/MediaPipe) would only say "person/object detected", not understand
what's happening, so it isn't used here (it could be added later purely as a cheap
"is anyone there?" trigger).

## Modules

- `vision/camera.py` — `Camera` interface and `OpenCVCamera` (opens the webcam only
  for the instant of capture, then releases it).
- `realtime/options.py` — adds the `look` tool to the session when vision is on.
- `realtime/gemini_session.py` — handles the tool call: capture → attach image →
  respond. If the camera is unavailable, Kayla is told so and just says it can't
  see.

## Configuration

```text
KAYLA_VISION_ENABLED=true   # set false to remove the look tool entirely
KAYLA_CAMERA_DEVICE=0       # webcam index (run with a different number if 0 is wrong)
KAYLA_VISION_MAX_WIDTH=768  # frames are downscaled to this width to keep them cheap
```

Install dependencies (OpenCV ships in the `voice` extra) and run:

```bash
uv sync --extra dev --extra voice
uv run kayla-realtime
```

## Notes

- Capturing a frame is a glance, not a stream: ~1 image per look, sent only when
  Kayla chooses to look.
- On a Raspberry Pi, swap `OpenCVCamera` for a `picamera2`-backed `Camera`
  implementation behind the same interface; nothing else changes.
