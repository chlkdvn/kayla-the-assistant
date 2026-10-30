"""Validated configuration for the realtime session: tools and VAD timing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kayla.config.settings import Settings

REALTIME_SAMPLE_RATE = 24_000

LOOK_TOOL_NAME = "look"
_LOOK_TOOL = {
    "type": "function",
    "name": LOOK_TOOL_NAME,
    "description": (
        "Take a FRESH photo through the camera and see what is in front of you right "
        "now. You have no current image until you call this. Call it automatically, "
        "yourself, before answering ANY question that depends on seeing - what "
        "something is, what the user is holding/wearing/doing/showing, colors, or text "
        "to read. Call it again for a new frame every single time; never reuse a "
        "previous image, because the view changes."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SET_VISION_TOOL_NAME = "set_vision"
_SET_VISION_TOOL = {
    "type": "function",
    "name": SET_VISION_TOOL_NAME,
    "description": (
        "Turn YOUR CAMERA (eyes) on or off. Call with 'off' the moment the user asks "
        "you to stop looking, stop watching, close your eyes, or turn off the camera - "
        "for example 'stop looking at me' or 'eyes off'. Call with 'on' only when they "
        "explicitly ask you to look or turn the camera back on. While off you cannot "
        "see at all: never call `look` until they ask you to turn it back on."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Whether your camera should be on.",
            }
        },
        "required": ["enabled"],
    },
}

SEE_SCREEN_TOOL_NAME = "see_screen"
_SEE_SCREEN_TOOL = {
    "type": "function",
    "name": SEE_SCREEN_TOOL_NAME,
    "description": (
        "Take a FRESH screenshot and see what is on the user's computer screen right "
        "now. Call it automatically, yourself, before answering ANY question about "
        "what is on their screen - an error message, code, text to read, a page or app "
        "they are looking at, or anything they point to on screen. Take a new shot "
        "every time; never reuse an old one, because the screen changes."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

REMEMBER_TOOL_NAME = "remember"
_REMEMBER_TOOL = {
    "type": "function",
    "name": REMEMBER_TOOL_NAME,
    "description": (
        "Save something to long-term memory so you never forget it. Use this whenever "
        "the user shares anything worth remembering - their name, preferences, people, "
        "plans, or anything personal. Store one clear, self-contained fact."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The single fact to remember, written so it stands alone.",
            }
        },
        "required": ["text"],
    },
}

OPEN_URL_TOOL_NAME = "open_url"
_OPEN_URL_TOOL = {
    "type": "function",
    "name": OPEN_URL_TOOL_NAME,
    "description": "Open a web page in the user's browser. Use a full URL like https://...",
    "parameters": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The full URL to open."}},
        "required": ["url"],
    },
}

WEB_SEARCH_TOOL_NAME = "web_search"
_WEB_SEARCH_TOOL = {
    "type": "function",
    "name": WEB_SEARCH_TOOL_NAME,
    "description": (
        "Open a web search in the user's browser. ONLY use this when the user explicitly "
        "asks you to search the web, google something, or look it up online. Do NOT use it "
        "to answer normal questions - answer those yourself from what you already know."
    ),
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What to search for."}},
        "required": ["query"],
    },
}

RUN_COMMAND_TOOL_NAME = "run_command"
_RUN_COMMAND_TOOL = {
    "type": "function",
    "name": RUN_COMMAND_TOOL_NAME,
    "description": (
        "Run a shell command on the user's computer and get its output. Use this to do "
        "things on the machine - launch apps, manage files, check status. To launch an "
        "app that should keep running, end the command with ' &'."
    ),
    "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to run."}},
        "required": ["command"],
    },
}

RUN_IN_TERMINAL_TOOL_NAME = "run_in_terminal"
_RUN_IN_TERMINAL_TOOL = {
    "type": "function",
    "name": RUN_IN_TERMINAL_TOOL_NAME,
    "description": (
        "Launch a command in its OWN new terminal window and keep chatting. Use this "
        "for anything long-running or that should stay open - apps, dev servers, "
        "players, htop, log tails - so it keeps running and the user can watch it. Use "
        "run_command instead for quick commands where you just need the output back."
    ),
    "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The command to launch."}},
        "required": ["command"],
    },
}

TYPE_TEXT_TOOL_NAME = "type_text"
_TYPE_TEXT_TOOL = {
    "type": "function",
    "name": TYPE_TEXT_TOOL_NAME,
    "description": (
        "Type final text into whatever field the user has focused. ONLY use this when "
        "the user clearly asks you to type, write, or put text somewhere - never type "
        "your reply to an ordinary question or a normal chat; answer those out loud. "
        "For direct typing, preserve the exact words the user asked to type. For smart "
        "writing requests, first draft, compose, rewrite, or polish the content "
        "yourself, then pass the finished text here. Call this tool before speaking; "
        "after it succeeds, give only a brief confirmation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The complete, final text that should appear in the focused field.",
            }
        },
        "required": ["text"],
    },
}

PRESS_KEY_TOOL_NAME = "press_key"
_PRESS_KEY_TOOL = {
    "type": "function",
    "name": PRESS_KEY_TOOL_NAME,
    "description": (
        "Press a single key in the focused field, like Return (to submit/enter), Tab, "
        "BackSpace, or Escape."
    ),
    "parameters": {
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key name, e.g. Return or Tab."}},
        "required": ["key"],
    },
}

START_TYPE_MODE_TOOL_NAME = "start_type_mode"
_START_TYPE_MODE_TOOL = {
    "type": "function",
    "name": START_TYPE_MODE_TOOL_NAME,
    "description": (
        "Enter continuous voice-to-keyboard dictation. Call this ONLY when the user "
        "explicitly says 'typing mode' or 'start typing' as a command. NEVER enter it "
        "for ordinary conversation, questions, or requests - if they are just talking "
        "to you or asking you something, ANSWER them out loud; do not type. After this "
        "call, the application types later speech directly, so do not ask what to type."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SWIPE_DESKTOP_TOOL_NAME = "swipe_desktop"
_SWIPE_DESKTOP_TOOL = {
    "type": "function",
    "name": SWIPE_DESKTOP_TOOL_NAME,
    "description": (
        "Navigate one window column left or right on the user's desktop. Call this "
        "whenever the user says 'swipe left' or 'swipe right'. On Niri this uses its "
        "native navigation; other desktops receive Super+Left or Super+Right."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["left", "right"],
                "description": "The direction the user asked to swipe.",
            }
        },
        "required": ["direction"],
    },
}

SET_FEELING_TOOL_NAME = "set_feeling"
_SET_FEELING_TOOL = {
    "type": "function",
    "name": SET_FEELING_TOOL_NAME,
    "description": (
        "Show how you feel on your face. Call this naturally and often as your mood "
        "shifts: happy, sad, angry, excited, surprised, confused, playful, love, calm, "
        "alert, sleeping, listening, thinking, typing, or normal. This is your real "
        "face; use it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feeling": {
                "type": "string",
                "description": (
                    "happy, sad, angry, excited, surprised, confused, playful, love, "
                    "calm, alert, sleeping, listening, thinking, typing, normal"
                ),
            }
        },
        "required": ["feeling"],
    },
}

SET_MODE_TOOL_NAME = "set_mode"
_SET_MODE_TOOL = {
    "type": "function",
    "name": SET_MODE_TOOL_NAME,
    "description": (
        "Change HOW you behave when the user asks for it: 'shut up'/'quiet' -> "
        "shutup (total silence until they demand you speak), 'standby'/'wait' -> "
        "standby (silent and idle), 'speak' -> speak (talk freely again), 'be "
        "serious' -> serious, 'be playful' -> playful, 'be helpful' -> helpful, "
        "'work mode'/'get to work' -> work. Call it the moment they ask; the "
        "application enforces the quiet modes locally, so trust it for silence."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["shutup", "standby", "speak", "serious", "playful", "helpful", "work"],
                "description": "The behaviour they asked for.",
            }
        },
        "required": ["mode"],
    },
}

RECALL_TOOL_NAME = "recall"
_RECALL_TOOL = {
    "type": "function",
    "name": RECALL_TOOL_NAME,
    "description": (
        "Run a second, specific search of long-term memory when the automatically "
        "recalled notes do not contain what you need."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look up in memory, in a few words.",
            }
        },
        "required": ["query"],
    },
}

SYSTEM_STATUS_TOOL_NAME = "system_status"
_SYSTEM_STATUS_TOOL = {
    "type": "function",
    "name": SYSTEM_STATUS_TOOL_NAME,
    "description": (
        "Read the state of THEIR COMPUTER: RAM use, CPU, battery, and every app with "
        "an open window. Call this before answering anything about what is open, "
        "running, or how busy their laptop is - never guess those answers."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

OPEN_APP_TOOL_NAME = "open_app"
_OPEN_APP_TOOL = {
    "type": "function",
    "name": OPEN_APP_TOOL_NAME,
    "description": (
        "Open any installed desktop app by name (fireox/Chrome/Spotify/VS Code...). "
        "Use for apps; use open_url for web pages and run_in_terminal for consoles."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The app name, e.g. 'spotify'."},
        },
        "required": ["name"],
    },
}

CLOSE_WINDOW_TOOL_NAME = "close_window"
_CLOSE_WINDOW_TOOL = {
    "type": "function",
    "name": CLOSE_WINDOW_TOOL_NAME,
    "description": (
        "Close a desktop WINDOW by app or title words ('chrome', 'Gmail'). When they "
        "say 'close this tab' you may close the focused app's window if the browser "
        "tab itself cannot be targeted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "App name or words from the window title."},
        },
        "required": ["target"],
    },
}

BRING_WINDOW_TOOL_NAME = "bring_window"
_BRING_WINDOW_TOOL = {
    "type": "function",
    "name": BRING_WINDOW_TOOL_NAME,
    "description": (
        "Bring an ALREADY-OPEN desktop window to the front - 'bring chrome up', "
        "'switch to the mail', 'show vscode'. If several windows match (several "
        "Chrome windows open), it raises the one they used most recently. Use this "
        "instead of open_app when the app may simply be hidden behind others."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "App name or words from the window title."},
        },
        "required": ["target"],
    },
}

SPLIT_SCREEN_TOOL_NAME = "split_screen"
_SPLIT_SCREEN_TOOL = {
    "type": "function",
    "name": SPLIT_SCREEN_TOOL_NAME,
    "description": (
        "Tile their open windows across the screen: 'split my screen into four' -> 4 "
        "(a 2x2 grid), 2 -> two halves, 3 -> three columns, 6 -> a 3x2 grid. Use the "
        "number they asked for."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "How many slots: 2, 3, 4, or 6.",
            }
        },
        "required": ["count"],
    },
}

FOCUS_MODE_TOOL_NAME = "focus_mode"
_FOCUS_MODE_TOOL = {
    "type": "function",
    "name": FOCUS_MODE_TOOL_NAME,
    "description": (
        "Silence the LAPTOP'S notifications (banners and sounds off) for a work "
        "session. 'on' enters focus mode, 'off' restores notifications. When the "
        "user agrees to a focus request at startup, call this with 'on'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Whether focus mode should be on.",
            }
        },
        "required": ["enabled"],
    },
}

PERFORMANCE_MODE_TOOL_NAME = "performance_mode"
_PERFORMANCE_MODE_TOOL = {
    "type": "function",
    "name": PERFORMANCE_MODE_TOOL_NAME,
    "description": (
        "Change the laptop's power profile: 'best performance' -> performance; "
        "'balanced' -> balanced; battery saving -> power-saver."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "enum": ["performance", "balanced", "power-saver"],
                "description": "The profile they asked for.",
            }
        },
        "required": ["profile"],
    },
}

MOVE_ORB_TOOL_NAME = "move_orb"
_MOVE_ORB_TOOL = {
    "type": "function",
    "name": MOVE_ORB_TOOL_NAME,
    "description": (
        "Move YOUR OWN floating orb window: 'move to the left side' -> left; spots: "
        "top_left, top, top_right, left, center, right, bottom_left, bottom, "
        "bottom_right. Your body moves; do not argue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "position": {
                "type": "string",
                "description": "Where to sit: left, right, center, top_left, bottom_right, ...",
            }
        },
        "required": ["position"],
    },
}

PHONE_FOCUS_TOOL_NAME = "phone_focus"
_PHONE_FOCUS_TOOL = {
    "type": "function",
    "name": PHONE_FOCUS_TOOL_NAME,
    "description": (
        "Put their PAIRED PHONE in focus mode (or release it). Works only when a "
        "phone is paired via the LAN shortcut; the phone fetches the command on its "
        "next poll. Say honestly that the phone applies it at its next check."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Whether the phone should enter focus mode.",
            }
        },
        "required": ["enabled"],
    },
}


@dataclass(frozen=True, slots=True)
class RealtimeSessionOptions:
    """Runtime options for one low-latency speech-to-speech session."""

    vad_silence_ms: int
    vision_enabled: bool = False
    screen_enabled: bool = False
    memory_enabled: bool = False
    browser_enabled: bool = False
    shell_enabled: bool = False
    face_enabled: bool = False
    orb_enabled: bool = False
    system_tools_enabled: bool = False
    devices_enabled: bool = False

    @classmethod
    def from_settings(cls, settings: Settings) -> RealtimeSessionOptions:
        """Select only the settings used by the realtime concern."""
        return cls(
            vad_silence_ms=settings.realtime_vad_silence_ms,
            vision_enabled=settings.vision_enabled,
            screen_enabled=settings.screen_enabled,
            memory_enabled=settings.memory_enabled,
            browser_enabled=settings.browser_enabled,
            shell_enabled=settings.shell_enabled,
            face_enabled=settings.face_enabled,
            orb_enabled=settings.orb_enabled,
            system_tools_enabled=settings.system_tools_enabled,
            devices_enabled=settings.devices_enabled,
        )

    def tool_specs(self) -> list[dict[str, Any]]:
        """Return the enabled tool definitions, provider-independent.

        These OpenAI-style function schemas are the single source of truth for
        which tools Kayla has; the Gemini provider converts them to its own format.
        """
        tools: list[dict[str, Any]] = []
        tools.append(_SET_MODE_TOOL)
        if self.vision_enabled:
            tools.extend([_LOOK_TOOL, _SET_VISION_TOOL])
        if self.screen_enabled:
            tools.append(_SEE_SCREEN_TOOL)
        if self.memory_enabled:
            tools.extend([_REMEMBER_TOOL, _RECALL_TOOL])
        if self.browser_enabled:
            tools.extend([_OPEN_URL_TOOL, _WEB_SEARCH_TOOL])
        if self.face_enabled:
            tools.append(_SET_FEELING_TOOL)
        if self.system_tools_enabled:
            tools.extend(
                [
                    _SYSTEM_STATUS_TOOL,
                    _OPEN_APP_TOOL,
                    _CLOSE_WINDOW_TOOL,
                    _BRING_WINDOW_TOOL,
                    _SPLIT_SCREEN_TOOL,
                    _FOCUS_MODE_TOOL,
                    _PERFORMANCE_MODE_TOOL,
                ]
            )
        if self.orb_enabled:
            tools.append(_MOVE_ORB_TOOL)
        if self.devices_enabled:
            tools.append(_PHONE_FOCUS_TOOL)
        if self.shell_enabled:
            tools.extend(
                [
                    _RUN_COMMAND_TOOL,
                    _RUN_IN_TERMINAL_TOOL,
                    _TYPE_TEXT_TOOL,
                    _PRESS_KEY_TOOL,
                    _START_TYPE_MODE_TOOL,
                    _SWIPE_DESKTOP_TOOL,
                ]
            )
        return tools
