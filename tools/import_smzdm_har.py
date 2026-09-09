#!/usr/bin/env python3
"""Import an authenticated SMZDM Cookie header from a HAR file into .env."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_COOKIE_NAMES = ("sess", "smzdm_id", "device_id")
ENV_ASSIGNMENT_PATTERN = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)(?P<name>SMZDM_COOKIE|SMZDM_SK)(?P<separator>\s*=).*$"
)


class HarImportError(RuntimeError):
    """Raised when the HAR cannot provide a usable SMZDM login."""


@dataclass(frozen=True)
class CookieCandidate:
    """One Cookie header captured from a SMZDM request."""

    value: str
    hostname: str
    cookies: dict[str, str]

    @property
    def user_id(self) -> str:
        return self.cookies.get("smzdm_id", "")

    @property
    def is_complete(self) -> bool:
        return all(self.cookies.get(name) for name in REQUIRED_COOKIE_NAMES)


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """Parse the simple name/value pairs in an HTTP Cookie header."""
    cookies: dict[str, str] = {}
    for cookie_part in cookie_header.split(";"):
        if "=" not in cookie_part:
            continue
        cookie_name, cookie_value = cookie_part.split("=", 1)
        cookie_name = cookie_name.strip()
        if cookie_name:
            cookies[cookie_name] = unquote(cookie_value.strip())
    return cookies


def is_smzdm_hostname(hostname: str) -> bool:
    """Return whether a hostname belongs to SMZDM."""
    normalized_hostname = hostname.lower().rstrip(".")
    return normalized_hostname == "smzdm.com" or normalized_hostname.endswith(".smzdm.com")


def load_har(har_path: Path) -> dict[str, object]:
    """Load and minimally validate a HAR document."""
    try:
        with har_path.open(encoding="utf-8-sig") as har_file:
            har_data = json.load(har_file)
    except FileNotFoundError as error:
        raise HarImportError(f"HAR file does not exist: {har_path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HarImportError(f"Cannot read HAR file: {error}") from error

    if not isinstance(har_data, dict):
        raise HarImportError("Invalid HAR: the top-level value must be an object")
    return har_data


def extract_candidates(har_data: dict[str, object]) -> list[CookieCandidate]:
    """Extract Cookie headers only from SMZDM request entries."""
    log = har_data.get("log")
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        raise HarImportError("Invalid HAR: log.entries is missing or is not an array")

    candidates: list[CookieCandidate] = []
    for entry in entries:
        request = entry.get("request") if isinstance(entry, dict) else None
        if not isinstance(request, dict):
            continue

        request_url = request.get("url")
        try:
            hostname = urlsplit(request_url).hostname if isinstance(request_url, str) else None
        except ValueError:
            continue
        if not hostname or not is_smzdm_hostname(hostname):
            continue

        cookie_headers = []
        headers = request.get("headers")
        if isinstance(headers, list):
            cookie_headers = [
                header.get("value")
                for header in headers
                if isinstance(header, dict)
                and str(header.get("name", "")).lower() == "cookie"
                and isinstance(header.get("value"), str)
            ]

        # Some HAR exporters omit Cookie headers but populate request.cookies.
        if not cookie_headers:
            request_cookies = request.get("cookies")
            if isinstance(request_cookies, list):
                pairs = [
                    f"{cookie['name']}={cookie['value']}"
                    for cookie in request_cookies
                    if isinstance(cookie, dict)
                    and isinstance(cookie.get("name"), str)
                    and isinstance(cookie.get("value"), str)
                ]
                if pairs:
                    cookie_headers = ["; ".join(pairs)]

        for cookie_header in cookie_headers:
            cookie_header = cookie_header.strip()
            if not cookie_header or "\n" in cookie_header or "\r" in cookie_header:
                continue
            candidates.append(
                CookieCandidate(
                    value=cookie_header,
                    hostname=hostname,
                    cookies=parse_cookie_header(cookie_header),
                )
            )

    return candidates


def select_candidate(
    candidates: list[CookieCandidate], requested_user_id: str | None = None
) -> CookieCandidate:
    """Choose the most complete, most frequently captured login Cookie."""
    authenticated = [candidate for candidate in candidates if candidate.cookies.get("sess")]
    if requested_user_id:
        authenticated = [
            candidate for candidate in authenticated if candidate.user_id == requested_user_id
        ]
        if not authenticated:
            raise HarImportError("No authenticated SMZDM Cookie matched --user-id")

    if not authenticated:
        raise HarImportError("No authenticated SMZDM Cookie header containing 'sess' was found")

    complete_user_ids = {
        candidate.user_id
        for candidate in authenticated
        if candidate.is_complete and candidate.user_id
    }
    if not requested_user_id and len(complete_user_ids) > 1:
        raise HarImportError(
            "The HAR contains multiple SMZDM accounts; rerun with --user-id to select one"
        )

    occurrence_counts = Counter(candidate.value for candidate in authenticated)
    hostname_priority = {"user-api.smzdm.com": 2, "app-api.smzdm.com": 1}

    def score(candidate: CookieCandidate) -> tuple[int, int, int, int, int]:
        required_count = sum(bool(candidate.cookies.get(name)) for name in REQUIRED_COOKIE_NAMES)
        return (
            int(candidate.is_complete),
            required_count,
            occurrence_counts[candidate.value],
            hostname_priority.get(candidate.hostname.lower(), 0),
            len(candidate.cookies),
        )

    selected = max(authenticated, key=score)
    missing_names = [name for name in REQUIRED_COOKIE_NAMES if not selected.cookies.get(name)]
    if missing_names:
        raise HarImportError(
            "The best authenticated Cookie is missing required fields: " + ", ".join(missing_names)
        )
    return selected


def quote_env_value(value: str) -> str:
    """Quote a value using the dotenv single-quoted form."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def update_env_content(existing_content: str, cookie_header: str, keep_sk: bool) -> str:
    """Update managed keys while preserving unrelated dotenv content."""
    replacements = {"SMZDM_COOKIE": quote_env_value(cookie_header)}
    if not keep_sk:
        replacements["SMZDM_SK"] = '""'

    found_names: set[str] = set()
    output_lines: list[str] = []
    for line in existing_content.splitlines(keepends=True):
        line_without_ending = line.rstrip("\r\n")
        line_ending = line[len(line_without_ending) :]
        match = ENV_ASSIGNMENT_PATTERN.match(line_without_ending)
        if not match or match.group("name") not in replacements:
            output_lines.append(line)
            continue

        variable_name = match.group("name")
        found_names.add(variable_name)
        output_lines.append(
            f"{match.group('prefix')}{variable_name}{match.group('separator')}"
            f"{replacements[variable_name]}{line_ending or os.linesep}"
        )

    if output_lines and not output_lines[-1].endswith(("\n", "\r")):
        output_lines[-1] += os.linesep
    for variable_name, value in replacements.items():
        if variable_name not in found_names:
            output_lines.append(f"{variable_name}={value}{os.linesep}")
    return "".join(output_lines)


