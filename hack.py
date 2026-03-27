#!/usr/bin/env python3
"""
HackEmpire X — Single Command Full Autonomous Scanner
Usage: python3 hack.py <target>
Example: python3 hack.py partners.shopify.com

What it does automatically:
  1. Validates target
  2. Loads API keys from config
  3. Starts web dashboard (https://127.0.0.1:5443/dashboard)
  4. Runs full 7-phase autonomous scan
  5. Generates PDF + JSON + HTML reports
  6. Saves findings to RAG knowledge base
  7. Opens dashboard in browser
"""
from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

# Bootstrap path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401

from rich.console import Console
from rich.panel import Panel

console = Console()


def _banner() -> None:
    console.print(Panel(
        "[bold red]HackEmpire X[/bold red] — [bold cyan]Full Autonomous Scanner[/bold cyan]\n"
        "[dim]Single command. Full attack surface. AI-driven.[/dim]",
        border_style="red",
    ))


def _load_keys() -> tuple[str, str]:
    cfg_file = Path.home() / ".hackempire" / "config.json"
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text())
            return cfg.get("bytez_key", "") or cfg.get("bytez_api_key", ""), \
                   cfg.get("openrouter_key", "") or cfg.get("openrouter_api_key", "")
        except Exception:
            pass
    return os.environ.get("BYTEZ_API_KEY", ""), os.environ.get("OPENROUTER_API_KEY", "")


def _start_dashboard() -> None:
    """Start web dashboard in background thread."""
    import socket as _sock

    def _port_free(p: int) -> bool:
        with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
            s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return True
            except OSError:
                return False

    if not _port_free(5443):
        console.print("[dim]Dashboard already running → https://127.0.0.1:5443/dashboard[/dim]")
        return

    def _run():
        try:
            from web.app import run_server
            run_server(host="127.0.0.1", port=5443, debug=False)
        except Exception as e:
            console.print(f"[dim]Dashboard: {e}[/dim]")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(2)
    console.print("[bold green]Dashboard started → https://127.0.0.1:5443/dashboard[/bold green]")


def _run_scan(target: str, bytez_key: str, openrouter_key: str) -> dict:
    """Run full 7-phase autonomous scan and return final report."""
    from utils.logger import Logger
    from core.config import Config
    from core.orchestrator import OrchestratorV2
    from tools.tool_manager import ToolManager
    from core.phase_manager import PhaseManager
    from web.realtime_emitter import RealTimeEmitter

    logger = Logger(console=console)

    # Config
    config = Config.create(
        target=target,
        mode="exploit",
        ai_key=openrouter_key or None,
        web_enabled=True,
        proxy=None,
        autonomous=True,
    )

    # AI Engine
    ai_engine = None
    if bytez_key or openrouter_key:
        try:
            from ai.ai_engine import AIEngine
            ai_engine = AIEngine(
                bytez_key=bytez_key or None,
                openrouter_key=openrouter_key or None,
            )
            provider = "Bytez AI" if bytez_key else "OpenRouter"
            logger.success(f"AI provider: {provider}")
        except Exception as exc:
            logger.warning(f"AIEngine init failed: {exc} — using offline KB")
    else:
        logger.info("No API keys — using offline KB (set keys: python3 hack.py --setup)")

    # Emitter
    emitter = None
    try:
        # Try to get socketio from running app
        try:
            import flask
            _sio = None
            if flask.has_app_context():
                _sio = flask.current_app.extensions.get("socketio")
        except Exception:
            _sio = None
        emitter = RealTimeEmitter(socketio=_sio)
    except Exception:
        pass

    # Tool Manager
    os.environ["HACKEMPIRE_AUTO_APPROVE"] = "1"
    tool_manager = None
    try:
        tool_manager = ToolManager(
            logger=logger,
            timeout_s=120.0,
            execution_mode="parallel",
            max_workers=4,
            web_scheme="https",
            proxy=None,
        )
    except Exception as exc:
        logger.warning(f"ToolManager init failed: {exc}")

    # Phase Manager
    phase_manager = None
    if tool_manager:
        try:
            phase_manager = PhaseManager(tool_manager=tool_manager, emitter=emitter)
        except Exception as exc:
            logger.warning(f"PhaseManager init failed: {exc}")

    # WAF Detection
    try:
        from tools.waf.waf_detector import WafDetector
        waf = WafDetector().detect(target)
        if waf.detected:
            logger.success(f"WAF detected: {waf.vendor} — bypass loaded")
        else:
            logger.info("No WAF detected")
    except Exception:
        pass

    # Run scan
    orchestrator = OrchestratorV2(
        config=config,
        logger=logger,
        emitter=emitter,
        ai_engine=ai_engine,
        phase_manager=phase_manager,
    )

    console.print(Panel(
        f"[bold cyan]Target:[/bold cyan] {target}\n"
        f"[bold cyan]Mode:[/bold cyan] Full Autonomous (7 phases)\n"
        f"[bold cyan]AI:[/bold cyan] {'Bytez → OpenRouter → KB' if bytez_key else 'Offline KB'}\n"
        f"[bold cyan]Dashboard:[/bold cyan] https://127.0.0.1:5443/dashboard",
        title="[bold red]SCAN STARTING[/bold red]",
        border_style="red",
    ))

    return orchestrator.run_full_scan(target)


