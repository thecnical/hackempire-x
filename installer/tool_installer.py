"""
ToolInstaller — production-grade tool installation engine for HackEmpire X.

Responsibilities:
- Detect whether a tool is installed (shutil.which)
- Ask user permission before installing
- Install via apt, pip, or git clone depending on tool config
- Verify installation after install attempt
- Log all results
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Literal, Optional

from utils.logger import Logger


# ---------------------------------------------------------------------------
# Install method type
# ---------------------------------------------------------------------------

InstallMethod = Literal["apt", "pip", "git", "go", "gem", "script"]


@dataclass(frozen=True, slots=True)
class ToolInstallSpec:
    """Describes how to install a single tool."""

    name: str                          # binary name (used for shutil.which)
    method: InstallMethod
    package: str                       # apt package, pip package, or git URL
    post_install_bin: Optional[str] = None  # binary to check after git clone (if different from name)
    git_dest: Optional[str] = None     # local directory for git clone
    extra_args: list[str] = field(default_factory=list)  # extra apt/pip flags


# ---------------------------------------------------------------------------
# Default tool registry — extend here to add new tools
# ---------------------------------------------------------------------------

TOOL_INSTALL_SPECS: dict[str, ToolInstallSpec] = {
    # --- original tools ---
    "nmap":       ToolInstallSpec(name="nmap",       method="apt", package="nmap"),
    "subfinder":  ToolInstallSpec(name="subfinder",  method="apt", package="subfinder"),
    "nuclei":     ToolInstallSpec(name="nuclei",     method="apt", package="nuclei"),
    "ffuf":       ToolInstallSpec(name="ffuf",       method="apt", package="ffuf"),
    "whatweb":    ToolInstallSpec(name="whatweb",    method="apt", package="whatweb"),
    "dirsearch":  ToolInstallSpec(
        name="dirsearch",
        method="git",
        package="https://github.com/maurosoria/dirsearch.git",
        post_install_bin="dirsearch",
        git_dest="/opt/dirsearch",
    ),
    # --- Go-based tools (Upgrade 1) ---
    "httpx":             ToolInstallSpec(name="httpx",             method="go", package="github.com/projectdiscovery/httpx/cmd/httpx@latest"),
    "dnsx":              ToolInstallSpec(name="dnsx",              method="go", package="github.com/projectdiscovery/dnsx/cmd/dnsx@latest"),
    "shuffledns":        ToolInstallSpec(name="shuffledns",        method="go", package="github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest"),
    "katana":            ToolInstallSpec(name="katana",            method="go", package="github.com/projectdiscovery/katana/cmd/katana@latest"),
    "hakrawler":         ToolInstallSpec(name="hakrawler",         method="go", package="github.com/hakluke/hakrawler@latest"),
    "gospider":          ToolInstallSpec(name="gospider",          method="go", package="github.com/jaeles-project/gospider@latest"),
    "kiterunner":        ToolInstallSpec(name="kr",                method="go", package="github.com/assetnote/kiterunner/cmd/kr@latest"),
    "afrog":             ToolInstallSpec(name="afrog",             method="go", package="github.com/zan8in/afrog/cmd/afrog@latest"),
    "dalfox":            ToolInstallSpec(name="dalfox",            method="go", package="github.com/hahwul/dalfox/v2@latest"),
    "jsluice":           ToolInstallSpec(name="jsluice",           method="go", package="github.com/BishopFox/jsluice/cmd/jsluice@latest"),
    "trufflehog":        ToolInstallSpec(name="trufflehog",        method="go", package="github.com/trufflesecurity/trufflehog/v3@latest"),
    "gau":               ToolInstallSpec(name="gau",               method="go", package="github.com/lc/gau/v2/cmd/gau@latest"),
    "waybackurls":       ToolInstallSpec(name="waybackurls",       method="go", package="github.com/tomnomnom/waybackurls@latest"),
    "cariddi":           ToolInstallSpec(name="cariddi",           method="go", package="github.com/edoardottt/cariddi/cmd/cariddi@latest"),
    "github-subdomains": ToolInstallSpec(name="github-subdomains", method="go", package="github.com/gwen001/github-subdomains@latest"),
    # --- pip-based tools (Upgrade 1) ---
    "arjun":        ToolInstallSpec(name="arjun",        method="pip", package="arjun"),
    "paramspider":  ToolInstallSpec(name="paramspider",  method="pip", package="paramspider"),
    "ghauri":       ToolInstallSpec(name="ghauri",       method="pip", package="ghauri"),
    "bloodhound":   ToolInstallSpec(name="bloodhound",   method="pip", package="bloodhound"),
    "impacket":     ToolInstallSpec(name="impacket",     method="pip", package="impacket"),
    "crackmapexec": ToolInstallSpec(name="crackmapexec", method="pip", package="crackmapexec"),
    # --- git-based tools (Upgrade 1) ---
    "xsstrike": ToolInstallSpec(name="xsstrike",   method="git", package="https://github.com/s0md3v/XSStrike.git",          git_dest="/opt/xsstrike"),
    "commix":   ToolInstallSpec(name="commix",     method="git", package="https://github.com/commixproject/commix.git",     git_dest="/opt/commix"),
    "linpeas":  ToolInstallSpec(name="linpeas",    method="git", package="https://github.com/carlospolop/PEASS-ng.git",     git_dest="/opt/peass"),
    "caido":    ToolInstallSpec(name="caido",      method="git", package="https://github.com/caido/caido.git",              git_dest="/opt/caido"),
    "testssl":  ToolInstallSpec(name="testssl.sh", method="git", package="https://github.com/drwetter/testssl.sh.git",      git_dest="/opt/testssl"),
    # --- apt-based tools (Upgrade 1) ---
    "feroxbuster": ToolInstallSpec(name="feroxbuster", method="apt", package="feroxbuster"),
    "nikto":       ToolInstallSpec(name="nikto",       method="apt", package="nikto"),
    "sqlmap":      ToolInstallSpec(name="sqlmap",      method="apt", package="sqlmap"),
    "amass":       ToolInstallSpec(name="amass",       method="apt", package="amass"),
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class InstallResult:
    tool: str
    status: Literal["installed", "not_installed", "skipped", "already_installed", "failed"]
    message: str = ""


# ---------------------------------------------------------------------------
# ToolInstaller
# ---------------------------------------------------------------------------

class ToolInstaller:
    """
    Checks, installs, and verifies external security tools.

    Usage:
        installer = ToolInstaller(logger=logger, mode="pro")
        results = installer.ensure_tools(["nmap", "nuclei", "subfinder"])
    """

    def __init__(
        self,
        *,
        logger: Logger,
        mode: str = "pro",
        auto_approve: bool = False,
    ) -> None:
        self._logger = logger
        self._mode = mode.lower()
        self._auto_approve = auto_approve  # skip prompts in non-interactive / test mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_installed(self, tool_name: str) -> bool:
        """Return True if the tool binary is on PATH."""
        spec = TOOL_INSTALL_SPECS.get(tool_name)
        binary = (spec.post_install_bin or spec.name) if spec else tool_name
        return shutil.which(binary) is not None

    def ensure_tools(self, tool_names: list[str]) -> list[InstallResult]:
        """
        For each tool: check → prompt → install → verify.
        Never raises; errors are captured in InstallResult.
        """
        results: list[InstallResult] = []
        for name in tool_names:
            results.append(self._process_tool(name))
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_tool(self, tool_name: str) -> InstallResult:
        if self.check_installed(tool_name):
            self._logger.info(f"[installer] '{tool_name}' is already installed.")
            return InstallResult(tool=tool_name, status="already_installed")

        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if spec is None:
            msg = f"No install spec found for '{tool_name}'. Manual installation required."
            self._logger.warning(f"[installer] {msg}")
            return InstallResult(tool=tool_name, status="not_installed", message=msg)

        if not self._ask_permission(tool_name, spec):
            self._logger.info(f"[installer] '{tool_name}' installation skipped by user.")
            return InstallResult(tool=tool_name, status="skipped", message="User declined installation.")

        return self._install_and_verify(spec)

    def _ask_permission(self, tool_name: str, spec: ToolInstallSpec) -> bool:
        """Prompt user for install permission. Returns True if approved."""
        if self._auto_approve:
            return True

        try:
            if self._mode == "beginner":
                print(
                    f"\n[HackEmpire X] Tool '{tool_name}' is missing.\n"
                    f"  Install method : {spec.method}\n"
                    f"  Package        : {spec.package}\n"
                    f"  This tool is required for scanning. "
                    f"Installing it will run a system command.\n"
                )
                answer = input("Install? (y/n): ").strip().lower()
            else:
                answer = input(
                    f"\n[HackEmpire X] Tool '{tool_name}' is missing. Install? (y/n): "
                ).strip().lower()
        except (EOFError, OSError):
            # Non-interactive environment — skip silently.
            self._logger.warning(
                f"[installer] Non-interactive environment; skipping '{tool_name}'."
            )
            return False

        return answer in ("y", "yes")

    def _install_and_verify(self, spec: ToolInstallSpec) -> InstallResult:
        self._logger.info(f"[installer] Installing '{spec.name}' via {spec.method}...")
        try:
            if spec.method == "apt":
                self._run_apt(spec)
            elif spec.method == "pip":
                self._run_pip(spec)
            elif spec.method == "git":
                self._run_git(spec)
            elif spec.method == "go":
                self._run_go(spec)
            elif spec.method == "gem":
                self._run_gem(spec)
            elif spec.method == "script":
                self._run_script(spec)
            else:
                raise ValueError(f"Unknown install method: {spec.method}")
        except Exception as exc:
            msg = f"Installation failed: {exc}"
            self._logger.error(f"[installer] '{spec.name}': {msg}")
            return InstallResult(tool=spec.name, status="failed", message=msg)

        # Verify
        if self.check_installed(spec.name):
            self._logger.success(f"[installer] '{spec.name}' installed and verified.")
            return InstallResult(tool=spec.name, status="installed", message="Installed successfully.")

        msg = "Install command ran but binary not found on PATH after install."
        self._logger.warning(f"[installer] '{spec.name}': {msg}")
        return InstallResult(tool=spec.name, status="failed", message=msg)

    # ------------------------------------------------------------------
    # Install strategies — no shell=True to prevent injection
    # ------------------------------------------------------------------

    def _run_apt(self, spec: ToolInstallSpec) -> None:
        cmd = ["apt-get", "install", "-y", spec.package] + spec.extra_args
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_pip(self, spec: ToolInstallSpec) -> None:
        cmd = [sys.executable, "-m", "pip", "install", spec.package] + spec.extra_args
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_git(self, spec: ToolInstallSpec) -> None:
        dest = spec.git_dest or f"/opt/{spec.name}"
        cmd = ["git", "clone", spec.package, dest]
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_go(self, spec: ToolInstallSpec) -> None:
        cmd = ["go", "install", spec.package]
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_gem(self, spec: ToolInstallSpec) -> None:
        cmd = ["gem", "install", spec.package]
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_script(self, spec: ToolInstallSpec) -> None:
        cmd = [spec.package]
        self._run_subprocess(cmd, tool_name=spec.name)

    def _run_subprocess(self, cmd: list[str], *, tool_name: str) -> None:
        """
        Run a subprocess safely (no shell=True).
        Raises subprocess.CalledProcessError on non-zero exit.
        """
        self._logger.info(f"[installer] Running: {shlex.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,  # 5-minute hard cap per install
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"Command exited {result.returncode}: {stderr[:500]}")
