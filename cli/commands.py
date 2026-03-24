"""
HackEmpire X — Global CLI Commands
Handles: --status, --doctor, --clean, --uninstall, scan, report,
         install-tools, terminal, config
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

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


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

_SCAN_MODES = ("recon-only", "full", "exploit", "stealth")


def cmd_scan(
    console: Console,
    target: str,
    mode: str = "full",
    ai_key: Optional[str] = None,
    web: bool = False,
    proxy: Optional[str] = None,
    resume: bool = False,
) -> int:
    """
    Run a scan against *target* with the given mode.

    Modes: recon-only, full, exploit, stealth
    """
    from utils.validator import validate_target

    if not validate_target(target):
        console.print("[bold red]Error:[/bold red] Invalid target. Provide a valid domain or IP.")
        return 2

    mode = mode.lower()
    if mode not in _SCAN_MODES:
        console.print(
            f"[bold red]Error:[/bold red] Unknown mode '{mode}'. "
            f"Choose: {', '.join(_SCAN_MODES)}"
        )
        return 2

    # ------------------------------------------------------------------
    # Exploit mode — require explicit confirmation
    # ------------------------------------------------------------------
    if mode == "exploit":
        console.print(
            Panel(
                "[bold red]WARNING: Exploit mode enabled.[/bold red]\n\n"
                "This will attempt active exploitation of discovered vulnerabilities.\n"
                "Only proceed if you have explicit written authorisation for this target.\n\n"
                "[bold yellow]Type CONFIRM to proceed:[/bold yellow]",
                border_style="red",
                title="[bold red]EXPLOIT MODE[/bold red]",
            )
        )
        try:
            answer = input("> ").strip()
        except (EOFError, OSError):
            answer = ""
        if answer != "CONFIRM":
            console.print("[dim]Exploit mode cancelled.[/dim]")
            return 1

    # ------------------------------------------------------------------
    # Stealth mode — set rate limit env vars
    # ------------------------------------------------------------------
    if mode == "stealth":
        os.environ["HACKEMPIRE_RATE_LIMIT_RPS"] = "2"
        jitter_ms = random.randint(500, 3000)
        os.environ["HACKEMPIRE_STEALTH_JITTER_MS"] = str(jitter_ms)
        console.print(
            f"[bold cyan]Stealth mode:[/bold cyan] rate limit 2 rps, "
            f"jitter {jitter_ms}ms"
        )

    if resume:
        console.print("[bold cyan]Resuming previous scan…[/bold cyan]")

    logger = Logger(console=console)

    if web:
        import threading
        try:
            from web.app import run_server
            web_thread = threading.Thread(
                target=run_server,
                kwargs={"host": "127.0.0.1", "port": 5443, "debug": False},
                daemon=True,
            )
            web_thread.start()
            logger.success("Web dashboard started → https://127.0.0.1:5443/dashboard")
        except Exception as exc:
            logger.warning(f"Web dashboard failed to start: {exc}")

    # ------------------------------------------------------------------
    # OrchestratorV2 path — full, exploit, stealth modes
    # ------------------------------------------------------------------
    if mode in ("full", "exploit", "stealth"):
        return _run_v2_scan(
            console=console,
            logger=logger,
            target=target,
            mode=mode,
            ai_key=ai_key,
            web=web,
            proxy=proxy,
        )

    # ------------------------------------------------------------------
    # Legacy path — recon-only
    # ------------------------------------------------------------------
    orchestrator_mode = "beginner"
    from cli.cli import _run_single_target
    return _run_single_target(
        console=console,
        logger=logger,
        target=target,
        mode=orchestrator_mode,
        ai_key=ai_key,
        web=web,
        proxy=proxy,
    )


def _run_v2_scan(
    *,
    console: Console,
    logger: Logger,
    target: str,
    mode: str,
    ai_key: Optional[str],
    web: bool,
    proxy: Optional[str],
) -> int:
    """Instantiate OrchestratorV2 with all subsystems and run the full 7-phase scan."""
    from core.config import Config

    try:
        config = Config(
            target=target,
            mode=mode,
            ai_key=ai_key,
            web_enabled=web,
            proxy=proxy,
        )
    except Exception as exc:
        logger.error("Failed to prepare configuration", exc=exc)
        return 1

    # ------------------------------------------------------------------
    # Instantiate subsystems — each wrapped in try/except so a broken
    # subsystem never prevents the scan from starting.
    # ------------------------------------------------------------------

    emitter = None
    try:
        from web.realtime_emitter import RealTimeEmitter
        emitter = RealTimeEmitter()
    except Exception as exc:
        logger.warning(f"[v2] RealTimeEmitter unavailable: {exc}")

    tool_manager = None
    try:
        from tools.tool_manager import ToolManager
        tool_manager = ToolManager(
            logger=logger,
            timeout_s=60.0,
            execution_mode="parallel",
            max_workers=4,
            web_scheme="https",
            proxy=proxy,
        )
    except Exception as exc:
        logger.warning(f"[v2] ToolManager unavailable: {exc}")

    phase_manager = None
    try:
        from core.phase_manager import PhaseManager
        if tool_manager is not None:
            phase_manager = PhaseManager(tool_manager=tool_manager, emitter=emitter)
    except Exception as exc:
        logger.warning(f"[v2] PhaseManager unavailable: {exc}")

    ai_engine = None
    if ai_key:
        try:
            from ai.ai_engine import AIEngine
            ai_engine = AIEngine(api_key=ai_key)
        except Exception as exc:
            logger.warning(f"[v2] AIEngine unavailable: {exc}")

    todo_planner = None
    try:
        from core.todo_planner import TodoPlanner
        todo_planner = TodoPlanner(emitter=emitter)
    except Exception as exc:
        logger.warning(f"[v2] TodoPlanner unavailable: {exc}")

    tor_manager = None
    if mode == "stealth":
        try:
            from core.tor_manager import TorManager
            tor_manager = TorManager()
        except Exception as exc:
            logger.warning(f"[v2] TorManager unavailable: {exc}")

    waf_detector = None
    try:
        from tools.waf.waf_detector import WafDetector
        waf_detector = WafDetector()
    except Exception as exc:
        logger.warning(f"[v2] WafDetector unavailable: {exc}")

    terminal_launcher = None
    try:
        from web.terminal_launcher import TerminalLauncher
        terminal_launcher = TerminalLauncher()
    except Exception as exc:
        logger.warning(f"[v2] TerminalLauncher unavailable: {exc}")

    dep_resolver = None
    try:
        from installer.dependency_resolver import DependencyResolver
        dep_resolver = DependencyResolver(logger=logger, auto_approve=True)
    except Exception as exc:
        logger.warning(f"[v2] DependencyResolver unavailable: {exc}")

    # ------------------------------------------------------------------
    # Build and run OrchestratorV2
    # ------------------------------------------------------------------
    try:
        from core.orchestrator import OrchestratorV2
        orchestrator_v2 = OrchestratorV2(
            config=config,
            logger=logger,
            emitter=emitter,
            ai_engine=ai_engine,
            phase_manager=phase_manager,
        )
    except Exception as exc:
        logger.error(f"[v2] Failed to instantiate OrchestratorV2: {exc}")
        return 1

    console.print(
        Panel(
            f"[bold cyan]Starting v2 scan: {target}[/bold cyan]  "
            f"[dim]mode={mode}[/dim]",
            border_style="cyan",
        )
    )

    try:
        final_report = orchestrator_v2.run_full_scan(target)
    except Exception as exc:
        logger.error(f"[v2] Scan failed: {exc}")
        return 1

    console.print(
        Panel(
            f"[bold green]Scan complete: {target}[/bold green]"
            + (f"  [dim]Dashboard → https://127.0.0.1:5443/dashboard[/dim]" if web else ""),
            border_style="green",
        )
    )
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

_REPORT_FORMATS = ("pdf", "json", "html", "markdown", "csv")


def cmd_report(console: Console, fmt: str = "json") -> int:
    """Export the latest scan report in the requested format."""
    fmt = fmt.lower()
    if fmt not in _REPORT_FORMATS:
        console.print(
            f"[bold red]Error:[/bold red] Unknown format '{fmt}'. "
            f"Choose: {', '.join(_REPORT_FORMATS)}"
        )
        return 2

    from web.state_bridge import read_state

    state = read_state()
    target = state.get("target") or "unknown"

    if fmt == "json":
        import json as _json
        data = state.get("data", {})
        vuln = data.get("vuln", {})
        vulns = vuln.get("vulnerabilities") or []
        report_data = {
            "target": target,
            "mode": state.get("mode"),
            "tool_health": state.get("tool_health"),
            "findings": {
                "ports": (data.get("recon") or {}).get("ports") or [],
                "subdomains": (data.get("recon") or {}).get("subdomains") or [],
                "urls": (data.get("enum") or {}).get("urls") or [],
                "vulnerabilities": vulns,
            },
        }
        out_file = Path(f"hackempire_report_{target}.json")
        out_file.write_text(_json.dumps(report_data, indent=2, default=str), encoding="utf-8")
        console.print(f"[bold green]Report saved:[/bold green] {out_file}")
        return 0

    if fmt == "html":
        from web.pdf_report import generate_html
        html = generate_html(state)
        out_file = Path(f"hackempire_report_{target}.html")
        out_file.write_text(html, encoding="utf-8")
        console.print(f"[bold green]Report saved:[/bold green] {out_file}")
        return 0

    if fmt == "pdf":
        from web.pdf_report import generate_pdf, generate_html, weasyprint_available
        out_file = Path(f"hackempire_report_{target}.pdf")
        if weasyprint_available():
            pdf_bytes = generate_pdf(state)
            if pdf_bytes:
                out_file.write_bytes(pdf_bytes)
                console.print(f"[bold green]Report saved:[/bold green] {out_file}")
                return 0
        # Fallback to HTML
        html = generate_html(state)
        html_file = out_file.with_suffix(".html")
        html_file.write_text(html, encoding="utf-8")
        console.print(
            f"[bold yellow]WeasyPrint not available — saved as HTML:[/bold yellow] {html_file}"
        )
        return 0

    if fmt == "markdown":
        from web.exporters.markdown_export import generate_markdown
        content = generate_markdown(state)
        out_file = Path(f"hackempire_report_{target}.md")
        out_file.write_text(content, encoding="utf-8")
        console.print(f"[bold green]Report saved:[/bold green] {out_file}")
        return 0

    if fmt == "csv":
        from web.exporters.csv_export import generate_csv
        content = generate_csv(state)
        out_file = Path(f"hackempire_report_{target}.csv")
        out_file.write_text(content, encoding="utf-8")
        console.print(f"[bold green]Report saved:[/bold green] {out_file}")
        return 0

    return 0


# ---------------------------------------------------------------------------
# install-tools
# ---------------------------------------------------------------------------

def cmd_install_tools(console: Console) -> int:
    """Invoke DependencyResolver to install all registered tools."""
    from installer.dependency_resolver import DependencyResolver
    from installer.tool_installer import TOOL_INSTALL_SPECS

    logger = Logger(console=console)
    resolver = DependencyResolver(logger=logger, auto_approve=True)

    all_tool_names = list(TOOL_INSTALL_SPECS.keys())
    console.print(
        Panel(
            f"[bold cyan]Installing {len(all_tool_names)} tools…[/bold cyan]",
            border_style="cyan",
        )
    )

    results = resolver.resolve(all_tool_names)

    table = Table(title="Install Results", border_style="cyan", show_lines=True)
    table.add_column("Tool", style="bold white")
    table.add_column("Status", justify="center")

    for name, status in results.items():
        if status in ("installed", "already_installed"):
            status_text = Text(status.upper(), style="bold green")
        elif status == "skipped":
            status_text = Text("SKIPPED", style="dim")
        else:
            status_text = Text("FAILED", style="bold red")
        table.add_row(name, status_text)

    console.print(table)
    return 0


# ---------------------------------------------------------------------------
# terminal
# ---------------------------------------------------------------------------

def cmd_terminal(console: Console) -> int:
    """Open the web terminal in the default browser."""
    url = "https://127.0.0.1:5443/dashboard"
    console.print(f"[bold cyan]Opening terminal:[/bold cyan] {url}")
    try:
        webbrowser.open(url)
    except Exception as exc:
        console.print(f"[bold red]Could not open browser:[/bold red] {exc}")
        console.print(f"[dim]Navigate manually to: {url}[/dim]")
        return 1
    return 0


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

_CONFIG_DIR = _ROOT / ".hackempire"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def cmd_config(console: Console, key: str, value: str) -> int:
    """Write a key/value pair to .hackempire/config.json."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if _CONFIG_FILE.exists():
        try:
            config = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}

    config[key] = value
    _CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    console.print(
        f"[bold green]Config updated:[/bold green] "
        f"[cyan]{key}[/cyan] = [white]{value}[/white]"
    )
    return 0
