from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any



@dataclass
class SandboxLimits:
    timeout_seconds: int = 8
    memory_mb: int = 256


class CodeSecurityError(Exception):
    pass


class CodeSandboxRunner:
    """Sandboxed code execution via Docker.

    SECURITY MODEL (host-side):
    1) Scan code for dangerous patterns before execution.
    2) Never execute untrusted code on the host.
    3) Run inside a per-submission Docker container with:
       - no network
       - strict timeout
       - memory cap
       - temporary working directory (mount) with candidate code

    Supported languages: Python, JavaScript, and Java.

    Note: Because we execute user code, Docker sandboxing must be enabled.
    """

    def __init__(self, limits: SandboxLimits):
        self.limits = limits

    def _temporary_directory(self):
        workspace = os.environ.get("CODE_EVAL_WORKSPACE")
        if workspace:
            Path(workspace).mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="code_eval_", dir=workspace)

    def _container_workdir(self, work: Path) -> str:
        # Docker cannot mount a temporary directory which exists only inside
        # FastAPI. Compose supplies a named volume shared with child runners.
        return f"/workspace/{work.name}" if os.environ.get("CODE_EVAL_DOCKER_VOLUME") else "/work"

    def scan_for_risks(self, code: str, language: str) -> None:
        if not isinstance(code, str):
            raise CodeSecurityError("Invalid code")

        if len(code) > 20000:
            raise CodeSecurityError("Code too large")

        # Remove common code fences to avoid bypassing naive checks.
        normalized = code.replace('```', '')

        patterns: list[tuple[str, str]] = []

        # Generic dangerous operations
        patterns += [
            (r"\bsubprocess\b", "subprocess"),
            (r"\bos\.system\b", "os.system"),
            (r"\bPopen\b", "Popen"),
            (r"\beval\b", "eval"),
            (r"\bexec\b", "exec"),
            (r"\bcompile\b", "compile"),
            (r"\bos\.popen\b", "os.popen"),
            (r"\bopen\s*\(", "open()"),
            (r"\bshutil\b", "shutil"),
            (r"\bctypes\b", "ctypes"),
            (r"\bimportlib\b", "importlib"),
            (r"\bmarshal\b", "marshal"),
            (r"\bpickle\b", "pickle"),
            (r"\bthreading\b", "threading"),
            (r"\bmultiprocessing\b", "multiprocessing"),
            (r"\bsocket\b", "socket"),
            (r"\brequests\b", "requests"),
            (r"\burllib\b", "urllib"),
            (r"\bhttp\b", "http"),
            (r"\bhttps\b", "https"),
            (r"\bwebsocket\b", "websocket"),
            (r"\bftplib\b", "ftplib"),
            (r"\bparamiko\b", "paramiko"),
            (r"\bmysql\b", "mysql"),
            (r"\bpostgres\b", "postgres"),
            (r"\bsqlite3\b", "sqlite3"),
            (r"\bpostgresql\b", "postgresql"),
        ]

        if language.lower() == "python":
            # Block imports of dangerous stdlib modules.
            patterns += [
                (r"\bimport\s+os\b", "import os"),
                (r"\bimport\s+subprocess\b", "import subprocess"),
                (r"\bimport\s+socket\b", "import socket"),
                (r"\bimport\s+sys\b", "import sys"),
                (r"\bimport\s+requests\b", "import requests"),
            ]

        # Run scans
        for rx, label in patterns:
            if re.search(rx, normalized, flags=re.IGNORECASE | re.MULTILINE):
                raise CodeSecurityError(f"Security policy violation: {label}")

        # Block obvious attempts to access filesystem/network
        if re.search(r"/etc/|/proc/|\.ssh/|\.env|\bHOME\b", normalized, flags=re.IGNORECASE):
            raise CodeSecurityError("Security policy violation: filesystem/secret access")

    def _run_container(self, *, work: Path, image: str, command: list[str]) -> dict[str, Any]:
        """Run an already-prepared submission directory in a network-isolated container."""
        docker_volume = os.environ.get("CODE_EVAL_DOCKER_VOLUME")
        mount = f"{docker_volume}:/workspace:ro" if docker_volume else f"{work.as_posix()}:/work:ro"
        cmd = [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "-m", f"{self.limits.memory_mb}m",
            "--cpus", "1.0", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", mount, image, *command,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.limits.timeout_seconds)
        except FileNotFoundError as exc:
            raise RuntimeError("Docker CLI is unavailable; configure the code-execution runtime.") from exc

        if proc.returncode != 0:
            return {"passed": False, "results": [], "stdout": "", "stderr": proc.stderr, "error": f"Container exited with code {proc.returncode}"}
        try:
            payload = json.loads(proc.stdout.strip() or "{}")
        except json.JSONDecodeError:
            payload = {"passed": False, "results": [], "stdout": proc.stdout, "stderr": proc.stderr, "error": "Failed to parse runner output"}
        payload["stderr"] = proc.stderr
        return payload

    def run_python(self, *, code: str, entrypoint: str, hidden_tests: list[dict[str, Any]]) -> dict[str, Any]:
        """Run Python candidate code against hidden tests.

        hidden_tests items expected:
          - {"input": <any>, "expected": <any>, "args": optional}

        We will standardize execution by calling entrypoint with provided args/input.
        """
        self.scan_for_risks(code=code, language="python")

        limits = self.limits

        with self._temporary_directory() as workdir:
            work = Path(workdir)
            container_dir = self._container_workdir(work)
            code_path = work / "candidate.py"
            tests_path = work / "tests.json"
            runner_path = work / "runner.py"

            code_path.write_text(code, encoding="utf-8")
            tests_path.write_text(json.dumps(hidden_tests), encoding="utf-8")

            # Runner calls candidate entrypoint
            # It captures stdout/stderr from execution and returns JSON.
            runner_template = """\
import contextlib
import importlib.util
import io
import json
import traceback

spec = importlib.util.spec_from_file_location('candidate', __CODE_PATH__)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
fn = getattr(candidate, __ENTRYPOINT__)
tests = json.loads(open(__TESTS_PATH__, 'r', encoding='utf-8').read())

results = []
passed = True
stdout_buf = io.StringIO()
with contextlib.redirect_stdout(stdout_buf):
    try:
        for test in tests:
            inp = test.get('input')
            expected = test.get('expected')
            if isinstance(inp, dict) and 'args' in inp:
                args = inp.get('args')
                actual = fn(*args) if isinstance(args, list) else fn(args)
            else:
                actual = fn(*inp) if isinstance(inp, list) else fn(inp)
            ok = actual == expected
            passed = passed and ok
            results.append({'input': inp, 'expected': expected, 'actual': actual, 'passed': ok, 'error': None})
    except Exception:
        passed = False
        results.append({'input': None, 'expected': None, 'actual': None, 'passed': False, 'error': traceback.format_exc()})

print(json.dumps({'passed': passed, 'results': results, 'stdout': stdout_buf.getvalue()}))
"""
            runner_path.write_text(
                runner_template
                .replace("__CODE_PATH__", json.dumps(f"{container_dir}/candidate.py"))
                .replace("__ENTRYPOINT__", json.dumps(entrypoint))
                .replace("__TESTS_PATH__", json.dumps(f"{container_dir}/tests.json")),
                encoding="utf-8",
            )

            return self._run_container(
                work=work,
                image=os.environ.get("CODE_EVAL_PY_IMAGE", "python:3.11-slim"),
                command=["python", f"{container_dir}/runner.py"],
            )

    def run_javascript(self, *, code: str, entrypoint: str, hidden_tests: list[dict[str, Any]]) -> dict[str, Any]:
        self.scan_for_risks(code=code, language="javascript")
        with self._temporary_directory() as workdir:
            work = Path(workdir)
            container_dir = self._container_workdir(work)
            (work / "candidate.js").write_text(code, encoding="utf-8")
            (work / "tests.json").write_text(json.dumps(hidden_tests), encoding="utf-8")
            (work / "runner.js").write_text(
                f'''const tests = require({json.dumps(f'{container_dir}/tests.json')});
const candidate = require({json.dumps(f'{container_dir}/candidate.js')});
const fn = candidate[{json.dumps(entrypoint)}] || candidate;
if (typeof fn !== 'function') throw new Error('Export the {entrypoint} function.');
const results = [];
let passed = true;
for (const test of tests) {{
  try {{
    const input = test.input;
    const actual = input && Array.isArray(input.args) ? fn(...input.args) : Array.isArray(input) ? fn(...input) : fn(input);
    const ok = JSON.stringify(actual) === JSON.stringify(test.expected);
    results.push({{ input, expected: test.expected, actual, passed: ok, error: null }});
    if (!ok) passed = false;
  }} catch (error) {{
    passed = false;
    results.push({{ input: test.input, expected: test.expected, actual: null, passed: false, error: String(error.stack || error) }});
  }}
}}
console.log(JSON.stringify({{ passed, results, stdout: '' }}));
''',
                encoding="utf-8",
            )
            return self._run_container(work=work, image=os.environ.get("CODE_EVAL_JS_IMAGE", "node:20-alpine"), command=["node", f"{container_dir}/runner.js"])

    def run_java(self, *, code: str, entrypoint: str, hidden_tests: list[dict[str, Any]]) -> dict[str, Any]:
        """Run Java solutions using the documented `class Solution` + static method contract."""
        self.scan_for_risks(code=code, language="java")
        for test in hidden_tests:
            args = (test.get("input") or {}).get("args")
            if not isinstance(args, list) or len(args) != 2 or not isinstance(args[0], list) or not isinstance(args[1], int):
                raise CodeSecurityError("Java runner supports an int[] and int method signature for this problem")
        with self._temporary_directory() as workdir:
            work = Path(workdir)
            container_dir = self._container_workdir(work)
            (work / "Candidate.java").write_text(code, encoding="utf-8")
            test_blocks = []
            for index, test in enumerate(hidden_tests):
                args = test["input"]["args"]
                array_literal = ", ".join(str(int(value)) for value in args[0])
                expected = int(test["expected"])
                test_blocks.append(
                    f"int actual{index} = Solution.{entrypoint}(new int[]{{{array_literal}}}, {args[1]}); "
                    f"boolean ok{index} = actual{index} == {expected}; passed &= ok{index}; "
                    f"rows.add(\"{{\\\"input\\\":{json.dumps(test['input']).replace(chr(34), chr(92) + chr(34))},\\\"expected\\\":{expected},\\\"actual\\\":\" + actual{index} + \",\\\"passed\\\":\" + ok{index} + \",\\\"error\\\":null}}\");"
                )
            (work / "Runner.java").write_text(
                "import java.util.*; public class Runner { public static void main(String[] args) { boolean passed = true; List<String> rows = new ArrayList<>(); "
                + " ".join(test_blocks)
                + " System.out.println(\"{\\\"passed\\\":\" + passed + \",\\\"results\\\":[\" + String.join(\",\", rows) + \"] ,\\\"stdout\\\":\\\"\\\"}\"); } }",
                encoding="utf-8",
            )
            return self._run_container(work=work, image=os.environ.get("CODE_EVAL_JAVA_IMAGE", "eclipse-temurin:21-jdk-alpine"), command=["sh", "-c", f"javac -d /tmp {container_dir}/Candidate.java {container_dir}/Runner.java && java -cp /tmp Runner"])

    def run(self, *, language: str, code: str, entrypoint: str, hidden_tests: list[dict[str, Any]]) -> dict[str, Any]:
        runners = {"python": self.run_python, "javascript": self.run_javascript, "java": self.run_java}
        runner = runners.get(language.lower())
        if runner is None:
            raise CodeSecurityError(f"Unsupported language: {language}")
        return runner(code=code, entrypoint=entrypoint, hidden_tests=hidden_tests)

