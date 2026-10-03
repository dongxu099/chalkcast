"""Optional macOS Keychain injection. No secret is printed or written to disk."""
import os
import subprocess
import sys


def load_keychain():
    if sys.platform != "darwin":
        raise ValueError("--keychain is macOS only. Inject keys through your process environment instead.")
    for env_name, service in [("ELEVENLABS_API_KEY", "elevenlabs_api_key"),
                              ("OPENAI_API_KEY", "openai_api_key"), ("PLANNER_API_KEY", "openrouter_api_key")]:
        if os.environ.get(env_name):
            continue
        result = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            os.environ[env_name] = result.stdout.strip()
            if env_name == "PLANNER_API_KEY":
                os.environ.setdefault("PLANNER_BASE_URL", "https://openrouter.ai/api/v1")
                os.environ.setdefault("PLANNER_MODEL", "openai/gpt-4.1-mini")
