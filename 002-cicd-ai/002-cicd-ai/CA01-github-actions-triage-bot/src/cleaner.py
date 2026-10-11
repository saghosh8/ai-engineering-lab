"""Step 2 of the pipeline: turn a raw CI log into plain, safe text.

Terminals use invisible control codes. A red error is stored as
`\\x1b[31mError\\x1b[0m`, and a progress bar rewrites the same line over
and over using carriage returns. Humans never see that mess, but an LLM
does — it wastes tokens and can split a `file:line` reference in half.

Order matters: collapse carriage returns, strip ANSI, drop other control
characters, then redact secrets.
"""

import re

from src.redactor import redact

# CSI sequences (colors, cursor moves, erase-line), OSC sequences
# (window titles, hyperlinks) and the two-character escape forms.
_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]"          # CSI  ESC [ ... final-byte
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"       # OSC  ESC ] ... BEL or ST
    r"|[@-Z\\-_])"                           # Fe   ESC + one character
)
# Everything below 0x20 except tab and newline, plus DEL.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_ansi(text: str) -> str:
    """Remove ANSI color/cursor escape sequences."""
    return _ANSI.sub("", text)


def collapse_carriage_returns(text: str) -> str:
    """Keep only what a terminal would finally show on each line.

    `10%\\r55%\\r100%` is one progress bar that updated three times; the
    reader sees `100%`. CRLF line endings are normalised first so they
    are not mistaken for overwrites.
    """
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if "\r" in line:
            segments = [s for s in line.split("\r") if s]
            line = segments[-1] if segments else ""
        out.append(line)
    return "\n".join(out)


def clean_log(raw: str) -> str:
    """Raw CI log in, plain redacted text out."""
    text = collapse_carriage_returns(raw)
    text = strip_ansi(text)
    text = _CONTROL.sub("", text)
    return redact(text)
