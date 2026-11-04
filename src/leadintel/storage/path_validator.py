"""
Path Traversal and File Security Validator.

Validates destination file paths for exporters (Excel, CSV, JSON):
- Prevents directory traversal attacks ('..', null bytes).
- Blocks writes to system root and critical directories (/etc, /bin, /sbin, /usr, /root, /sys, /proc, /System, /Library, Windows System32, etc.).
- Blocks writes to sensitive user directories (.ssh, .gnupg, .aws, .config, shell rc files).
- Enforces allowed file extensions (.xlsx, .csv, .json).
- Canonicalizes and verifies destination paths cross-platform.
"""

from __future__ import annotations

import os
from typing import Optional

from ..services.url_validator import SecurityValidationError

# System and user directories strictly protected from export writes
BLOCKED_PATH_PREFIXES = (
    "/etc",
    "/bin",
    "/sbin",
    "/usr",
    "/root",
    "/dev",
    "/sys",
    "/proc",
    "/System",
    "/Library",
    "/private/etc",
)

BLOCKED_WINDOWS_PREFIXES = (
    "c:/windows",
    "c:/program files",
    "c:/program files (x86)",
    "c:/programdata",
    "d:/windows",
)

BLOCKED_USER_TARGETS = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".config",
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".zprofile",
    ".profile",
    "id_rsa",
    "id_ed25519",
)


def validate_safe_export_path(
    path: str,
    allowed_extensions: Optional[set[str]] = None,
) -> str:
    """
    Validate and return an absolute path for safe file exports.

    Raises SecurityValidationError or ValueError if path is invalid or attempts traversal.
    """
    if not path or not isinstance(path, str):
        raise ValueError("Export path must be a non-empty string.")

    if "\0" in path:
        raise SecurityValidationError("Null byte detected in file path.")

    # Check raw path for cross-platform Windows system paths (regardless of host OS)
    p_norm = path.replace("\\", "/").lower().strip()
    for win_prefix in BLOCKED_WINDOWS_PREFIXES:
        if p_norm == win_prefix or p_norm.startswith(win_prefix + "/"):
            raise SecurityValidationError(
                f"Export path '{path}' resolves to protected Windows system location '{win_prefix}'."
            )

    # Prevent UNC network share paths (e.g. \\server\share or //server/share)
    if p_norm.startswith("//"):
        raise SecurityValidationError("UNC network paths are not permitted for exports.")

    # Enforce allowed extension if specified
    if allowed_extensions:
        _, ext = os.path.splitext(path)
        ext_clean = ext.lower().lstrip(".")
        allowed_clean = {e.lower().lstrip(".") for e in allowed_extensions}
        if ext_clean not in allowed_clean:
            raise SecurityValidationError(
                f"Invalid file extension '{ext}'. Allowed extensions: {sorted(allowed_clean)}"
            )

    abs_path = os.path.abspath(path)
    real_path = os.path.realpath(abs_path)

    # Check blocked system path prefixes across both real_path and abs_path
    for prefix in BLOCKED_PATH_PREFIXES:
        if real_path == prefix or real_path.startswith(prefix + os.sep) or abs_path == prefix or abs_path.startswith(prefix + os.sep):
            raise SecurityValidationError(
                f"Export path '{path}' resolves to protected system directory '{prefix}'."
            )

    # Check sensitive user targets across both real_path and abs_path
    home = os.path.expanduser("~")
    for sensitive in BLOCKED_USER_TARGETS:
        sensitive_full = os.path.join(home, sensitive)
        if (
            real_path == sensitive_full
            or real_path.startswith(sensitive_full + os.sep)
            or abs_path == sensitive_full
            or abs_path.startswith(sensitive_full + os.sep)
        ):
            raise SecurityValidationError(
                f"Export path '{path}' resolves to protected user location '{sensitive}'."
            )

    return abs_path
