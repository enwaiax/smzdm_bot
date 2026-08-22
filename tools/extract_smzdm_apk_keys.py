#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "androguard",
#   "capstone",
#   "loguru",
#   "pyelftools",
# ]
# ///
"""Extract and verify SMZDM signing constants from a local Android APK."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from androguard.core.apk import APK
from androguard.core.dex import DEX
from capstone import CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, CS_OP_IMM, CS_OP_REG, Cs
from elftools.elf.elffile import ELFFile
from loguru import logger

NATIVE_KEY_SYMBOL_SUFFIX = "ZDMKeyUtil_getDefaultNativeKey"
NATIVE_KEY_LIBRARY = "liblib_zdm_key.so"
SK_ENCRYPT_METHOD = "Lcom/smzdm/client/base/utils/A;->h("


@dataclass
class KeyFinding:
    value: str | None
    confidence: str
    source: str | None
    evidence: list[str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def instruction_string(output: str) -> str | None:
    match = re.search(r',\s*"([^"]*)"\s*$', output)
    return match.group(1) if match else None


def key_score(value: str) -> int:
    if not 8 <= len(value) <= 128 or not value.isprintable():
        return -100

    score = 0
    score += 3 if 16 <= len(value) <= 64 else 0
    score += 2 if re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) else 0
    score += 2 if re.search(r"\d", value) else 0
    score += 2 if re.search(r"[^A-Za-z0-9]", value) else 0
    score -= 4 if value.startswith(("_Z", "Java_", "http://", "https://")) else 0
    return score


def find_sk_key(dex_entries: list[tuple[str, bytes]]) -> tuple[KeyFinding, dict[str, bool]]:
    candidates: list[tuple[int, str, str, list[str]]] = []
    algorithm = {
        "des_cipher_present": False,
        "user_id_source_present": False,
        "device_id_source_present": False,
    }
    known_helper_markers = (
        b"com/smzdm/client/base/utils/A;",
        b"com/smzdm/client/base/utils/s;",
    )
    likely_entries = [
        entry for entry in dex_entries if all(marker in entry[1] for marker in known_helper_markers)
    ]

    for dex_name, dex_data in likely_entries or dex_entries:
        dex = DEX(dex_data)
        for class_def in dex.get_classes():
            class_name = class_def.get_name()
            for method in class_def.get_methods():
                code = method.get_code()
                if code is None:
                    continue

                instructions = list(code.get_bc().get_instructions())
                outputs = [instruction.get_output() for instruction in instructions]

                if any("Ljavax/crypto/Cipher;->getInstance" in output for output in outputs):
                    strings = {
                        value
                        for output in outputs
                        if (value := instruction_string(output)) is not None
                    }
                    if "DES" in strings:
                        algorithm["des_cipher_present"] = True

                if not any(SK_ENCRYPT_METHOD in output for output in outputs):
                    continue

                algorithm["user_id_source_present"] |= any(
                    "base/data/b;->u0()" in output for output in outputs
                )
                algorithm["device_id_source_present"] |= any(
                    "base/utils/s;->r(Z)" in output for output in outputs
                )

                for output in outputs:
                    value = instruction_string(output)
                    if value is None:
                        continue
                    score = key_score(value)
                    if class_name.endswith("/base/utils/s;") and method.get_name() == "p":
                        score += 8
                    evidence = [
                        f"DEX entry: {dex_name}",
                        f"Method: {class_name}->{method.get_name()}{method.get_descriptor()}",
                        f"Calls encryption helper: {SK_ENCRYPT_METHOD}",
                    ]
                    candidates.append((score, value, dex_name, evidence))

    if not candidates:
        return (
            KeyFinding(
                value=None,
                confidence="missing",
                source=None,
                evidence=["No constant string was found at an SK encryption-helper call site."],
            ),
            algorithm,
        )

    score, value, dex_name, evidence = max(candidates, key=lambda candidate: candidate[0])
    confidence = "high" if score >= 10 and algorithm["des_cipher_present"] else "medium"
    return (
        KeyFinding(value=value, confidence=confidence, source=dex_name, evidence=evidence),
        algorithm,
    )


def virtual_address_bytes(elf: ELFFile, address: int, size: int) -> bytes | None:
    stream = elf.stream
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        start = int(segment["p_vaddr"])
        file_size = int(segment["p_filesz"])
        if start <= address and address + size <= start + file_size:
            offset = int(segment["p_offset"]) + address - start
            stream.seek(offset)
            return stream.read(size)
    return None


def read_c_string(elf: ELFFile, address: int, limit: int = 256) -> str | None:
    data = virtual_address_bytes(elf, address, limit)
    if not data:
        return None
    raw = data.split(b"\0", 1)[0]
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return value if value.isprintable() else None


def find_native_symbol(elf: ELFFile) -> Any | None:
    for section_name in (".dynsym", ".symtab"):
        section = elf.get_section_by_name(section_name)
        if section is None:
            continue
        for symbol in section.iter_symbols():
            if symbol.name.endswith(NATIVE_KEY_SYMBOL_SUFFIX):
                return symbol
    return None


def referenced_strings_from_arm64_function(
    elf: ELFFile, function_address: int, function_size: int
) -> list[tuple[int, str]]:
    code = virtual_address_bytes(elf, function_address, function_size)
    if not code:
        return []

    disassembler = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    disassembler.detail = True
    page_values: dict[str, int] = {}
    references: list[tuple[int, str]] = []

    for instruction in disassembler.disasm(code, function_address):
        operands = instruction.operands
        if (
            instruction.mnemonic == "adrp"
            and len(operands) == 2
            and operands[0].type == CS_OP_REG
            and operands[1].type == CS_OP_IMM
        ):
            register = instruction.reg_name(operands[0].reg)
            page_values[register] = int(operands[1].imm)
            continue

        if (
            instruction.mnemonic == "add"
            and len(operands) == 3
            and operands[0].type == CS_OP_REG
            and operands[1].type == CS_OP_REG
            and operands[2].type == CS_OP_IMM
        ):
            destination = instruction.reg_name(operands[0].reg)
            source = instruction.reg_name(operands[1].reg)
            if source not in page_values:
                continue
            address = page_values[source] + int(operands[2].imm)
            value = read_c_string(elf, address)
            if value:
                references.append((address, value))
            page_values[destination] = address

    return references


def printable_strings(data: bytes, minimum: int = 8) -> list[tuple[int, str]]:
    pattern = re.compile(rb"[\x20-\x7e]{" + str(minimum).encode() + rb",128}\x00")
    return [(match.start(), match.group()[:-1].decode("ascii")) for match in pattern.finditer(data)]


def find_sign_key(native_entries: list[tuple[str, bytes]]) -> KeyFinding:
    preferred = [
        (name, data) for name, data in native_entries if Path(name).name == NATIVE_KEY_LIBRARY
    ]
    entries = preferred or native_entries

    for entry_name, data in entries:
        elf = ELFFile(io.BytesIO(data))
        if elf["e_machine"] != "EM_AARCH64":
            continue

        symbol = find_native_symbol(elf)
        if symbol is None:
            continue

        address = int(symbol["st_value"])
        size = int(symbol["st_size"])
        references = referenced_strings_from_arm64_function(elf, address, size)
        candidates = [
            (key_score(value), value, string_address) for string_address, value in references
        ]
        if candidates:
            score, value, string_address = max(candidates, key=lambda candidate: candidate[0])
            return KeyFinding(
                value=value,
                confidence="high" if score >= 7 else "medium",
                source=entry_name,
                evidence=[
                    f"JNI symbol: {symbol.name}",
                    f"Function address: 0x{address:x}",
                    f"Referenced string address: 0x{string_address:x}",
                ],
            )

    fallback: list[tuple[int, str, str, int]] = []
    for entry_name, data in entries:
        for offset, value in printable_strings(data):
            score = key_score(value)
            if score >= 7:
                fallback.append((score, value, entry_name, offset))

    if fallback:
        _, value, entry_name, offset = max(fallback, key=lambda candidate: candidate[0])
        return KeyFinding(
            value=value,
            confidence="low",
            source=entry_name,
            evidence=[
                "JNI key getter was not traceable; selected the highest-scoring native string.",
                f"File offset: 0x{offset:x}",
            ],
        )

    return KeyFinding(
        value=None,
        confidence="missing",
        source=None,
        evidence=["No signing-key candidate was found in native libraries."],
    )


def inspect_apk(apk_path: Path) -> dict[str, Any]:
    logger.remove()
    if not apk_path.is_file():
        raise FileNotFoundError(apk_path)

    with zipfile.ZipFile(apk_path) as archive:
        names = archive.namelist()
        dex_entries = [
            (name, archive.read(name)) for name in names if re.fullmatch(r"classes\d*\.dex", name)
        ]
        native_names = [name for name in names if name.startswith("lib/") and name.endswith(".so")]
        preferred_native_names = [
            name for name in native_names if Path(name).name == NATIVE_KEY_LIBRARY
        ]
        native_entries = [
            (name, archive.read(name)) for name in preferred_native_names or native_names
        ]

    if not dex_entries:
        raise ValueError("APK contains no classes*.dex entries")

    apk = APK(str(apk_path))
    sk_key, sk_algorithm = find_sk_key(dex_entries)
    sign_key = find_sign_key(native_entries)

    return {
        "apk": {
            "path": str(apk_path),
            "sha256": sha256_file(apk_path),
            "package": apk.get_package(),
            "version_name": apk.get_androidversion_name(),
            "version_code": apk.get_androidversion_code(),
            "dex_count": len(dex_entries),
            "native_library_count": len(native_names),
        },
        "sign_key": asdict(sign_key),
        "sk_key": asdict(sk_key),
        "algorithm": {
            "sign": {
                "parameter_order": "lexicographic by key",
                "empty_values": "excluded",
                "suffix": "&key=<SIGN_KEY>",
                "normalization": "remove ASCII spaces",
                "digest": "MD5 uppercase",
            },
            "sk": {
                "plaintext": "smzdm_id + device_id",
                "cipher": "DES/ECB/PKCS5Padding",
                "encoding": "Base64",
                **sk_algorithm,
            },
        },
    }


def print_human_report(report: dict[str, Any]) -> None:
    apk = report["apk"]
    print("APK")
    print(f"  package: {apk['package']}")
    print(f"  version: {apk['version_name']} ({apk['version_code']})")
    print(f"  sha256: {apk['sha256']}")
    print(f"  dex files: {apk['dex_count']}")
    print(f"  native libraries: {apk['native_library_count']}")

    for label, key_name in (("SIGN_KEY", "sign_key"), ("SK_KEY", "sk_key")):
        finding = report[key_name]
        print(f"{label}")
        print(f"  value: {finding['value'] or '<not found>'}")
        print(f"  confidence: {finding['confidence']}")
        print(f"  source: {finding['source'] or '<not found>'}")
        for evidence in finding["evidence"]:
            print(f"  evidence: {evidence}")

    sk_algorithm = report["algorithm"]["sk"]
    print("Algorithm checks")
    print(f"  DES cipher present: {sk_algorithm['des_cipher_present']}")
    print(f"  user ID source present: {sk_algorithm['user_id_source_present']}")
    print(f"  device ID source present: {sk_algorithm['device_id_source_present']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract SMZDM SIGN_KEY and SK_KEY candidates from a local APK."
    )
    parser.add_argument("apk", type=Path, help="Path to the SMZDM APK")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = inspect_apk(args.apk.resolve())
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_report(report)

    findings_complete = all(
        report[name]["value"] and report[name]["confidence"] in {"high", "medium"}
        for name in ("sign_key", "sk_key")
    )
    return 0 if findings_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
