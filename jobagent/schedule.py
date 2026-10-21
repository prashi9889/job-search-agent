"""Run the agent automatically with the operating system's own scheduler."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

TASK_NAME = "JobSearchAgent"
LAUNCHD_LABEL = "com.jobagent.run"
CRON_MARK = "# jobagent-run"


def run_command() -> list[str]:
    return [sys.executable, "-m", "jobagent.cli", "run"]


def launchd_plist(minutes: int) -> str:
    args = "".join(f"<string>{a}</string>" for a in run_command())
    log = Path.home() / ".jobagent" / "run.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{LAUNCHD_LABEL}</string>
<key>ProgramArguments</key><array>{args}</array>
<key>StartInterval</key><integer>{minutes * 60}</integer>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>{log}</string>
<key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""


def cron_line(minutes: int) -> str:
    cmd = " ".join(run_command())
    log = Path.home() / ".jobagent" / "run.log"
    return f"*/{minutes} * * * * {cmd} >> {log} 2>&1 {CRON_MARK}"


def windows_command(minutes: int) -> list[str]:
    exe, *args = run_command()
    # pythonw runs without opening a console window every time.
    pythonw = str(Path(exe).with_name("pythonw.exe"))
    exe = pythonw if os.path.exists(pythonw) else exe
    return ["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(minutes), "/TN", TASK_NAME,
            "/TR", subprocess.list2cmdline([exe, *args])]


def install(minutes: int = 30) -> str:
    system = platform.system()
    if system == "Windows":
        subprocess.run(windows_command(minutes), check=True)
        return f"Windows Task Scheduler task '{TASK_NAME}' runs every {minutes} minutes."
    if system == "Darwin":
        path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(launchd_plist(minutes))
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
        subprocess.run(["launchctl", "load", str(path)], check=True)
        return f"launchd job {LAUNCHD_LABEL} runs every {minutes} minutes."
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lines = [l for l in current.splitlines() if CRON_MARK not in l] + [cron_line(minutes)]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
    return f"cron job runs every {minutes} minutes."


def remove() -> str:
    system = platform.system()
    if system == "Windows":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=True)
    elif system == "Darwin":
        path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
        path.unlink(missing_ok=True)
    else:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        lines = [l for l in current.splitlines() if CRON_MARK not in l]
        subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
    return "Automatic runs removed."
