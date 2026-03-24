"""
HackEmpire X — Dynamic CLI Banner
Cyberpunk/hacker aesthetic using Rich. Safe on all terminals including Kali Linux.
"""
from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align


# ASCII art — pure ASCII, no Unicode box-drawing chars that break on some terminals
_LOGO = r"""
 _   _            _     _____                 _            __  __
| | | | __ _  ___| | __| ____|_ __ ___  _ __ (_)_ __ ___  \ \/ /
| |_| |/ _` |/ __| |/ /|  _| | '_ ` _ \| '_ \| | '__/ _ \  \  /
|  _  | (_| | (__|   < | |___| | | | | | |_) | | | |  __/  /  \
|_| |_|\__,_|\___|_|\_\|_____|_| |_| |_| .__/|_|_|  \___| /_/\_\
                                        |_|
"""

_TAGLINE = "AI-Orchestrated Pentesting Platform"
_AUTHOR  = "Made by Chandan Pandey"
_VERSION = "v1.0.0"


def print_banner(console: Console) -> None:
    """
    Render the full HackEmpire X startup banner.
    Gracefully degrades on terminals without color/Unicode support.
    """
    # Logo block
    logo_text = Text(_LOGO.strip("\n"), style="bold red", justify="center")

    # Info line
    info = Text(justify="center")
    info.append("  [ ", style="dim white")
    info.append(_TAGLINE, style="bold cyan")
    info.append(" ]  ", style="dim white")
    info.append(_VERSION, style="bold yellow")

    # Author line
    author = Text(justify="center")
    author.append(_AUTHOR, style="dim cyan")

    # Separator
    sep = Text("─" * 62, style="dim red", justify="center")

    body = Text.assemble(
        logo_text, "\n",
        info, "\n",
        author, "\n",
        sep,
    )

    console.print(
        Panel(
            Align.center(body),
            border_style="bold red",
            padding=(0, 2),
        )
    )


def print_scan_info(
    console: Console,
    *,
    target: str,
    mode: str,
    web: bool = False,
    ai: bool = False,
    proxy: Optional[str] = None,
) -> None:
    """Render the pre-scan info panel."""
    lines: list[str] = [
        f"[bold green]  Target  [/bold green] [white]{target}[/white]",
        f"[bold green]  Mode    [/bold green] [bold yellow]{mode.upper()}[/bold yellow]",
        f"[bold green]  Web GUI [/bold green] {'[bold cyan]ON  http://127.0.0.1:5000[/bold cyan]' if web else '[dim]OFF[/dim]'}",
        f"[bold green]  AI      [/bold green] {'[bold magenta]ENABLED[/bold magenta]' if ai else '[dim]DISABLED[/dim]'}",
        f"[bold green]  Proxy   [/bold green] {'[bold yellow]' + proxy + '[/bold yellow]' if proxy else '[dim]NONE[/dim]'}",
        "",
        "[dim]  Initializing scan engine...[/dim]",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold red]>> SCAN CONFIG <<[/bold red]",
            border_style="magenta",
            padding=(0, 2),
        )
    )
