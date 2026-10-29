#!/usr/bin/env python3
"""Atomic heartbeat appends shared by the dispatcher and the observer (F11).

Both processes append to the same file. A long-held buffered writer opened in
mode ``w`` keeps its own offset: when the observer appends ``SURVEY running``
after the dispatcher's ``START``, the dispatcher's later terminal write lands at
the stale offset and overwrites the observer's bytes (observed as a bare
``unning`` line in the D5 heartbeat). Each record here is one ``O_APPEND``
write of complete newline-terminated text, so concurrent writers cannot
interleave or clobber.
"""
import os


def append_records(path, text, fresh=False):
    """Append complete newline-delimited records in a single O_APPEND write.

    ``fresh`` truncates first, but only for the dispatcher's initial
    header+START write. Later writers (the child, the observer) always append.
    """
    data = text if text.endswith("\n") else text + "\n"
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if fresh:
        flags |= os.O_TRUNC
    fd = os.open(path, flags, 0o644)
    try:
        payload = data.encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError(f"short write to {path}")
            view = view[written:]
    finally:
        os.close(fd)
    return data


def check_writable(path):
    """Preflight: create the parent and prove the path is append-writable.

    Opens and closes without writing so a dispatch can exit 2 before launching
    opencode (AC6) without clobbering an existing heartbeat.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.close(fd)
