"""
HackEmpire X — Main CLI entry point.

Usage:
    python main.py <target> --mode [beginner|pro|lab] [--web] [--ai-key KEY]
    python main.py --status
    python main.py --doctor
    python main.py --clean
    python main.py --uninstall
"""
from __future__ import annotations

import argparse
import sys
import threading
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.text import Text

from cli.banner import print_banner, print_scan_info
from core.config import Config
from core.orchestrator import Orchestrator
from core.phases import Phase
from utils.logger import Logger
from utils.validator import validate_target


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hackempire",
        description="HackEmpire X — AI-Orchestrated Pentesting Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py example.com --mode pro\n"
            "  python main.py 192.168.1.1 --mode beginner --web\n"
            "  python main.py example.com --mode lab --ai-key YOUR_KEY --web\n"
            "  python main.py --status\n"
            "  python main.py --doctor\n"
            "  python main.py --clean\n"
            "  python main.py --uninstall\n"
            "  python main.py scan example.com --mode full\n"
            "  python main.py scan example.com --mode exploit\n"
            "  python main.py scan example.com --mode stealth --resume\n"
            "  python main.py report --format json\n"
            "  python main.py install-tools\n"
            "  python main.py terminal\n"
            "  python main.py config ai_key YOUR_KEY\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="COMMAND")

    # ------------------------------------------------------------------
    # scan subcommand
    # ------------------------------------------------------------------
    scan_parser = subparsers.add_parser(
        "scan",
        help="Run a scan against a target",
    )
    scan_parser.add_argument("target", help="Target domain or IP address")
    scan_parser.add_argument(
        "--mode",
        choices=["recon-only", "full", "exploit", "stealth"],
        default="full",
        help="Scan mode (default: full)",
    )
    scan_parser.add_argument("--ai-key", dest="ai_key", default=None)
    scan_parser.add_argument("--web", action="store_true", default=False)
    scan_parser.add_argument("--proxy", default=None)
    scan_parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume a previous scan",
    )

    # ------------------------------------------------------------------
    # report subcommand
    # ------------------------------------------------------------------
    report_parser = subparsers.add_parser(
        "report",
        help="Export the latest scan report",
    )
    report_parser.add_argument(
        "--format",
        dest="fmt",
        choices=["pdf", "json", "html", "markdown", "csv"],
        default="json",
        help="Output format (default: json)",
    )

    # ------------------------------------------------------------------
    # install-tools subcommand
    # ------------------------------------------------------------------
    subparsers.add_parser("install-tools", help="Install all registered tools")

    # ------------------------------------------------------------------
    # terminal subcommand
    # ------------------------------------------------------------------
    subparsers.add_parser("terminal", help="Open web terminal in default browser")

    # ------------------------------------------------------------------
    # config subcommand
    # ------------------------------------------------------------------
    config_parser = subparsers.add_parser(
        "config",
        help="Set a configuration key/value in .hackempire/config.json",
    )
    config_parser.add_argument("key", help="Configuration key")
    config_parser.add_argument("value", help="Configuration value")

    # ------------------------------------------------------------------
    # Legacy positional target (kept for backward compatibility)
    # ------------------------------------------------------------------
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target domain or IP address (legacy positional form)",
    )

    # Scan options (legacy)
    parser.add_argument(
        "--mode",
        choices=["beginner", "pro", "lab"],
        default=None,
        help="Execution mode (required for legacy scans)",
    )
    parser.add_argument(
        "--ai-key",
        dest="ai_key",
        default=None,
        help="OpenRouter API key for AI-assisted decisions",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        default=False,
        help="Launch web dashboard at https://127.0.0.1:5443/dashboard",
    )
    parser.add_argument(
        "--proxy",
        dest="proxy",
        default=None,
        metavar="URL",
        help="Route all tool traffic through a proxy (e.g. http://127.0.0.1:8080 for Burp Suite)",
    )
    parser.add_argument(
        "--target-file",
        dest="target_file",
        default=None,
        metavar="FILE",
        help="Path to a file containing one target per line (multi-target mode)",
    )

    # Global utility commands
    parser.add_argument(
        "--status",
        action="store_true",
        default=False,
        help="Show system and tool installation status",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        default=False,
        help="Run the Tool Doctor to diagnose and fix broken tools",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Clear logs and temporary files",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        default=False,
        help="Completely remove HackEmpire X (logs, cache, optionally packages)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    console = Console(legacy_windows=True, emoji=False)

    # Always show the banner first
    print_banner(console)

    # -----------------------------------------------------------------------
    # New subcommands
    # -----------------------------------------------------------------------
    from cli.commands import (
        cmd_status, cmd_doctor, cmd_clean, cmd_uninstall,
        cmd_scan, cmd_report, cmd_install_tools, cmd_terminal, cmd_config,
    )

    if args.subcommand == "scan":
        return cmd_scan(
            console=console,
            target=args.target,
            mode=args.mode,
            ai_key=args.ai_key,
            web=args.web,
            proxy=args.proxy,
            resume=args.resume,
        )

    if args.subcommand == "report":
        return cmd_report(console=console, fmt=args.fmt)

    if args.subcommand == "install-tools":
        return cmd_install_tools(console=console)

    if args.subcommand == "terminal":
        return cmd_terminal(console=console)

    if args.subcommand == "config":
        return cmd_config(console=console, key=args.key, value=args.value)

    # -----------------------------------------------------------------------
    # Legacy global utility commands — no target required
    # -----------------------------------------------------------------------
    if args.uninstall:
        return cmd_uninstall(console)

    if args.status:
        return cmd_status(console)

    if args.doctor:
        return cmd_doctor(console)

    if args.clean:
        return cmd_clean(console)

    # -----------------------------------------------------------------------
    # Scan mode — target + mode are required
    # -----------------------------------------------------------------------
    if args.target is None and args.target_file is None:
        parser.print_help()
        return 0

    if args.mode is None:
        console.print("[bold red]Error:[/bold red] --mode is required for scans. "
                      "Choose: beginner | pro | lab")
        return 2

    logger = Logger(console=console)

    # Build target list
    from utils.validator import validate_target, load_target_file

    targets: list[str] = []

    if args.target_file:
        targets = load_target_file(args.target_file)
        if not targets:
            logger.error("No valid targets found in target file.")
            return 2
        logger.success(f"Loaded {len(targets)} target(s) from {args.target_file}")
    else:
        raw_target = (args.target or "").strip()
        if not validate_target(raw_target):
            logger.error("Invalid target. Provide a valid domain name or IP address.")
            return 2
        targets = [raw_target]
        logger.success("Target validated")

    mode = args.mode.strip().lower()
    proxy = args.proxy or None

    if proxy:
        logger.success(f"Proxy configured: {proxy}")

    # -----------------------------------------------------------------------
    # Web GUI — start before scan so dashboard is ready immediately
    # -----------------------------------------------------------------------
    if args.web:
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

    # -----------------------------------------------------------------------
    # Multi-target loop
    # -----------------------------------------------------------------------
    overall_exit = 0
    for idx, target in enumerate(targets):
        if len(targets) > 1:
            console.print(
                Panel.fit(
                    f"[bold cyan]Target {idx + 1}/{len(targets)}: {target}[/bold cyan]",
                    border_style="cyan",
                )
            )

        exit_code = _run_single_target(
            console=console,
            logger=logger,
            target=target,
            mode=mode,
            ai_key=args.ai_key,
            web=args.web,
            proxy=proxy,
        )
        if exit_code != 0:
            overall_exit = exit_code

    if args.web:
        console.print(
            Panel.fit(
                "[bold green]All scans complete.[/bold green]  "
                "[dim]Dashboard → https://127.0.0.1:5443/dashboard[/dim]",
                border_style="green",
            )
        )
    return overall_exit


# ---------------------------------------------------------------------------
# Single-target scan runner (called once per target in multi-target mode)
# ---------------------------------------------------------------------------

def _run_single_target(
    *,
    console: Console,
    logger: Logger,
    target: str,
    mode: str,
    ai_key: Optional[str],
    web: bool,
    proxy: Optional[str],
) -> int:
    try:
        print_scan_info(
            console,
            target=target,
            mode=mode,
            web=web,
            ai=bool(ai_key),
            proxy=proxy,
        )

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

    phase_names = [Phase.RECON.value, Phase.ENUM.value, Phase.VULN.value]
    task_ids: dict[str, int] = {}
    _progress_ref: list[Progress] = []

    def phase_hook(phase_name: str, event: str) -> None:
        if not _progress_ref or phase_name not in task_ids:
            return
        prog = _progress_ref[0]
        if event == "start":
            prog.start_task(task_ids[phase_name])
        elif event == "success":
            prog.update(task_ids[phase_name], completed=100)
        elif event == "error":
            prog.update(task_ids[phase_name], description=f"[red]{phase_name} (error)[/red]")

    orchestrator = Orchestrator(
        config=config,
        logger=logger,
        phase_hook=phase_hook,  # type: ignore[arg-type]
    )

    console.print(
        Panel.fit(
            f"[bold cyan]Starting scan: {target}[/bold cyan]",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(style="bold red"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="red", complete_style="green"),
        TextColumn("[bold]{task.completed:>3}/{task.total}"),
        TimeElapsedColumn(),
        transient=False,
        console=console,
    ) as progress:
        _progress_ref.append(progress)

        for name in phase_names:
            task_ids[name] = progress.add_task(
                description=f"[dim]{name}[/dim]",
                total=100,
                start=False,
            )

        try:
            orchestrator.initialize()
            orchestrator.run()
        except Exception as exc:
            logger.error("Orchestration failed", exc=exc)
            return 1

    console.print(
        Panel.fit(
            f"[bold green]Scan complete: {target}[/bold green]"
            + (f"  [dim]Dashboard → https://127.0.0.1:5443/dashboard[/dim]" if web else ""),
            border_style="green",
        )
    )
    return 0
