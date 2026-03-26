"""
ToolInstaller — HackEmpire X tool installation engine.

Fixes applied (from Kali install errors):
- git clone: skip if dest already exists (no "not empty dir" error)
- git clone: use sudo for /opt/ paths
- crackmapexec: replaced with netexec (maintained fork, correct PyPI name)
- paramspider: correct git clone (not on PyPI)
- ghauri: correct git clone (not on PyPI)
- bloodhound: correct binary = bloodhound-python, pip pkg = bloodhound
- impacket: correct binary check = impacket-secretsdump
- kiterunner: correct go module path
- trufflehog: pre-built binary via curl (needs Go >= 1.24)
- caido: removed (closed-source, no public git)
- testssl: skip if /opt/testssl exists (already cloned)
- xsstrike: skip if /opt/xsstrike exists

New tools added:
- naabu (go) — fast port scanner
- interactsh-client (go) — OOB interaction server
- metasploit (apt) — exploitation framework
- waymore (pip) — URL harvester
- tplmap (git) — SSTI exploitation
- commix (git) — command injection
- chisel (go) — TCP tunnel
- ligolo-ng (go) — reverse tunnel/pivoting
- sslyze (pip) — TLS analysis
- enum4linux-ng (apt) — SMB/AD enumeration
- naabu (go) — port scanner
- assetfinder (go) — subdomain finder
- anew (go) — dedup pipeline tool
- qsreplace (go) — query string replacer
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from utils.logger import Logger

InstallMethod = Literal["apt", "pip", "git", "go", "gem", "curl"]


@dataclass(frozen=True, slots=True)
class ToolInstallSpec:
    name: str                           # logical tool name
    method: InstallMethod
    package: str                        # apt pkg / pip pkg / git URL / go module / curl URL
    check_bin: Optional[str] = None     # binary to check (overrides name)
    git_dest: Optional[str] = None      # destination dir for git clone
    pip_bin: Optional[str] = None       # binary name after pip install (if different)
    extra_args: list[str] = field(default_factory=list)
    needs_sudo_clone: bool = True       # git clone to /opt needs sudo


# ---------------------------------------------------------------------------
# Tool registry — all correct specs
# ---------------------------------------------------------------------------

TOOL_INSTALL_SPECS: dict[str, ToolInstallSpec] = {

    # ── APT ──────────────────────────────────────────────────────────────────
    "nmap":          ToolInstallSpec("nmap",          "apt", "nmap"),
    "ffuf":          ToolInstallSpec("ffuf",          "apt", "ffuf"),
    "whatweb":       ToolInstallSpec("whatweb",       "apt", "whatweb"),
    "feroxbuster":   ToolInstallSpec("feroxbuster",   "apt", "feroxbuster"),
    "nikto":         ToolInstallSpec("nikto",         "apt", "nikto"),
    "amass":         ToolInstallSpec("amass",         "apt", "amass"),
    "gobuster":      ToolInstallSpec("gobuster",      "apt", "gobuster"),
    "wfuzz":         ToolInstallSpec("wfuzz",         "apt", "wfuzz"),
    "smbmap":        ToolInstallSpec("smbmap",        "apt", "smbmap"),
    "sqlmap":        ToolInstallSpec("sqlmap",        "apt", "sqlmap"),
    "metasploit":    ToolInstallSpec("metasploit",    "apt", "metasploit-framework",  check_bin="msfconsole"),
    # enum4linux-ng: apt package name is enum4linux (Kali), NOT enum4linux-ng
    "enum4linux-ng": ToolInstallSpec("enum4linux-ng", "apt", "enum4linux",            check_bin="enum4linux-ng"),
    "responder":     ToolInstallSpec("responder",     "apt", "responder"),
    "wafw00f":       ToolInstallSpec("wafw00f",       "apt", "wafw00f"),
    # rustscan: fast port scanner, replaces naabu (which needs libpcap-dev + Go>=1.24)
    "rustscan":      ToolInstallSpec("rustscan",      "apt", "rustscan"),

    # ── Go ───────────────────────────────────────────────────────────────────
    "subfinder":     ToolInstallSpec("subfinder",     "go", "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
    "httpx":         ToolInstallSpec("httpx",         "go", "github.com/projectdiscovery/httpx/cmd/httpx@latest"),
    "dnsx":          ToolInstallSpec("dnsx",          "go", "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"),
    "shuffledns":    ToolInstallSpec("shuffledns",    "go", "github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest"),
    "nuclei":        ToolInstallSpec("nuclei",        "go", "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
    # naabu: needs libpcap-dev + Go>=1.24 — install via apt with libpcap first
    "naabu":         ToolInstallSpec("naabu",         "go", "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest",
                                     check_bin="naabu"),
    "interactsh-client": ToolInstallSpec("interactsh-client", "go", "github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest"),
    "katana":        ToolInstallSpec("katana",        "go", "github.com/projectdiscovery/katana/cmd/katana@latest"),
    "hakrawler":     ToolInstallSpec("hakrawler",     "go", "github.com/hakluke/hakrawler@latest"),
    "gospider":      ToolInstallSpec("gospider",      "go", "github.com/jaeles-project/gospider@latest"),
    "dalfox":        ToolInstallSpec("dalfox",        "go", "github.com/hahwul/dalfox/v2@latest"),
    "gau":           ToolInstallSpec("gau",           "go", "github.com/lc/gau/v2/cmd/gau@latest"),
    "waybackurls":   ToolInstallSpec("waybackurls",   "go", "github.com/tomnomnom/waybackurls@latest"),
    "cariddi":       ToolInstallSpec("cariddi",       "go", "github.com/edoardottt/cariddi/cmd/cariddi@latest"),
    "assetfinder":   ToolInstallSpec("assetfinder",   "go", "github.com/tomnomnom/assetfinder@latest"),
    "anew":          ToolInstallSpec("anew",          "go", "github.com/tomnomnom/anew@latest"),
    "qsreplace":     ToolInstallSpec("qsreplace",     "go", "github.com/tomnomnom/qsreplace@latest"),
    "chisel":        ToolInstallSpec("chisel",        "go", "github.com/jpillora/chisel@latest"),
    "ligolo-ng":     ToolInstallSpec("ligolo-ng",     "go", "github.com/nicocha30/ligolo-ng/cmd/proxy@latest", check_bin="proxy"),
    "afrog":         ToolInstallSpec("afrog",         "go", "github.com/zan8in/afrog/cmd/afrog@latest"),
    "jsluice":       ToolInstallSpec("jsluice",       "go", "github.com/BishopFox/jsluice/cmd/jsluice@latest"),
    "github-subdomains": ToolInstallSpec("github-subdomains", "go", "github.com/gwen001/github-subdomains@latest"),
    # kiterunner: use pre-built binary from GitHub releases (correct URL format)
    "kiterunner":    ToolInstallSpec("kiterunner",    "git",
                                     "https://github.com/assetnote/kiterunner.git",
                                     git_dest="/opt/kiterunner",
                                     check_bin="kr"),

    # pip (isolated venvs) — only tools actually on PyPI
    "arjun":         ToolInstallSpec("arjun",         "pip", "arjun"),
    "waymore":       ToolInstallSpec("waymore",       "pip", "waymore"),
    "sslyze":        ToolInstallSpec("sslyze",        "pip", "sslyze"),
    "bloodhound":    ToolInstallSpec("bloodhound",    "pip", "bloodhound",       check_bin="bloodhound-python"),
    "impacket":      ToolInstallSpec("impacket",      "pip", "impacket",         check_bin="impacket-secretsdump"),
    "netexec":       ToolInstallSpec("netexec",       "pip", "netexec",          check_bin="nxc"),
    "ldapdomaindump":ToolInstallSpec("ldapdomaindump","pip", "ldapdomaindump"),

    # ── git clone ────────────────────────────────────────────────────────────
    # All git tools: skip clone if dest already exists (fixes "not empty dir" error)
    "xsstrike":  ToolInstallSpec("xsstrike",  "git", "https://github.com/s0md3v/XSStrike.git",           git_dest="/opt/xsstrike",  check_bin=None),
    "commix":    ToolInstallSpec("commix",    "git", "https://github.com/commixproject/commix.git",      git_dest="/opt/commix",    check_bin=None),
    "tplmap":    ToolInstallSpec("tplmap",    "git", "https://github.com/epinna/tplmap.git",             git_dest="/opt/tplmap",    check_bin=None),
    "linpeas":   ToolInstallSpec("linpeas",   "git", "https://github.com/carlospolop/PEASS-ng.git",      git_dest="/opt/peass",     check_bin=None),
    "testssl":   ToolInstallSpec("testssl",   "git", "https://github.com/drwetter/testssl.sh.git",       git_dest="/opt/testssl",   check_bin=None),
    "dirsearch": ToolInstallSpec("dirsearch", "git", "https://github.com/maurosoria/dirsearch.git",      git_dest="/opt/dirsearch", check_bin=None),
    # ghauri: not on PyPI, must be git cloned
    "ghauri":    ToolInstallSpec("ghauri",    "git", "https://github.com/r0oth3x49/ghauri.git",          git_dest="/opt/ghauri",    check_bin=None),
    # paramspider: not on PyPI in all versions, git clone is reliable
    "paramspider":ToolInstallSpec("paramspider","git","https://github.com/devanshbatham/ParamSpider.git",git_dest="/opt/paramspider",check_bin=None),
    # trufflehog: needs Go >= 1.24, use pre-built binary via curl
    "trufflehog": ToolInstallSpec("trufflehog","curl",
                                   "https://github.com/trufflesecurity/trufflehog/releases/latest/download/trufflehog_linux_amd64.tar.gz"),
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

    def __init__(self, *, logger: Logger, mode: str = "pro", auto_approve: bool = False) -> None:
        self._logger = logger
        self._mode = mode.lower()
        self._auto_approve = auto_approve

    def check_installed(self, tool_name: str) -> bool:
        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if spec is None:
            return shutil.which(tool_name) is not None
        # Use check_bin override if set
        binary = spec.check_bin if spec.check_bin else spec.name
        if shutil.which(binary) is not None:
            return True
        # For git tools: check if dest directory exists
        if spec.method == "git" and spec.git_dest:
            return Path(spec.git_dest).exists()
        return False

    def ensure_tools(self, tool_names: list[str]) -> list[InstallResult]:
        results: list[InstallResult] = []
        for name in tool_names:
            results.append(self._process_tool(name))
        return results

    def _process_tool(self, tool_name: str) -> InstallResult:
        if self.check_installed(tool_name):
            return InstallResult(tool=tool_name, status="already_installed")

        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if spec is None:
            msg = f"No install spec for '{tool_name}'"
            self._logger.warning(f"[installer] {msg}")
            return InstallResult(tool=tool_name, status="not_installed", message=msg)

        if not self._ask_permission(tool_name, spec):
            return InstallResult(tool=tool_name, status="skipped", message="User declined.")

        return self._install_and_verify(spec)

    def _ask_permission(self, tool_name: str, spec: ToolInstallSpec) -> bool:
        if self._auto_approve:
            return True
        try:
            ans = input(f"\n[HackEmpire X] '{tool_name}' missing. Install via {spec.method}? (y/n): ").strip().lower()
        except (EOFError, OSError):
            return False
        return ans in ("y", "yes")

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
            elif spec.method == "curl":
                self._run_curl(spec)
        except Exception as exc:
            msg = f"Installation failed: {exc}"
            self._logger.error(f"[installer] '{spec.name}': {msg}")
            return InstallResult(tool=spec.name, status="failed", message=msg)

        if self.check_installed(spec.name):
            self._logger.success(f"[installer] '{spec.name}' installed.")
            return InstallResult(tool=spec.name, status="installed")

        # For git tools, dest existing = success even without binary on PATH
        if spec.method == "git" and spec.git_dest and Path(spec.git_dest).exists():
            self._logger.success(f"[installer] '{spec.name}' cloned to {spec.git_dest}.")
            return InstallResult(tool=spec.name, status="installed", message=f"Cloned to {spec.git_dest}")

        msg = "Binary not found on PATH after install."
        self._logger.warning(f"[installer] '{spec.name}': {msg}")
        return InstallResult(tool=spec.name, status="failed", message=msg)

    def _run_apt(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess(["sudo", "apt-get", "install", "-y", "--no-install-recommends", spec.package], spec.name)

    def _run_pip(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess([sys.executable, "-m", "pip", "install", "--quiet", spec.package], spec.name)

    def _run_git(self, spec: ToolInstallSpec) -> None:
        dest = spec.git_dest or f"/opt/{spec.name}"
        dest_path = Path(dest)
        # Skip if already cloned — fixes "destination path already exists" error
        if dest_path.exists():
            self._logger.info(f"[installer] '{spec.name}' already cloned at {dest} — skipping.")
            return
        # Use sudo for /opt/ paths
        cmd = (["sudo"] if dest.startswith("/opt") else []) + ["git", "clone", "--depth=1", spec.package, dest]
        self._run_subprocess(cmd, spec.name)

    def _run_go(self, spec: ToolInstallSpec) -> None:
        # naabu needs libpcap-dev
        if spec.name == "naabu":
            subprocess.run(["sudo", "apt-get", "install", "-y", "libpcap-dev"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        env = {**os.environ, "GOPATH": os.environ.get("GOPATH", str(Path.home() / "go"))}
        self._run_subprocess(["go", "install", spec.package], spec.name, env=env)

    def _run_gem(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess(["gem", "install", spec.package], spec.name)

    def _run_curl(self, spec: ToolInstallSpec) -> None:
        """Download a .tar.gz binary release and extract to /usr/local/bin."""
        import tempfile, tarfile
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tool.tar.gz"
            self._run_subprocess(["curl", "-sSL", "-o", str(archive), spec.package], spec.name)
            with tarfile.open(archive) as tf:
                # Extract only the binary (first executable file)
                for member in tf.getmembers():
                    if member.isfile() and not member.name.endswith((".md", ".txt", ".sh")):
                        member.name = Path(member.name).name
                        tf.extract(member, tmp)
                        bin_path = Path(tmp) / member.name
                        dest = Path("/usr/local/bin") / (spec.check_bin or spec.name)
                        try:
                            shutil.copy2(str(bin_path), str(dest))
                            dest.chmod(0o755)
                        except PermissionError:
                            subprocess.run(["sudo", "cp", str(bin_path), str(dest)], check=True)
                            subprocess.run(["sudo", "chmod", "+x", str(dest)], check=True)
                        break

    def _run_subprocess(self, cmd: list[str], tool_name: str, env: dict | None = None) -> None:
        self._logger.info(f"[installer] {shlex.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, env=env)
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"exit {result.returncode}: {stderr[:400]}")