def backup_path_for(env_path: Path) -> Path:
    """Return an unused timestamped backup path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = env_path.with_name(f"{env_path.name}.bak-{timestamp}")
    suffix = 1
    while candidate.exists():
        candidate = env_path.with_name(f"{env_path.name}.bak-{timestamp}-{suffix}")
        suffix += 1
    return candidate


def write_env_file(env_path: Path, content: str, create_backup: bool) -> Path | None:
    """Atomically write dotenv content and optionally back up the old file."""
    if env_path.is_symlink():
        raise HarImportError(f"Refusing to replace symlink: {env_path}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if env_path.exists() and create_backup:
        backup_path = backup_path_for(env_path)
        shutil.copy2(env_path, backup_path)
        backup_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=env_path.parent,
            prefix=f".{env_path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        temporary_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary_path, env_path)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise HarImportError(f"Cannot write environment file: {error}") from error

    return backup_path


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Import an authenticated SMZDM Cookie from a HAR file into .env."
    )
    parser.add_argument("har_file", type=Path, help="path to the captured HAR file")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="dotenv file to update (default: ./.env)",
    )
    parser.add_argument(
        "--user-id",
        help="select this smzdm_id when the HAR contains multiple accounts",
    )
    parser.add_argument(
        "--keep-sk",
        action="store_true",
        help="preserve the existing SMZDM_SK instead of clearing it for auto-generation",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="do not create a timestamped backup when the target file already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and select a Cookie without writing the dotenv file",
    )
    return parser


def main() -> int:
    """Run the HAR import command."""
    arguments = build_parser().parse_args()
    try:
        har_data = load_har(arguments.har_file)
        candidates = extract_candidates(har_data)
        selected = select_candidate(candidates, arguments.user_id)

        existing_content = ""
        if arguments.env_file.exists():
            existing_content = arguments.env_file.read_text(encoding="utf-8")
        updated_content = update_env_content(existing_content, selected.value, arguments.keep_sk)

        print(
            "Validated an authenticated Cookie "
            f"({len(selected.cookies)} fields; required identity fields present)."
        )
        if arguments.dry_run:
            print("Dry run only; no file was changed.")
            return 0

        backup_path = write_env_file(
            arguments.env_file,
            updated_content,
            create_backup=not arguments.no_backup,
        )
        print(f"Updated {arguments.env_file} with permissions 0600.")
        if backup_path:
            print(f"Backup: {backup_path}")
        if not arguments.keep_sk:
            print(
                "SMZDM_SK was cleared; Android generates it from Cookie identity, "
                "while iPhone does not require it."
            )
        return 0
    except (HarImportError, OSError, UnicodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
