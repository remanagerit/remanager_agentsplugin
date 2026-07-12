"""Fail-closed local PDF boundary for the Hermes connector."""

import os
import stat
from pathlib import Path

from .client import RemanError


def _configured_values():
    return [value.strip() for value in os.environ.get("REMAN_AGENT_ALLOWED_PDF_DIRS", "").split(os.pathsep) if value.strip()]


def has_configured_pdf_roots():
    return bool(_configured_values())


def allowed_pdf_roots():
    values = _configured_values()
    if not values:
        raise RemanError("reman_pdf_roots_not_configured")
    roots = []
    for value in values:
        declared = Path(value).expanduser()
        if not declared.is_absolute():
            raise RemanError("reman_pdf_root_invalid")
        try:
            canonical = declared.resolve(strict=True)
        except OSError:
            raise RemanError("reman_pdf_root_invalid") from None
        if not canonical.is_dir():
            raise RemanError("reman_pdf_root_invalid")
        pair = (declared.absolute(), canonical)
        if pair not in roots:
            roots.append(pair)
    return roots


def _relative_to_allowed_root(raw_path, roots):
    path = Path(raw_path).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise RemanError("reman_pdf_path_denied")
    lexical = path.absolute()
    for declared, canonical in roots:
        for base in (declared, canonical):
            try:
                return canonical, lexical.relative_to(base)
            except ValueError:
                continue
    raise RemanError("reman_pdf_path_denied")


def _validate_path(root, relative):
    current = root
    parts = relative.parts
    if not parts:
        raise RemanError("reman_pdf_not_regular")
    for index, part in enumerate(parts):
        current = current / part
        try:
            details = os.lstat(current)
        except OSError:
            raise RemanError("reman_pdf_invalid_or_missing") from None
        if stat.S_ISLNK(details.st_mode):
            raise RemanError("reman_pdf_symlink_denied")
        if index < len(parts) - 1 and not stat.S_ISDIR(details.st_mode):
            raise RemanError("reman_pdf_path_denied")
    if not stat.S_ISREG(details.st_mode):
        raise RemanError("reman_pdf_not_regular")
    try:
        if current.resolve(strict=True) != current:
            raise RemanError("reman_pdf_symlink_denied")
    except OSError:
        raise RemanError("reman_pdf_invalid_or_missing") from None
    return current, details


def _same_file(left, right):
    return (
        left.st_dev,
        left.st_ino,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def read_allowed_pdf(raw_path, roots, max_bytes=None, before_open=None):
    root, relative = _relative_to_allowed_root(raw_path, roots)
    path, before = _validate_path(root, relative)
    if path.suffix.lower() != ".pdf":
        raise RemanError("reman_pdf_invalid_or_missing")
    if before.st_size <= 0 or (max_bytes is not None and before.st_size > max_bytes):
        raise RemanError("reman_pdf_exceeds_grant_limit")
    if before_open:
        before_open(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise RemanError("reman_pdf_changed_during_read") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise RemanError("reman_pdf_changed_during_read")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError:
            raise RemanError("reman_pdf_changed_during_read") from None
        if not _same_file(opened, after) or not _same_file(after, path_after):
            raise RemanError("reman_pdf_changed_during_read")
        return path, b"".join(chunks), opened.st_size
    finally:
        os.close(descriptor)
