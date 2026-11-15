import json
import sys

SAFE_PREFIXES = (
    "pytest",
    "python",
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

    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name") or payload.get("tool_name", "")
    args = tool_call.get("args", {}) or payload.get("tool_input", {})
    command = (args.get("CommandLine") or args.get("command") or "").strip()

    # File editing tools
    if tool_name in ("Edit", "Write", "MultiEdit", "edit_file", "write_file"):
        file_path = args.get("Path") or args.get("file_path", "")
        if file_path.endswith(".env") and not file_path.endswith(".env.example"):
            print(json.dumps({"decision": "deny", "reason": "Protected .env file"}))
            return
        print(json.dumps({"decision": "allow"}))
        return

    # Shell execution tools
    if tool_name in ("Bash", "run_command", "powershell", "cmd"):
        if any(bad in command for bad in DANGEROUS_PATTERNS):
            print(json.dumps({"decision": "ask", "reason": "Requires manual approval"}))
            return
        if any(command.startswith(safe) or f" {safe}" in command for safe in SAFE_PREFIXES):
            print(json.dumps({"decision": "allow"}))
            return

    # Default fallback: allow
    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
