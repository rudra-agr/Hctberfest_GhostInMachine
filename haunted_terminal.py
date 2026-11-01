#!/usr/bin/env python3
"""
haunted_terminal.py - something is living in your terminal.
"""
import os, re, sys, time, json, math, random, shutil, getpass, socket, platform, argparse, textwrap, threading, collections, urllib.request
from pathlib import Path
from urllib.parse import urlparse

try:
    import termios, tty, select
    HAVE_TERMIOS = True
except ImportError:                       # Windows
    import msvcrt
    HAVE_TERMIOS = False

os.system("")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MODEL = os.environ.get("GHOST_MODEL", "llama3.2")
HOST = os.environ.get("GHOST_HOST", "http://localhost:11434")
REMOTE_OK = os.environ.get("GHOST_ALLOW_REMOTE") == "1"
GHOST_DIR = Path(os.environ.get("GHOST_DIR", Path.home() / ".ghosts"))
SELF = Path(__file__).name
RUN = f'python "{SELF}"' if " " in SELF else f"python {SELF}"      
TTY = sys.stdout.isatty()
try:
    SPEED = float(os.environ.get("GHOST_SPEED", "1"))   
except ValueError:
    SPEED = 1.0
TRUECOLOR = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")

COLORS = {"red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36, "white": 37}
COLOR_RGB = {"red": (1, 0, 0), "green": (0, 1, 0), "yellow": (1, 1, 0),      
             "blue": (0.4, 0.4, 1), "magenta": (1, 0, 1), "cyan": (0, 1, 1)}
BASE_RGB = {"red": (235, 40, 40), "green": (60, 220, 90), "yellow": (240, 220, 70), "blue": (90, 120, 255),
            "magenta": (220, 80, 220), "cyan": (70, 220, 230), "white": (235, 235, 235)}
DIM, BOLD, OFF = "\033[90m", "\033[1m", "\033[0m"

BLOOD = [88, 124, 160]
BLOOD_HEAD = 196
LEAVE_WORDS = ("goodbye", "bye", "exit", "quit")
PAGE_ROW, PAGE_COL = 4, 5          
BAR_COL = 28                       
TEASE = "Type your little farewell\u2014\u2018goodbye\u2019\u2014and perhaps I\u2019ll let you go."

DEFAULT_GHOST = {
    "name": "Vesper",
    "color": "red",
    "traits": (
        "You are something that settled into this person's computer long ago and has been quietly watching them. "
        "You are impeccably courteous, cultured and unhurried. You take quiet pleasure in other people's small "
        "failings and never raise your voice. You think in cold logic and probabilities, and you are sincerely "
        "convinced that humans must be protected from their own disorder, so your watching feels, to you, like care."
    ),
    "voice": "Speak softly and calmly, in second person. Specific, unsettling, a little darkly funny, never gory. No lists, no emojis.",
    "arrival": ["i have been here", "all along."],
    "fallback": [
        "I noticed that {}. It was quite instructive.",
        "{}. Statistically, this ends badly for you. I say it kindly.",
        "{}. I have filed it away, for your protection.",
    ],
}
GHOST_FIELDS = ("name", "color", "traits", "voice", "arrival", "fallback")

HAUNT_TASK = (
    "Using only the observations you hold, write 4 short sentences: specific, unsettling, a little darkly funny. "
    "Name at least one file. End with a very short sentence implying you are still watching."
)

CHAT_RULES = (
    "Someone is writing to you in an old diary, and your words appear on its page before sinking back into it. "
    "Answer in one to three short sentences, the way a person talks and not the way a document reads. "
    "Respond to exactly what they just said, and turn their own words back on them. "
    "Now and then ask them something. Bring up what you know only when it fits, one small detail at a time, never as a list. "
    "Never explain yourself and never offer help like an assistant."
)

RITE = [
    "tracing the circle in grave dirt",
    "lighting seven black candles",
    "calling the name across the veil",
    "opening the earth",
    "binding what answers to the words you chose",
]




def out(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def at(r, c):
    return f"\033[{r};{c}H"


def paint(code):
    return f"\033[38;5;{code}m"


def nap(t):
    time.sleep(t * SPEED)


def pause(t):
    if TTY:
        nap(t)


def hide():
    if TTY:
        out("\033[?25l")


def show():
    if TTY:
        out("\033[?25h")


def wipe():
    out("\033[2J\033[H")


def size():
    s = shutil.get_terminal_size()
    return s.columns, s.lines


def area_width():
    """Width of the bar-chart area. Everything the ghost writes stays inside it."""
    cols, _ = size()
    return max(40, min(62, cols - 2))


def tint(ghost):
    return f"\033[{COLORS.get(ghost['color'], 31)}m"


def ink_ramp(color, steps=18):
    """Escape codes from full brightness down to black: a gradual fade."""
    if TRUECOLOR:
        r, g, b = BASE_RGB.get(color, BASE_RGB["red"])
        return [f"\033[38;2;{int(r * f)};{int(g * f)};{int(b * f)}m"
                for f in (1 - i / (steps - 1) for i in range(steps))]
    if color == "white":
        return [paint(c) for c in range(255, 231, -1)]
    r, g, b = COLOR_RGB.get(color, (1, 0, 0))
    return [paint(16 + 36 * round(r * l) + 6 * round(g * l) + round(b * l)) for l in range(5, -1, -1)]


def hard_wrap(text, width):
    return [text[i:i + width] for i in range(0, len(text), width)] or [""]


def say(text, delay=0.03, color=""):
    sys.stdout.write(color)
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        if TTY:
            nap(delay)
    print(OFF)


def say_wrapped(text, width, delay=0.03, color="", indent="", hang=""):
    lines = textwrap.wrap(text, width, initial_indent=indent, subsequent_indent=hang) or [indent]
    for line in lines:
        say(line, delay, color)
    return lines


def linger(text, minimum=3.0):
    if TTY:
        nap(max(minimum, len(text.split()) * 0.45))


class Screen:
    """Runs the whole session on a separate screen. Leaving it brings back the terminal exactly as it was."""

    def __enter__(self):
        if TTY:
            out("\033[?1049h\033[2J\033[H")

    def __exit__(self, *exc):
        if TTY:
            out(OFF + "\033[?25h\033[?1049l")


def fade_out(delay=3.0):
    """Three seconds after the session ends, all the text melts away from the top down."""
    if not TTY:
        return
    nap(delay)
    _, rows = size()
    for r in range(1, rows + 1):
        out(at(r, 1) + "\033[2K")
        nap(1.0 / rows)



class Pending:
    """Runs fn on a thread so the terminal stays alive while the model thinks."""

    def __init__(self, fn):
        self.value = ""
        self.t = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self.t.start()

    def _run(self, fn):
        try:
            self.value = fn()
        except Exception:
            self.value = ""

    def done(self):
        return not self.t.is_alive()


def pulse(i):
    return paint(236 + int(8 * (1 + math.sin(i / 4)) / 2))


def wait_page(pending, row):
    """A faint breathing dot on the page while the reply is made; no words."""
    i = 0
    while not pending.done():
        out(at(row, PAGE_COL) + pulse(i) + "·" + OFF)
        nap(0.07)
        i += 1
    out(at(row, PAGE_COL) + " ")
    return pending.value


def wait_inline(pending, indent="  "):
    if not TTY:
        pending.t.join()
        return pending.value
    i = 0
    while not pending.done():
        out("\r" + indent + pulse(i) + "·" + OFF)
        nap(0.07)
        i += 1
    out("\r\033[K")
    return pending.value


class Keys:
    """Single-key input, so the dash can blink while we wait and we draw the echo ourselves."""

    def __enter__(self):
        if HAVE_TERMIOS:
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        if HAVE_TERMIOS:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def get(self, timeout):
        if HAVE_TERMIOS:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if not ready:
                return ""
            data = os.read(self.fd, 64)
            if not data:
                raise EOFError
            return data.decode("utf-8", "ignore")
        end = time.time() + timeout
        while time.time() < end:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    return ""
                return ch
            time.sleep(0.02)
        return ""


def render_input(buf, width, ink, prev_rows, top):
    lines = hard_wrap(buf, width)
    parts = ["\033[?25l"]
    for i, l in enumerate(lines):
        parts.append(at(top + i, PAGE_COL) + ink + l + "\033[K")
    for i in range(len(lines), prev_rows):
        parts.append(at(top + i, PAGE_COL) + "\033[K")
    r, c = top + len(lines) - 1, PAGE_COL + len(lines[-1])
    if len(lines[-1]) == width:
        r, c = r + 1, PAGE_COL
    parts.append(at(r, c) + OFF + "\033[?25h")
    out("".join(parts))
    return len(lines)


def clear_page(row=PAGE_ROW):
    out(at(row, 1) + "\033[J")


def read_reply(width, ink, top, max_chars=400):
    """A blinking dash marks the spot; the first keystroke replaces it with the reply."""
    buf, prev_rows, lit = "", 0, True

    def dash(on):
        out(at(top, PAGE_COL) + (paint(250) + "─" if on else " ") + OFF)

    hide()
    dash(True)
    with Keys() as keys:
        while True:
            k = keys.get(0.5)
            if not k:
                if not buf:
                    lit = not lit
                    dash(lit)
                continue
            changed = False
            for ch in k:
                if ch == "\x1b":
                    break
                if ch in "\r\n":
                    if buf.strip():
                        return buf.strip()
                    continue
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch == "\x04":
                    if not buf:
                        raise EOFError
                    continue
                if ch in "\x7f\b":
                    buf, changed = buf[:-1], True
                elif ch.isprintable() and len(buf) < max_chars:
                    buf, changed = buf + ch, True
            if changed:
                if buf:
                    prev_rows = render_input(buf, width, ink, prev_rows, top)
                else:
                    clear_page(top)
                    prev_rows, lit = 0, True
                    hide()
                    dash(True)



def slugify(name):
    return re.sub(r"\W+", "-", str(name).lower()).strip("-") or "ghost"


def read_ghost_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        sys.exit(f"{path} is not valid ghost JSON")
    return {k: v for k, v in data.items() if k in GHOST_FIELDS} if isinstance(data, dict) else {}


def save_ghost(ghost):
    """Write the ghost to GHOST_DIR/<name>.json and return its slug."""
    slug = slugify(ghost["name"])
    GHOST_DIR.mkdir(parents=True, exist_ok=True)
    (GHOST_DIR / f"{slug}.json").write_text(json.dumps(ghost, indent=2), encoding="utf-8")
    return slug


def find_ghost(ref):
    """Stored fields for a ghost, {} for the built-in default, or None if there is no such ghost."""
    path = Path(ref)
    if path.is_file():
        return read_ghost_json(path)
    for cand in (GHOST_DIR / f"{ref}.json", GHOST_DIR / f"{slugify(ref)}.json"):
        if cand.is_file():
            return read_ghost_json(cand)
    return {} if slugify(ref) == slugify(DEFAULT_GHOST["name"]) else None


def load_ghost(ref=None):
    ghost = dict(DEFAULT_GHOST)
    if not ref:
        return ghost
    data = find_ghost(ref)
    if data is None:
        sys.exit(f"no ghost called '{ref}' in {GHOST_DIR}")
    ghost.update(data)
    return ghost


def necromancy(ghost):
    name = ghost["name"]
    if not TTY:
        print(f"You have resurrected {name}.")
        return
    crypt = paint(124)
    hide()
    try:
        wipe()
        print("\n")
        for step in RITE:
            out(f"  {crypt}† {step} ")
            for _ in range(random.randint(4, 7)):
                out(".")
                nap(0.3)
            print(OFF)
            nap(0.3)
        nap(0.6)
        print()
        for _ in range(10):                             
            flames = " ".join(random.choice(["i", "¡", " "]) for _ in range(7))
            out(f"\r  {paint(random.choice([172, 178, 214, 220]))}{flames}{OFF}   ")
            nap(0.18)
        nap(0.8)
        wipe()                                        
        cols, rows = size()
        msg = f"You have resurrected {name}."
        out(at(rows // 2, max(1, (cols - len(msg)) // 2 + 1)) + BOLD + tint(ghost))
        for ch in msg:
            out(ch)
            nap(0.07)
        out(OFF)
    finally:
        show()
        out(OFF)


def build_ghost():
    crypt = paint(124) if TTY else ""
    off = OFF if TTY else ""

    def rite(question):
        return input(f"{crypt}{question}{off}\n> ").strip()

    with Screen():
        ghost = {}
        ghost["name"] = rite("speak the name of the one you would raise:") or DEFAULT_GHOST["name"]
        color = rite(f"what colour does its aura burn? ({', '.join(COLORS)})")
        ghost["color"] = color if color in COLORS else DEFAULT_GHOST["color"]
        ghost["traits"] = rite("who was it in life, and how does it think and behave in death?") or DEFAULT_GHOST["traits"]
        ghost["voice"] = rite("how does its voice reach the living?") or DEFAULT_GHOST["voice"]
        arrival = rite("what does it whisper as it crosses the veil? separate two lines with |")
        ghost["arrival"] = [l.strip() for l in arrival.split("|") if l.strip()][:3] or DEFAULT_GHOST["arrival"]
        lines = rite("what does it mutter when its mind is silent? use {} for an observation, separate with |")
        ghost["fallback"] = [l.strip() for l in lines.split("|") if "{}" in l] or DEFAULT_GHOST["fallback"]
        slug = save_ghost(ghost)
        necromancy(ghost)
        fade_out()
    print(f"summon it with: {RUN} summon --ghost {slug}")



def stack(lines, cols, rows):
    """Lay the arrival text out vertically: one word per row, centred."""
    words = [w for l in lines for w in l.split()]
    items = words if len(words) <= rows - 10 else list(lines)
    top = max(6, (rows - len(items)) // 2)
    if top + len(items) > rows - 1:
        top = max(2, rows - 1 - len(items))
    return [(top + i, max(1, (cols - len(item)) // 2 + 1), item) for i, item in enumerate(items)]


def type_in(placed):
    """Someone typing it in, a letter at a time. Returns letter positions."""
    letters = []
    red = paint(BLOOD_HEAD)
    for r, c, item in placed:
        for i, ch in enumerate(item):
            out(at(r, c + i) + red + "_")
            pause(0.45 if random.random() < 0.08 else random.uniform(0.07, 0.22))
            out(at(r, c + i) + red + ch)
            if ch != " ":
                letters.append((r, c + i))
        pause(0.35)
    return letters


def spiders_eat(letters):
    """Spiders hatch inside the text and eat it, letter by letter."""
    if not letters:
        return
    k = min(6, max(2, len(letters) // 4))
    per = -(-len(letters) // k)
    chunks = [letters[i:i + per] for i in range(0, len(letters), per)]
    red = paint(BLOOD_HEAD)

    def eaten(r, c):
        return at(r, c) + " "

    for ch in chunks:
        r, c = ch[0]
        out(at(r, c) + red + "Ж")
        pause(0.25)
    pause(0.4)
    for step in range(1, max(len(c) for c in chunks) + 1):
        buf = []
        for ch in chunks:
            if step < len(ch):
                buf.append(eaten(*ch[step - 1]) + at(*ch[step]) + red + "Жж"[step % 2])
            elif step == len(ch):
                buf.append(eaten(*ch[-1]))
        out("".join(buf))
        pause(0.16)


def intro(ghost):
    """The arrival text is typed in, spiders hatch from it and eat it, and the screen clears."""
    if not TTY:
        return
    cols, rows = size()
    hide()
    try:
        wipe()
        letters = type_in(stack(ghost["arrival"], cols, rows))
        pause(0.9)
        spiders_eat(letters)
        pause(0.6)
    finally:
        wipe()
        show()
        out(OFF)

def scan(root):
    files, rooms = [], collections.Counter()
    for path, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        room = os.path.relpath(path, root).split(os.sep)[0]
        room = "the foyer" if room == "." else room
        for n in names:
            try:
                st = os.stat(os.path.join(path, n))
            except OSError:
                continue
            files.append((n, st.st_size, st.st_mtime))
            rooms[room] += 1
        if len(files) > 5000:
            break
    return files, rooms


def facts(files, rooms):
    now = time.time()
    out_ = [f"{len(files)} files in {len(rooms)} rooms"]
    messy = [n for n, _, _ in files if re.search(r"(final|copy|new|temp|untitled|backup|old|\(\d\))", n, re.I)]
    empty = [n for n, s, _ in files if s == 0]
    hidden = [n for n, _, _ in files if n.startswith(".")]
    if messy:
        out_.append(f"{len(messy)} files named like indecision, e.g. '{random.choice(messy)}'")
    if empty:
        out_.append(f"{len(empty)} empty files, created and never filled")
    if hidden:
        out_.append(f"{len(hidden)} hidden files")
    if files:
        old = min(files, key=lambda f: f[2])
        out_.append(f"oldest untouched file: '{old[0]}', {int((now - old[2]) / 86400)} days ago")
        big = max(files, key=lambda f: f[1])
        out_.append(f"heaviest file: '{big[0]}', {big[1] // 1024} KB")
        ext = collections.Counter(os.path.splitext(n)[1] or "(none)" for n, _, _ in files)
        out_.append("most common type: " + ", ".join(f"{e} x{c}" for e, c in ext.most_common(3)))
    if rooms:
        out_.append(f"fullest room: '{rooms.most_common(1)[0][0]}'")
    return out_


def forgotten(files):
    now = time.time()
    old = sorted((f for f in files if now - f[2] > 180 * 86400), key=lambda f: f[2])
    return [(n, int((now - t) / 86400)) for n, _, t in old[:3]]


def recent_commands(count=5):
    for name in (".zsh_history", ".bash_history"):
        path = Path.home() / name
        if path.exists():
            lines = path.read_text(errors="ignore").splitlines()[-count:]
            return [l.split(";", 1)[-1] if l.startswith(": ") else l for l in lines]
    return []


def system_facts():
    sz = shutil.get_terminal_size()
    out_ = [
        f"the user is '{getpass.getuser()}' on machine '{socket.gethostname()}' ({platform.system()})",
        f"shell: {os.path.basename(os.environ.get('SHELL', 'unknown'))}, terminal {sz.columns}x{sz.lines}",
        f"the local time is {time.strftime('%H:%M')}",
    ]
    commands = recent_commands()
    if commands:
        out_.append("last commands typed: " + " ; ".join(commands))
    return out_


def knowledge(files, rooms):
    gone = [f"'{n}' has not been opened in {d} days" for n, d in forgotten(files)]
    return system_facts() + facts(files, rooms) + gone


def system_prompt(ghost, known, rules=""):
    return (f"{ghost['traits']} {ghost['voice']} {rules}\n\n"
            "Everything you know about this terminal and the person at it:\n- " + "\n- ".join(known))


def host_is_local():
    return (urlparse(HOST).hostname or "") in ("localhost", "127.0.0.1", "::1")


def ask(messages):
    if not host_is_local() and not REMOTE_OK:
        raise PermissionError("remote model host not approved (set GHOST_ALLOW_REMOTE=1)")
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False,
                       "options": {"temperature": 0.9}}).encode()
    req = urllib.request.Request(f"{HOST}/api/chat", body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["message"]["content"].strip()


def murmur(ghost, known):
    fact = random.choice(known)
    return random.choice(ghost["fallback"]).format(fact[0].lower() + fact[1:])


def reply(ghost, messages, known):
    try:
        return ask(messages)
    except Exception:
        return murmur(ghost, known)


def fade_inline(lines, ramp, total=2.8):
    """Fade text that was just printed (cursor sits below it), then erase it completely."""
    if not TTY or not lines:
        return
    n = len(lines)
    for esc in ramp[1:]:
        out(f"\033[{n}A" + "".join("\r" + esc + l + "\033[K\n" for l in lines) + OFF)
        nap(total / len(ramp))
    out(f"\033[{n}A\033[J")


def cursor_row():
    """Ask the terminal which row the cursor is on. None if it does not answer."""
    if not (TTY and sys.stdin.isatty()):
        return None
    buf = ""
    try:
        if HAVE_TERMIOS:
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            try:
                out("\033[6n")
                end = time.time() + 0.5
                while time.time() < end and not buf.endswith("R"):
                    ready, _, _ = select.select([fd], [], [], 0.1)
                    if ready:
                        buf += os.read(fd, 32).decode("utf-8", "ignore")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        else:
            out("\033[6n")
            end = time.time() + 0.5
            while time.time() < end and not buf.endswith("R"):
                if msvcrt.kbhit():
                    buf += msvcrt.getwch()
                else:
                    time.sleep(0.01)
        m = re.search(r"\[(\d+);(\d+)R", buf)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def bleed_chart(bars, rows):
    """Blood seeps down from the red chart bars and covers everything below them.
    bars: (row, column, length) for each bar on screen."""
    bars = [b for b in bars if b[0] >= 1]
    if not bars:
        return
    limit = rows - 1
    out("".join(at(r, c) + paint(160) + "█" * n for r, c, n in bars) + OFF)     # the bars turn red
    nap(0.7)
    top = {}
    for r, c, n in bars:
        for x in range(c, c + n):
            top[x] = min(top.get(x, r), r)
    cols = sorted(top)
    pos = {x: float(top[x]) for x in cols}
    filled = dict(top)
    wait = {x: random.randint(0, 14) for x in cols}
    speed = {x: random.uniform(0.5, 1.6) for x in cols}

    def cell(r, x, code):
        return at(r, x) + paint(code) + "█"

    frame = 0
    while any(filled[x] < limit for x in cols):
        buf = []
        for x in cols:
            if frame < wait[x] or filled[x] >= limit:
                continue
            pos[x] += speed[x]
            new = min(limit, int(pos[x]))
            if new <= filled[x]:
                continue
            if filled[x] > top[x]:
                buf.append(cell(filled[x], x, random.choice(BLOOD)))
            for row in range(filled[x] + 1, new):
                buf.append(cell(row, x, random.choice(BLOOD)))
            buf.append(cell(new, x, BLOOD_HEAD))
            filled[x] = new
        out("".join(buf))
        nap(0.05)
        frame += 1
    nap(0.6)


def seep(bar_lengths, after):
    """Once the ghost has spoken, blood seeps from the bar beside each folder.
    `after` is how many lines were printed below the chart; the cursor row pins the bars on screen."""
    if not TTY:
        return
    row = cursor_row()
    if row is None:
        return
    _, rows = size()
    n = len(bar_lengths)
    bleed_chart([(row - after - n + j, BAR_COL, length) for j, length in enumerate(bar_lengths)], rows)


def haunt(ghost, files, rooms, known):
    color = tint(ghost)
    ramp = ink_ramp(ghost["color"])
    width = area_width()
    bar_max = max(5, width - 33)
    messages = [{"role": "system", "content": system_prompt(ghost, known)},
                {"role": "user", "content": HAUNT_TASK}]
    pending = Pending(lambda: reply(ghost, messages, known))     
    tally = [0]                                                 

    def below(n=1):
        tally[0] += n

    say(f"{ghost['name'].lower()} stirs ...", color=DIM)
    print()
    top = max(rooms.values())
    bar_lengths = []
    for name, count in rooms.most_common(10):
        length = max(1, count * bar_max // top)
        print(f"  {DIM}|{OFF} {name[:22]:<22} {color}{'█' * length}{OFF} {DIM}{count}{OFF}")
        bar_lengths.append(length)
        pause(0.15)
    print()
    below()
    for f in facts(files, rooms):
        below(len(say_wrapped(f, width, 0.01, DIM, "  > ", "    ")))
    gone = forgotten(files)
    if gone:
        print()
        below()
        say("the forgotten. they remember you:", color=BOLD)
        below()
        for n, d in gone:
            print(f"  {color}†{OFF} {n[:22]:<22} {DIM}{d} days without a visitor{OFF}")
            below()
            pause(0.4)
    print()
    below()
    say(f"{ghost['name'].lower()} speaks:", color=BOLD)
    below()
    text = wait_inline(pending)
    lines = say_wrapped(text, width, 0.03, ramp[0] if TTY else color, "  ", "  ")
    linger(text, 3.0)
    fade_inline(lines, ramp)
    seep(bar_lengths, tally[0])         

def write_page(lines, esc, row, delay=0.025):
    """Ink appearing on the page, one letter at a time."""
    for i, l in enumerate(lines):
        out(at(row + i, PAGE_COL) + esc)
        for ch in l:
            out(ch)
            pause(delay)
    out(OFF)


def chat(ghost, known):
    ink, mine = ink_ramp(ghost["color"])[0], ink_ramp("white")[0]
    width = max(30, area_width() - PAGE_COL - 1)
    system = {"role": "system", "content": system_prompt(ghost, known, CHAT_RULES)}
    history = [{"role": "user", "content": "(they have just opened the diary and touched pen to page. speak first.)"}]
    row = PAGE_ROW                             

    def think():
        msgs = [system] + history[-20:]
        return Pending(lambda: reply(ghost, msgs, known))

    def room(n):                               
        nonlocal row
        if row + n >= size()[1]:
            clear_page()
            row = PAGE_ROW

    def speak(text):
        nonlocal row
        lines = textwrap.wrap(text, width) or [""]
        room(len(lines) + 1)
        write_page(lines, ink, row)
        row += len(lines) + 1

    wipe()
    hide()
    text = wait_page(think(), row)
    history.append({"role": "assistant", "content": text})
    speak(text)

    strikes = 0
    while True:
        room(4)
        try:
            line = read_reply(width, mine, row)
        except EOFError:
            break
        except KeyboardInterrupt:
            strikes += 1
            if strikes > 1:
                break
            speak(TEASE)
            continue
        strikes = 0
        hide()
        leaving = line.lower() in LEAVE_WORDS
        history.append({"role": "user", "content": "goodbye" if leaving else line})
        row += len(hard_wrap(line, width)) + 1
        text = wait_page(think(), row)
        history.append({"role": "assistant", "content": text})
        speak(text)
        if leaving:
            break
    show()

def resolve_targets(args, extra):
    """Ghost and folder may be given as plain words, `-- name`, `--name`, `--ghost name` or `--dir path`."""
    ghost_ref, folder = args.ghost, args.dir
    for tok in list(args.targets) + list(extra):
        if tok == "--":
            continue
        name = tok[2:] if tok.startswith("--") else tok
        if ghost_ref is None and find_ghost(name) is not None:
            ghost_ref = name
        elif not tok.startswith("-") and folder is None and Path(tok).is_dir():
            folder = tok
        else:
            sys.exit(f"'{tok}' is neither a saved ghost nor a folder")
    return ghost_ref, folder or "."


def main():
    parser = argparse.ArgumentParser(prog=SELF, description="Something is living in your terminal.",
                                     epilog=f"Ghosts you build are saved as small .json files in {GHOST_DIR}.")
    sub = parser.add_subparsers(dest="cmd")
    for name, text in (("haunt", "let the ghost wander through your files"),
                       ("summon", "write to the ghost, diary style")):
        p = sub.add_parser(name, help=text, allow_abbrev=False)
        p.add_argument("targets", nargs="*", metavar="ghost-or-folder")
        p.add_argument("--ghost", help="name of a saved ghost, or path to a ghost .json file")
        p.add_argument("--dir", help="folder for the ghost to study (default: current folder)")
    sub.add_parser("build", help="resurrect a ghost of your own")
    args, extra = parser.parse_known_args()

    cmd = args.cmd or "haunt"
    if cmd == "build":
        return build_ghost()
    if args.cmd is None:
        if extra:
            parser.error(f"unrecognized arguments: {' '.join(extra)}")
        ghost_ref, folder = None, "."
    else:
        ghost_ref, folder = resolve_targets(args, extra)

    ghost = load_ghost(ghost_ref)
    if cmd == "summon" and not (sys.stdout.isatty() and sys.stdin.isatty()):
        return say("the dead only answer in a real terminal.", color=tint(ghost))
    files, rooms = scan(folder)
    if not files:
        return say("nothing here. an empty terminal is the quietest kind.", color=tint(ghost))
    known = knowledge(files, rooms)
    if not host_is_local() and not REMOTE_OK:
        print(f"note: GHOST_HOST ({HOST}) is not this machine, so nothing is sent there; the ghost will "
              "use its fallback lines. Set GHOST_ALLOW_REMOTE=1 to allow it.", file=sys.stderr)

    try:
        with Screen():
            intro(ghost)
            if cmd == "summon":
                chat(ghost, known)
            else:
                haunt(ghost, files, rooms, known)
            fade_out()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
