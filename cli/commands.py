"""
HackEmpire X — Global CLI Commands
Handles: --status, --doctor, --clean, --uninstall
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from utils.logger import Logger

_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# --status
# ---------------------------------------------------------------------------

def cmd_status(console: Console) -> int:
    """Show system and tool installation status."""
    from installer.tool_installer import TOOL_INSTALL_SPECS

    table = Table(title="Tool Status", border_style="cyan", show_lines=True)
    table.add_column("Tool", style="bold white")
    table.add_column("Binary", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Install Method", style="dim")

    for name, spec in TOOL_INSTALL_SPECS.items():
        binary = spec.post_install_bin or spec.name
        found = shutil.which(binary) is not None
        status = Text("INSTALLED", style="bold green") if found else Text("MISSING", style="bold red")
        table.add_row(name, binary, status, spec.method)

    console.print(table)

    # Python version
    v = sys.version_info
    py_ok = (v.major, v.minor) >= (3, 11)
    py_style = "bold green" if py_ok else "bold red"
    console.print(
        f"\n  Python [bold]{v.major}.{v.minor}.{v.micro}[/bold] — "
        f"[{py_style}]{'OK' if py_ok else 'REQUIRES >= 3.11'}[/{py_style}]"
    )

    # Required packages
    import importlib.util
    packages = {"rich": "rich", "requests": "requests", "flask": "flask"}
    for import_name, pip_name in packages.items():
        found_pkg = importlib.util.find_spec(import_name) is not None
        style = "bold green" if found_pkg else "bold red"
        label = "OK" if found_pkg else "MISSING — run: pip install " + pip_name
        console.print(f"  Package [bold]{pip_name}[/bold] — [{style}]{label}[/{style}]")

    console.print()
    return 0


# ---------------------------------------------------------------------------
# --doctor
# ---------------------------------------------------------------------------

def cmd_doctor(console: Console) -> int:
    """Run the Tool Doctor on all registered tools."""
    from installer.tool_installer import ToolInstaller, TOOL_INSTALL_SPECS
    from installer.tool_doctor import ToolDoctor
    from rich.table import Table

    logger = Logger(console=console)
    installer = ToolInstaller(logger=logger, mode="pro", auto_approve=False)

    # Build a synthetic tool_status from current install state
    tool_status: dict[str, str] = {}
    for name in TOOL_INSTALL_SPECS:
        tool_status[name] = "ok" if installer.check_installed(name) else "not_installed"

    doctor = ToolDoctor(logger=logger, installer=installer, mode="pro")
    reports = doctor.diagnose_and_fix(tool_status)
    summary = doctor.generate_summary(reports)

    if not reports:
        console.print(Panel("[bold green]All tools are healthy.[/bold green]", border_style="green"))
        return 0

    table = Table(title="Doctor Report", border_style="yellow", show_lines=True)
    table.add_column("Tool", style="bold white")
    table.add_column("Issue", style="bold red")
    table.add_column("Fix Attempted")
    table.add_column("Result", justify="center")
    table.add_column("Suggestion", style="dim")

    for r in reports:
        result_text = Text("FIXED", style="bold green") if r.fix_succeeded else Text("MANUAL", style="bold red")
        table.add_row(r.tool, r.issue, r.fix_attempted, result_text, r.suggestion[:60])

    console.print(table)
    console.print(
        f"\n  [bold]Total:[/bold] {summary['total_issues']}  "
        f"[bold green]Fixed:[/bold green] {summary['fixed']}  "
        f"[bold red]Manual:[/bold red] {len(summary['manual_action_required'])}\n"
    )
    return 0


# ---------------------------------------------------------------------------
# --clean
# ---------------------------------------------------------------------------

def cmd_clean(console: Console) -> int:
    """Clear log files and temporary scan state."""
    logs_dir = _ROOT / "logs"
    targets = [
        logs_dir / "hackempire.log",
        logs_dir / "scan_state.json",
        logs_dir / "scan_state.tmp",
    ]

    # Also clear __pycache__ dirs
    pycache_dirs = list(_ROOT.rglob("__pycache__"))

    console.print("[bold yellow]Files to remove:[/bold yellow]")
    for t in targets:
        exists = "  [green]exists[/green]" if t.exists() else "  [dim]not found[/dim]"
        console.print(f"  {t.relative_to(_ROOT)}{exists}")
    console.print(f"  __pycache__ directories: {len(pycache_dirs)}")

    try:
        answer = input("\nProceed with clean? (y/n): ").strip().lower()
    except (EOFError, OSError):
        answer = "n"

    if answer not in ("y", "yes"):
        console.print("[dim]Clean cancelled.[/dim]")
        return 0

    removed = 0
    for t in targets:
        if t.exists():
            t.unlink()
            removed += 1

    for d in pycache_dirs:
        shutil.rmtree(d, ignore_errors=True)

    console.print(
        f"\n[bold green]Clean complete.[/bold green] "
        f"Removed {removed} file(s) and {len(pycache_dirs)} __pycache__ dir(s)."
    )
    return 0


# ---------------------------------------------------------------------------
# --uninstall
# ---------------------------------------------------------------------------

def cmd_uninstall(console: Console) -> int:
    """
    Fully uninstall HackEmpire X.

    Steps:
    1. Remove logs and temp files
    2. Optionally remove pip packages
    3. Optionally remove the project directory
    """
    console.print(
        Panel(
            "[bold red]HackEmpire X Uninstaller[/bold red]\n\n"
            "This will remove logs, temp files, and optionally the project directory.\n"
            "[dim]Installed system tools (nmap, nuclei, etc.) will NOT be removed.[/dim]",
            border_style="red",
        )
    )

    try:
        confirm = input("\nAre you sure you want to uninstall HackEmpire X? (yes/no): ").strip().lower()
    except (EOFError, OSError):
        console.print("[dim]Uninstall cancelled (non-interactive).[/dim]")
        return 0

    if confirm not in ("yes",):
        console.print("[dim]Uninstall cancelled.[/dim]")
        return 0

    # Step 1: clean logs
    logs_dir = _ROOT / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir, ignore_errors=True)
        console.print("[green]  Logs directory removed.[/green]")

    # Step 2: remove __pycache__
    for d in _ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    console.print("[green]  __pycache__ directories removed.[/green]")

    # Step 3: optionally remove pip packages
    try:
        remove_pkgs = input(
            "\nRemove pip packages (rich, requests, flask)? (y/n): "
        ).strip().lower()
    except (EOFError, OSError):
        remove_pkgs = "n"

    if remove_pkgs in ("y", "yes"):
        import subprocess
        for pkg in ("rich", "requests", "flask"):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", pkg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            status = "removed" if result.returncode == 0 else "not found / skipped"
            console.print(f"  pip uninstall {pkg} — {status}")

    # Step 4: optionally remove project directory
    try:
        remove_dir = input(
            f"\nRemove project directory '{_ROOT}'? (yes/no): "
        ).strip().lower()
    except (EOFError, OSError):
        remove_dir = "no"

    if remove_dir == "yes":
        try:
            shutil.rmtree(_ROOT)
            console.print(f"[bold red]  Project directory removed: {_ROOT}[/bold red]")
        except OSError as exc:
            console.print(f"[red]  Could not remove project directory: {exc}[/red]")
    else:
        console.print("[dim]  Project directory kept.[/dim]")

    console.print(
        "\n[bold green]HackEmpire X has been uninstalled.[/bold green]\n"
        "[dim]Thank you for using HackEmpire X — Made by Chandan Pandey[/dim]\n"
    )
    return 0
