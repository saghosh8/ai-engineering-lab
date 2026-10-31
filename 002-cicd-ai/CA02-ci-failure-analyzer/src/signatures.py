"""The failure catalog: what each kind of CI failure looks like in a log.

Rule-based on purpose. Matching a known error string is cheap, fast and
auditable, so we do it in code and let the LLM spend its one call on the
part code cannot do: explaining *this* failure.

`weight` says how specific a category is as a root cause. A log with an
out-of-memory kill and a failed test is almost always an out-of-memory
problem that *made* the test fail, so out_of_memory outranks
test_failure. Extend the patterns for your own tools and error messages.
"""

import re
from dataclasses import dataclass
from typing import List, Pattern


@dataclass(frozen=True)
class Signature:
    category: str
    label: str
    weight: int
    hint: str
    patterns: List[Pattern]


def _p(*patterns: str) -> List[Pattern]:
    return [re.compile(p) for p in patterns]


SIGNATURES: List[Signature] = [
    Signature("disk_space", "Runner out of disk space", 9,
              "The runner or agent ran out of disk.",
              _p(r"No space left on device", r"\bENOSPC\b", r"(?i)disk quota exceeded")),
    Signature("out_of_memory", "Out of memory", 9,
              "A process was killed or crashed for lack of memory.",
              _p(r"OutOfMemoryError", r"JavaScript heap out of memory", r"(?i)\bOOMKilled\b",
                 r"Cannot allocate memory", r"\bMemoryError\b", r"exit code 137\b",
                 r"(?i)java heap space")),
    Signature("infrastructure", "Runner or agent lost", 8,
              "The machine running the job disappeared, not your code.",
              _p(r"(?i)runner has received a shutdown signal", r"(?i)hosted runner lost communication",
                 r"(?i)agent .{0,60}was lost", r"ChannelClosedException", r"(?i)node is offline",
                 r"(?i)remote call on .{0,60} failed")),
    Signature("auth_permission", "Authentication or permission error", 8,
              "Credentials are missing, expired or lack the needed access.",
              _p(r"Permission denied", r"\b40[13] (?:Forbidden|Unauthorized)\b",
                 r"Resource not accessible by integration",
                 r"denied: requested access to the resource is denied",
                 r"(?i)unauthorized: authentication required", r"(?i)authentication failed",
                 r"Host key verification failed", r"\bEACCES\b")),
    Signature("missing_config", "Missing configuration or secret", 8,
              "A required variable, secret, input or workflow setting is not set.",
              _p(r"Input required and not supplied", r"(?i)environment variable \S+ (?:is )?(?:not set|required|missing)",
                 r"(?i)missing required (?:env|environment|config|variable|parameter)",
                 r"Unable to resolve action", r"Invalid workflow file", r"(?i)could not find credentials",
                 r"(?i)\b(?:token|api[_ ]?key|secret)\b.{0,40}\b(?:is )?(?:required|not set|missing|empty)\b")),
    Signature("dependency_install", "Dependency could not be installed", 7,
              "A package or version could not be found or resolved.",
              _p(r"npm (?:ERR!|error) code (?:E404|ERESOLVE|ETARGET|E401)", r"npm (?:ERR!|error) 404",
                 r"Could not find a version that satisfies the requirement", r"No matching distribution found",
                 r"Could not resolve dependencies", r"Failed to collect dependencies", r"Could not find artifact",
                 r"failed to select a version for", r"go: .{0,100}unknown revision", r"(?i)yarn error .{0,60}not found")),
    Signature("container_build", "Container build or pull failed", 7,
              "Docker could not build, pull or push an image.",
              _p(r"failed to solve", r"executor failed running", r"docker: Error response from daemon",
                 r"manifest unknown", r"pull access denied", r"toomanyrequests", r"Error response from daemon",
                 r"COPY failed")),
    Signature("timeout", "Job or step timed out", 7,
              "Something ran longer than its time limit.",
              _p(r"exceeded the maximum execution time", r"Sending interrupt signal", r"Cancelling nested steps due to timeout",
                 r"(?i)deadline exceeded", r"(?i)\btimed out after\b", r"(?i)timeout of \d+\s?m?s exceeded")),
    Signature("network", "Network or registry problem", 6,
              "A network call failed. Often temporary, so a retry may pass.",
              _p(r"\bETIMEDOUT\b", r"\bECONNRESET\b", r"\bECONNREFUSED\b", r"Connection reset by peer",
                 r"Temporary failure in name resolution", r"Could not resolve host", r"TLS handshake timeout",
                 r"\b50[34] (?:Service Unavailable|Gateway)", r"Read timed out", r"socket hang up", r"\bEAI_AGAIN\b")),
    Signature("compile_error", "Compilation or type error", 5,
              "The code does not compile or type-check.",
              _p(r"\berror TS\d+:", r"\bSyntaxError:", r"error: cannot find symbol", r"COMPILATION ERROR",
                 r"error\[E\d+\]", r"undefined reference to", r"fatal error: .{0,80}No such file or directory",
                 r"\.go:\d+:\d+: ", r"(?i)cannot find package")),
    Signature("lint_format", "Lint or formatting check failed", 4,
              "A style or lint rule rejected the change.",
              _p(r"\d+ problems? \(\d+ errors?", r"would reformat", r"(?i)code style issues found",
                 r"\bflake8\b.{0,40}\bE\d{3}\b", r"(?i)\bruff\b.{0,40}\bfound \d+ error")),
    Signature("test_failure", "Test failure", 3,
              "One or more tests failed.",
              _p(r"\bFAIL\b", r"\bAssertionError\b", r"Tests run:.*(?:Failures|Errors): [1-9]", r"\b[1-9]\d* failed\b",
                 r"\bFAILED \S+::", r"✕", r"●.{0,100}›")),
]

BY_CATEGORY = {s.category: s for s in SIGNATURES}
CATEGORIES = [s.category for s in SIGNATURES]
