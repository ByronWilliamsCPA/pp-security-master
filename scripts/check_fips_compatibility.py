#!/usr/bin/env python3
"""FIPS 140-2/140-3 compatibility checker for the Security-Master codebase.

Scans Python source (and optionally tests) for cryptographic usage that is not
permitted under FIPS mode, and inspects installed distributions for crypto
libraries that are not FIPS validated.

FIPS mode restricts cryptography to NIST-approved algorithms. Common problems
this checker flags:

* Weak hash algorithms (MD5, SHA-1) used for security.
* Non-approved cipher primitives (ARC4, Blowfish, IDEA, CAST5, SEED, 3DES).
* Insecure block cipher modes (ECB).
* Deprecated TLS/SSL protocol selectors.
* The ``random`` module used where a cryptographic RNG is required.
* Dependencies that are not FIPS validated (pycrypto, pycryptodome).

The script is intentionally dependency-free (standard library only) so it can
run in any environment that has the project synced.

Usage::

    python scripts/check_fips_compatibility.py [--include-tests] [--fix-hints]
    python scripts/check_fips_compatibility.py --json

Exit code is non-zero when errors are found. With ``--strict`` warnings are
treated as errors for the purpose of the exit code.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Severity levels, ordered from most to least serious.
ERROR = "error"
WARNING = "warning"
INFO = "info"

# Hash algorithms that are not FIPS-approved for security use.
WEAK_HASHES = {
    "md5": ERROR,
    "md4": ERROR,
    "sha": ERROR,
    "sha1": WARNING,
    "ripemd160": WARNING,
}

# Cipher primitives exposed by ``cryptography.hazmat`` that FIPS disallows.
DISALLOWED_CIPHERS = {
    "ARC4": ERROR,
    "Blowfish": ERROR,
    "IDEA": ERROR,
    "CAST5": ERROR,
    "SEED": ERROR,
    "ChaCha20": WARNING,
    "TripleDES": WARNING,
}

# Block cipher modes that are not approved for general use.
DISALLOWED_MODES = {"ECB": WARNING}

# Deprecated TLS/SSL protocol selectors.
WEAK_TLS_PROTOCOLS = {
    "PROTOCOL_SSLv2": ERROR,
    "PROTOCOL_SSLv3": ERROR,
    "PROTOCOL_SSLv23": WARNING,
    "PROTOCOL_TLSv1": WARNING,
    "PROTOCOL_TLSv1_1": WARNING,
}

# Installed distributions that are not FIPS validated.
NON_FIPS_DISTRIBUTIONS = {
    "pycrypto": (ERROR, "pycrypto is unmaintained and not FIPS validated."),
    "pycryptodome": (WARNING, "pycryptodome is not a FIPS 140 validated module."),
    "pycryptodomex": (WARNING, "pycryptodomex is not a FIPS 140 validated module."),
    "m2crypto": (INFO, "m2crypto wraps OpenSSL; verify the linked provider is FIPS."),
}

# Remediation hints keyed by finding code.
FIX_HINTS = {
    "weak-hash": "Use SHA-256 or SHA-3, or pass usedforsecurity=False for non-security digests.",
    "disallowed-cipher": "Use AES (cryptography.hazmat.primitives.ciphers.algorithms.AES).",
    "disallowed-mode": "Use an authenticated mode such as GCM instead of ECB.",
    "weak-tls": "Use ssl.PROTOCOL_TLS_CLIENT/SERVER and set a minimum_version of TLS 1.2.",
    "insecure-random": "Use the 'secrets' module or os.urandom for security-sensitive values.",
    "non-fips-dependency": "Prefer 'cryptography' backed by a FIPS-validated OpenSSL provider.",
}


@dataclass
class Finding:
    """A single FIPS compatibility issue discovered during a scan."""

    severity: str
    code: str
    message: str
    file: str
    line: int
    column: int

    def hint(self) -> str:
        """Return the remediation hint for this finding.

        Returns:
            The remediation hint string, or an empty string when none exists.
        """
        return FIX_HINTS.get(self.code, "")


def _attr_name(node: ast.AST) -> str:
    """Return the trailing attribute or name of an expression node.

    Args:
        node: The expression node to inspect.

    Returns:
        The attribute or identifier name, or an empty string.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _string_value(node: ast.AST) -> str | None:
    """Return the literal string value of a node.

    Args:
        node: The node that may hold a string constant.

    Returns:
        The string value, or None when the node is not a string literal.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class FipsVisitor(ast.NodeVisitor):
    """AST visitor that records FIPS-incompatible cryptographic usage."""

    def __init__(self, relative_path: str) -> None:
        """Initialise the visitor.

        Args:
            relative_path: Repository-relative path of the file being scanned.
        """
        self.path = relative_path
        self.findings: list[Finding] = []

    def _add(self, node: ast.AST, severity: str, code: str, message: str) -> None:
        """Record a finding anchored at the given AST node.

        Args:
            node: The AST node the finding refers to.
            severity: One of ``error``, ``warning``, or ``info``.
            code: Short machine-readable finding code.
            message: Human-readable description of the issue.
        """
        self.findings.append(
            Finding(
                severity=severity,
                code=code,
                message=message,
                file=self.path,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
            ),
        )

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        """Flag imports of non-cryptographic RNG or non-FIPS modules.

        Args:
            node: The import statement node.
        """
        for alias in node.names:
            self._check_module_name(node, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        """Flag from-imports of non-cryptographic RNG or non-FIPS modules.

        Args:
            node: The from-import statement node.
        """
        if node.module:
            self._check_module_name(node, node.module)
        self.generic_visit(node)

    def _check_module_name(self, node: ast.AST, module: str) -> None:
        """Record findings for a module name referenced by an import.

        Args:
            node: The import node, used for location reporting.
            module: The dotted module name being imported.
        """
        root = module.split(".", maxsplit=1)[0]
        if root == "random":
            self._add(
                node,
                INFO,
                "insecure-random",
                "'random' is not a cryptographic RNG; verify it is not used for secrets.",
            )

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Inspect a call expression for weak hashes, ciphers, and modes.

        Args:
            node: The call expression node.
        """
        name = _attr_name(node.func)

        if name in WEAK_HASHES:
            self._check_hash_call(node, name)
        elif name == "new" and isinstance(node.func, ast.Attribute):
            self._check_hashlib_new(node)

        if name in DISALLOWED_CIPHERS:
            self._add(
                node,
                DISALLOWED_CIPHERS[name],
                "disallowed-cipher",
                f"Cipher '{name}' is not FIPS-approved.",
            )
        if name in DISALLOWED_MODES:
            self._add(
                node,
                DISALLOWED_MODES[name],
                "disallowed-mode",
                f"Cipher mode '{name}' is not FIPS-approved.",
            )

        self.generic_visit(node)

    def _check_hash_call(self, node: ast.Call, name: str) -> None:
        """Record a finding for a direct weak-hash constructor call.

        Args:
            node: The call expression node.
            name: The hash constructor name (for example ``md5``).
        """
        if _has_used_for_security_false(node):
            self._add(
                node,
                INFO,
                "weak-hash",
                f"'{name}' used with usedforsecurity=False (non-security use).",
            )
            return
        self._add(
            node,
            WEAK_HASHES[name],
            "weak-hash",
            f"Weak hash '{name}' is not FIPS-approved for security use.",
        )

    def _check_hashlib_new(self, node: ast.Call) -> None:
        """Record a finding for ``hashlib.new('md5'/'sha1', ...)`` calls.

        Args:
            node: The call expression node for ``hashlib.new``.
        """
        if not node.args:
            return
        algorithm = _string_value(node.args[0])
        if algorithm is None:
            return
        severity = WEAK_HASHES.get(algorithm.lower())
        if severity is None:
            return
        if _has_used_for_security_false(node):
            severity = INFO
        self._add(
            node,
            severity,
            "weak-hash",
            f"Weak hash '{algorithm}' requested via hashlib.new.",
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        """Flag references to deprecated TLS/SSL protocol selectors.

        Args:
            node: The attribute access node.
        """
        if node.attr in WEAK_TLS_PROTOCOLS:
            self._add(
                node,
                WEAK_TLS_PROTOCOLS[node.attr],
                "weak-tls",
                f"TLS/SSL selector '{node.attr}' is deprecated and not FIPS-safe.",
            )
        self.generic_visit(node)


def _has_used_for_security_false(node: ast.Call) -> bool:
    """Return whether a call passes ``usedforsecurity=False``.

    Args:
        node: The call expression node to inspect.

    Returns:
        True when the call explicitly sets ``usedforsecurity=False``.
    """
    for keyword in node.keywords:
        if keyword.arg == "usedforsecurity":
            value = keyword.value
            return isinstance(value, ast.Constant) and value.value is False
    return False


def scan_file(path: Path) -> list[Finding]:
    """Scan a single Python file for FIPS findings.

    Args:
        path: Filesystem path of the Python file to scan.

    Returns:
        A list of findings, empty when the file is clean or unparsable.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    visitor = FipsVisitor(str(path.relative_to(REPO_ROOT)))
    visitor.visit(tree)
    return visitor.findings


def iter_python_files(directories: list[Path]) -> list[Path]:
    """Return Python files under the given directories.

    Args:
        directories: Directories to search recursively.

    Returns:
        A sorted list of Python file paths.
    """
    files: list[Path] = []
    for directory in directories:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.py")))
    return files


def scan_dependencies() -> list[Finding]:
    """Inspect installed distributions for non-FIPS crypto libraries.

    Returns:
        A list of findings for any non-FIPS distributions that are installed.
    """
    findings: list[Finding] = []
    for dist in metadata.distributions():
        raw_name = dist.metadata["Name"]
        if not raw_name:
            continue
        name = raw_name.lower()
        if name in NON_FIPS_DISTRIBUTIONS:
            severity, message = NON_FIPS_DISTRIBUTIONS[name]
            findings.append(
                Finding(
                    severity=severity,
                    code="non-fips-dependency",
                    message=f"{raw_name}: {message}",
                    file="pyproject.toml",
                    line=0,
                    column=0,
                ),
            )
    return findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity.

    Args:
        findings: The findings to summarise.

    Returns:
        A mapping of severity level to count.
    """
    summary = {ERROR: 0, WARNING: 0, INFO: 0}
    for finding in findings:
        summary[finding.severity] = summary.get(finding.severity, 0) + 1
    return summary


def render_text(
    findings: list[Finding], summary: dict[str, int], *, fix_hints: bool
) -> str:
    """Render a human-readable report.

    Args:
        findings: The findings to render.
        summary: Severity counts for the findings.
        fix_hints: Whether to include remediation hints.

    Returns:
        The formatted text report.
    """
    lines = ["FIPS Compatibility Report", "=" * 25, ""]
    if not findings:
        lines.append("No FIPS compatibility issues detected.")
    else:
        for finding in findings:
            location = f"{finding.file}:{finding.line}:{finding.column}"
            lines.append(
                f"[{finding.severity.upper()}] {finding.code} {location} - {finding.message}",
            )
            if fix_hints and finding.hint():
                lines.append(f"    hint: {finding.hint()}")
    lines.extend(
        [
            "",
            f"Summary: {summary[ERROR]} error(s), "
            f"{summary[WARNING]} warning(s), {summary[INFO]} info.",
        ],
    )
    return "\n".join(lines)


def render_json(findings: list[Finding], summary: dict[str, int]) -> str:
    """Render a machine-readable JSON report.

    Args:
        findings: The findings to render.
        summary: Severity counts for the findings.

    Returns:
        The JSON report as a string.
    """
    payload = {
        "summary": {
            "errors": summary[ERROR],
            "warnings": summary[WARNING],
            "info": summary[INFO],
        },
        "findings": [asdict(finding) for finding in findings],
    }
    return json.dumps(payload, indent=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: The argument list to parse.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Check the codebase for FIPS compatibility."
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also scan the tests/ directory.",
    )
    parser.add_argument(
        "--fix-hints",
        action="store_true",
        help="Include remediation hints in the text report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors for the exit code.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit a JSON report instead of text.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the FIPS compatibility check.

    Args:
        argv: Optional argument list; defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` when no blocking issues are found, otherwise ``1``.
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])

    directories = [REPO_ROOT / "src"]
    if args.include_tests:
        directories.append(REPO_ROOT / "tests")

    findings: list[Finding] = []
    for path in iter_python_files(directories):
        findings.extend(scan_file(path))
    findings.extend(scan_dependencies())

    severity_rank = {ERROR: 0, WARNING: 1, INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.file, f.line))

    summary = summarize(findings)

    if args.as_json:
        print(render_json(findings, summary))
    else:
        print(render_text(findings, summary, fix_hints=args.fix_hints))

    if summary[ERROR] > 0:
        return 1
    if args.strict and summary[WARNING] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
