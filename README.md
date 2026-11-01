# Haunted Terminal

A ghost that lives in your terminal. One file: `haunted_terminal.py`.

## You need

- Python 3 (python.org)
- Optional: [Ollama](https://ollama.com), then `ollama pull llama3.2`, for real ghost replies.
  Without it the ghost uses pre-written lines.

## Run it

Open a terminal in the folder that holds the file (Desktop, for example) and run:

**Windows - PowerShell**
```
cd $HOME\Desktop
python haunted_terminal.py haunt .
python haunted_terminal.py summon .
python haunted_terminal.py build
```

**Windows - Git Bash**
```
cd ~/Desktop
python haunted_terminal.py haunt .
python haunted_terminal.py summon .
python haunted_terminal.py build
```

**Mac and Linux**
```
cd ~/Desktop
python3 haunted_terminal.py haunt .
python3 haunted_terminal.py summon .
python3 haunted_terminal.py build
```

The `.` means "the folder I'm in". To haunt another folder, put its path instead, for example
`~/Documents` (Git Bash, Mac, Linux) or `$HOME\Documents` (PowerShell).

## What each command does

- `haunt` - the ghost looks through the folder and speaks. Blood seeps from the bars, the screen blinks, then it is back to normal.
- `summon` - chat with the ghost. Type `goodbye` to leave. The screen blinks and returns to normal.
- `build` - create your own ghost. It ends with "You have resurrected ..." and a blink.

Use a ghost you built with `summon --ghost name` (`summon name` and `summon -- name` also work).
Built ghosts are saved as small files in `~/.ghosts`. Nothing you type is saved.