def _export_reports(target: str) -> None:
    """Export PDF, JSON, HTML reports."""
    from web.state_bridge import read_state
    from web.pdf_report import generate_html, generate_pdf, weasyprint_available

    state = read_state()
    safe_target = target.replace(".", "_").replace("/", "_")

    # JSON
    try:
        out = Path(f"report_{safe_target}.json")
        out.write_text(json.dumps(state, indent=2, default=str))
        console.print(f"[green]JSON report:[/green] {out}")
    except Exception as e:
        console.print(f"[dim]JSON export failed: {e}[/dim]")

    # HTML
    try:
        html = generate_html(state)
        out = Path(f"report_{safe_target}.html")
        out.write_text(html)
        console.print(f"[green]HTML report:[/green] {out}")
    except Exception as e:
        console.print(f"[dim]HTML export failed: {e}[/dim]")

    # PDF
    try:
        if weasyprint_available():
            pdf = generate_pdf(state)
            if pdf:
                out = Path(f"report_{safe_target}.pdf")
                out.write_bytes(pdf)
                console.print(f"[green]PDF report:[/green] {out}")
    except Exception as e:
        console.print(f"[dim]PDF export failed: {e}[/dim]")


def _setup_keys() -> None:
    """Interactive setup for API keys."""
    console.print(Panel(
        "[bold cyan]API Key Setup[/bold cyan]\n\n"
        "Get free Bytez key: [link]https://bytez.com[/link]\n"
        "Get free OpenRouter key: [link]https://openrouter.ai[/link]",
        border_style="cyan",
    ))
    cfg_dir = Path.home() / ".hackempire"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.json"

    existing = {}
    if cfg_file.exists():
        try:
            existing = json.loads(cfg_file.read_text())
        except Exception:
            pass

    bytez = input("Bytez API key (Enter to skip): ").strip()
    openrouter = input("OpenRouter API key (Enter to skip): ").strip()

    if bytez:
        existing["bytez_api_key"] = bytez
    if openrouter:
        existing["openrouter_key"] = openrouter

    cfg_file.write_text(json.dumps(existing, indent=2))
    console.print(f"[green]Keys saved to {cfg_file}[/green]")


def main() -> None:
    _banner()

    if len(sys.argv) < 2:
        console.print(
            "[bold yellow]Usage:[/bold yellow]\n"
            "  python3 hack.py [bold]<target>[/bold]          — Full autonomous scan\n"
            "  python3 hack.py [bold]--setup[/bold]           — Set API keys\n\n"
            "[bold]Examples:[/bold]\n"
            "  python3 hack.py partners.shopify.com\n"
            "  python3 hack.py accounts.shopify.com\n"
            "  python3 hack.py admin.shopify.com\n"
        )
        sys.exit(0)

    if sys.argv[1] == "--setup":
        _setup_keys()
        return

    target = sys.argv[1].strip()

    # Validate
    from utils.validator import validate_target
    if not validate_target(target):
        console.print(f"[bold red]Invalid target:[/bold red] {target}")
        sys.exit(1)

    bytez_key, openrouter_key = _load_keys()

    # Start dashboard
    _start_dashboard()

    # Open browser after 3 seconds
    def _open_browser():
        time.sleep(3)
        try:
            webbrowser.open("https://127.0.0.1:5443/dashboard")
        except Exception:
            pass
    threading.Thread(target=_open_browser, daemon=True).start()

    # Run scan
    try:
        report = _run_scan(target, bytez_key, openrouter_key)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Scan interrupted by user.[/bold yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"[bold red]Scan error:[/bold red] {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Export reports
    console.print("\n[bold cyan]Exporting reports...[/bold cyan]")
    _export_reports(target)

    # Summary
    vulns = []
    try:
        from core.phases import Phase
        vuln_data = report.get("phase_results", {}).get(Phase.VULN_SCAN.value, {})
        if isinstance(vuln_data, dict):
            vulns = vuln_data.get("vulnerabilities", [])
    except Exception:
        pass

    console.print(Panel(
        f"[bold green]Scan Complete![/bold green]\n\n"
        f"Target: [cyan]{target}[/cyan]\n"
        f"Vulnerabilities found: [bold red]{len(vulns)}[/bold red]\n"
        f"Reports saved: report_{target.replace('.', '_')}.[json/html/pdf]\n"
        f"Dashboard: [link]https://127.0.0.1:5443/dashboard[/link]",
        border_style="green",
        title="[bold]RESULTS[/bold]",
    ))

    # Keep dashboard alive
    console.print("\n[dim]Dashboard running. Press Ctrl+C to exit.[/dim]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Exiting.[/dim]")


if __name__ == "__main__":
    main()
