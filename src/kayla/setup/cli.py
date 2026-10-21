"""`kayla-setup`: a friendly first-run wizard that writes a working .env.

Keeps all the interactive I/O here; the configuration itself is built by the pure
`wizard.build_env_text`, so the logic is tested without touching a terminal.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

from kayla.setup.wizard import (
    FREE_GEMINI_KEY_URL,
    FREE_GROQ_KEY_URL,
    Answers,
    build_env_text,
    summary,
)

_VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
_VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{_VOSK_MODEL_NAME}.zip"


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_required(prompt: str) -> str:
    while True:
        answer = input(f"{prompt}: ").strip()
        if answer:
            return answer
        print("  (this one's needed — try again)")


def _ask_yes_no(prompt: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def _choose_audio() -> tuple[str, str]:
    """Show the available devices (if we can) and let them pick, or take defaults."""
    try:
        import sounddevice as sd

        print("\nAudio devices:")
        print(sd.query_devices())
    except Exception:  # noqa: BLE001 - listing is a nicety; defaults still work
        print("\n(Couldn't list audio devices — leave the next two blank for system defaults.)")
    print("Enter a device name or number, or leave blank for the system default.")
    return _ask("  Microphone", ""), _ask("  Speaker", "")


def _download_wake_model(models_dir: Path) -> str | None:
    """Download + unzip the Vosk wake model, returning its path (or None on failure)."""
    target = models_dir / _VOSK_MODEL_NAME
    if target.exists():
        return str(target)
    try:
        print(f"  Downloading wake model (~40 MB) from {_VOSK_MODEL_URL} ...")
        models_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(_VOSK_MODEL_URL, timeout=60) as response:  # noqa: S310
            data = response.read()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(models_dir)
        if target.exists():
            print("  Wake model ready.")
            return str(target)
        print("  Downloaded, but the model folder wasn't where expected — skipping wake.")
    except Exception as error:  # noqa: BLE001 - wake is optional; degrade to off
        print(f"  Couldn't set up the wake model ({error}); leaving wake word off.")
    return None


def _write_env(project_root: Path, text: str) -> bool:
    """Write .env, refusing to silently clobber an existing one."""
    env_path = project_root / ".env"
    if env_path.exists() and not _ask_yes_no(f"\n{env_path} already exists — overwrite it?", False):
        print("Left your existing .env untouched.")
        return False
    env_path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    project_root = Path.cwd()
    print("── Let's set up Kayla ─────────────────────────────────────────")
    print("This writes a .env file so she's ready to talk. Ctrl+C to bail anytime.\n")

    name = _ask("What should she be called?", "Kayla") or "Kayla"

    print(f"\nShe uses Google Gemini for her voice. Get a FREE key: {FREE_GEMINI_KEY_URL}")
    gemini_key = _ask_required("Paste your Gemini key")

    print("\nChat, push-to-talk voice and wake greetings run on Groq.")
    print(f"Get a FREE key: {FREE_GROQ_KEY_URL}")
    groq_key = _ask_required("Paste your Groq key")

    input_device, output_device = _choose_audio()

    wake_enabled, wake_path = False, ""
    if _ask_yes_no(
        '\nSet up the wake word ("Kayla, pay attention")? Downloads a ~40 MB model', False
    ):
        path = _download_wake_model(project_root / "models")
        wake_enabled, wake_path = (bool(path), path or "")

    screen_enabled = _ask_yes_no(
        "\nLet Kayla see your screen? (a see_screen tool; needs grim on Wayland)", False
    )

    print("\nComputer control lets Kayla run terminal commands on THIS machine.")
    shell_enabled = _ask_yes_no("Enable it? (leave off unless you trust this setup)", False)

    face_enabled = _ask_yes_no("\nShow her animated on-screen face?", True)

    answers = Answers(
        gemini_api_key=gemini_key,
        groq_api_key=groq_key,
        robot_name=name,
        audio_input_device=input_device,
        audio_output_device=output_device,
        wake_enabled=wake_enabled,
        wake_model_path=wake_path,
        screen_enabled=screen_enabled,
        shell_enabled=shell_enabled,
        face_enabled=face_enabled,
    )

    if not _write_env(project_root, build_env_text(answers)):
        return

    print("\n── You're set ───────────────────────────────────────────────")
    for line in summary(answers):
        print(f"  {line}")
    print(f"\n  {name} is ready. Start talking to her with:\n\n      uv run kayla-realtime\n")


if __name__ == "__main__":
    main()
