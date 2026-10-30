# Phone mode over Wi-Fi (iPhone Shortcuts bridge)

Kayla can flip your **phone's** Focus mode from the couch. Apple does not let
another computer switch Focus over the network — there is no public API — so
Kayla ships the *demand* side of that: a tiny LAN server your phone talks to,
and one Apple Shortcut on the phone that does the actual switching.

Be honest about the timing with anyone who asks: **the phone applies the
command at its next check-in**, not instantly. Kayla queues "focus on";
whenever your shortcut polls (typically every few minutes while the phone is on
the same Wi-Fi), the phone fetches it and performs it itself.

## The pieces

- `kayla/devices/bridge.py` — the server. Runs automatically with realtime
  mode (port 8711); state (pair code, device tokens, pending commands) persists
  to `KAYLA_DEVICES_PATH`, by default `kayla_devices.json`.
- The `phone_focus` tool — what Kayla calls when you say "put my phone in
  focus mode" / "turn off phone focus".
- One Apple Shortcut on the iPhone — the actuator (recipe below).

## Endpoints (plain HTTP, LAN only)

- `GET /health`                     → `{"ok": true, "name": "Kayla"}`
- `GET /pair?code=NN&name=iPhone`    → `{"ok": true, "token": "..."}` (one-time)
- `GET /commands?token=T`            → `{"commands": [...]}`, drains the queue
- `POST /ack?token=T&id=C&ok=1`      → `{"ok": true}` (mark a command done)
- `POST /notify?token=T` body `{"text": "..."}` → a one-line note Kayla stores

Every command is a small dict like `{"id": "c-7", "action": "focus_on"}`
(`focus_off` releases it). Tokens are long-lived; the pairing code is one-shot.

## One-time pairing

1. Run Kayla in realtime mode (`uv run kayla` floats the orb; the bridge starts
   with it). On startup the bridge prints its address and the current pairing
   code, something like:

   ```
   Phone bridge: http://0.0.0.0:8711 - pair your iPhone with the shortcut (code 429105); see docs/devices.md.
   ```

   The code also appears on her orb's message band. It clears after a phone
   pairs (one-shot); a fresh one appears on the next Kayla start if no phone
   has paired.
2. Make sure the phone is on the **same Wi-Fi** as the laptop.
3. On the iPhone, build a Shortcut (next section) and run it once while a
   pairing code is active. The shortcut asks for the code + laptop IP, exchanges
   both for a token, and saves the token for later runs.

## The Apple Shortcut recipe

Create one shortcut (name it whatever you like — "Kayla Phone") with this flow:

1. **Ask for Input** — question: "Laptop IP + port (e.g. `192.168.0.12:8711`)".
   Keep "Default Answer" empty; save the IP:port text into variable `Server`.
2. **Ask for Input** — question: "Pairing code (first run only)".
3. **Get Contents of URL** — `http://{Server}/pair?code={Input}&name=My%20iPhone`
   → dictionary. (First run only.)
4. **If** the pair response has `token` → **Set Variable** `Token` to it, then
   **Save File** `Token` to the iCloud Drive "Shortcuts" folder (or use
   "Append to File" once). On later runs: **Get File** `Token` / type `token.txt`
   → **Set Variable** `Token`.
5. **Get Contents of URL** — `http://{Server}/commands?token={Token}` →
   dictionary with `commands`.
6. **Repeat** with each item in `commands`:
   - **Get Dictionary Value** key `action` from the item.
   - **If** equals `focus_on` → **Set Focus** (Do Not Disturb) **turn on**
     until turned off.
   - **Otherwise If** it equals `focus_off` → **Set Focus** (Do Not Disturb)
     **turn off**.
   - **Get Contents of URL** —
     `http://{Server}/ack?token={Token}&id={item.id}&ok=1` (mark done).
7. Optional: after the loop, **Get Contents of URL** `http://{Server}/health`
   to confirm Kayla is alive before/after polling.

To avoid the two prompts annoying you on every run, keep step 1–4 inside an
**If "token file empty"** block: files made on the first run skip prompts
afterwards. Check "Allow Running Without Asking" in the shortcut's details.

Finally: **Automation** → App/Time trigger (e.g. Every 5 minutes... or "When
[phone] connects to your home Wi-Fi") that runs the shortcut silently.
iOS automations fire at their own pace — this is exactly the "next check-in"
delay Kayla tells people about.

A reverse action is also available: your shortcut can **POST /notify** with a
short note ("I left the house") which appears in Kayla's bridge notes for the
next turn.

## What Kayla does with it

Say "put my phone in focus mode" — the realtime session calls `phone_focus`
with `on`. If no phone has paired yet she says so and points here. Otherwise
the command is queued and she answers honestly, like:

> Queued focus ON for 1 paired phone; it applies the next time the phone's
> shortcut checks in.

Note that the phone bridge does not need to be reachable from phones on other
networks; it binds on all interface by default (`0.0.0.0:8711`), which is a
home-network convenience. Never port-forward it through your router.
