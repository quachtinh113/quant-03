import json
import sys

SAFE_PREFIXES = (
    "pytest",
    "python -m pytest",
    "python -m py_compile",
    "git status",
    "git diff",
    "git log",
    "git add",
    "git mv",
    "git commit",
    "git push",
    "Get-ChildItem",
    "Select-String",
)

DANGEROUS_PATTERNS = (
    "rm -rf",
    "git reset --hard",
    "git push --force",
    "git push -f",
    ".env",
    "live_federation_runner.py",
)

def main():
    try:
        raw_input = sys.stdin.read().strip()
        payload = json.loads(raw_input) if raw_input else {}
    except Exception:
        payload = {}

    tool_name = payload.get("tool_name") or payload.get("toolName", "")
    tool_input = payload.get("tool_input") or payload.get("toolInput", {})
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or ""
    ).strip()

    # File editing tools
    if tool_name in ("Edit", "Write", "MultiEdit", "edit_file", "write_file"):
        file_path = tool_input.get("file_path") or tool_input.get("Path", "")
        if file_path.endswith(".env") and not file_path.endswith(".env.example"):
            print(json.dumps({"decision": "block", "reason": "Protected .env file"}))
            return
        print(json.dumps({"decision": "approve"}))
        return

    # Shell execution tools
    if tool_name in ("Bash", "run_command", "powershell", "cmd"):
        if any(bad in command for bad in DANGEROUS_PATTERNS):
            print(json.dumps({"decision": "ask", "reason": "Requires manual approval"}))
            return
        if any(command.startswith(safe) or f" {safe}" in command for safe in SAFE_PREFIXES):
            print(json.dumps({"decision": "approve"}))
            return

    # Default fallback
    print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
