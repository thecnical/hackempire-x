"""
ToolInstaller — HackEmpire X v4 tool installation engine.

Covers all v3 + v4 tools:
  - v4 recon:       theHarvester, recon-ng, dnsenum, fierce
  - v4 enum:        wpscan, wpprobe, joomscan
  - v4 vuln:        sstimap, zaproxy, semgrep
  - v4 external:    metasploit (msfconsole), ysoserial, certipy-ad
  - v4 post_exploit: adaptix-c2, atomic-operator, pypykatz, pspy, evil-winrm

Install method notes:
  - git tools: check_installed returns True if /opt/toolname dir exists
  - apt uses sudo; go uses GOPATH; pip installs to user site-packages
  - naabu: installs libpcap-dev first
  - ysoserial: curl download of JAR
  - pspy: curl download of binary
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
    name: str
    method: InstallMethod
    package: str
    check_bin: Optional[str] = None   # binary name to check on PATH
    git_dest: Optional[str] = None    # /opt/toolname for git clones
    extra_args: list[str] = field(default_factory=list)


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
    "metasploit":    ToolInstallSpec("metasploit",    "apt", "metasploit-framework", check_bin="msfconsole"),
    "responder":     ToolInstallSpec("responder",     "apt", "responder"),
    "wafw00f":       ToolInstallSpec("wafw00f",       "apt", "wafw00f"),
    "masscan":       ToolInstallSpec("masscan",       "apt", "masscan"),
    "enum4linux-ng": ToolInstallSpec("enum4linux-ng", "apt", "enum4linux", check_bin="enum4linux"),
    # v4 — APT-available tools
    "theHarvester":  ToolInstallSpec("theHarvester",  "apt", "theharvester",  check_bin="theHarvester"),
    "dnsenum":       ToolInstallSpec("dnsenum",       "apt", "dnsenum"),
    "fierce":        ToolInstallSpec("fierce",        "apt", "fierce"),
    "wpscan":        ToolInstallSpec("wpscan",        "apt", "wpscan"),
    "joomscan":      ToolInstallSpec("joomscan",      "apt", "joomscan"),
    "zaproxy":       ToolInstallSpec("zaproxy",       "apt", "zaproxy",       check_bin="zaproxy"),
    "evil-winrm":    ToolInstallSpec("evil-winrm",    "gem", "evil-winrm"),

    # ── Go ───────────────────────────────────────────────────────────────────
    "subfinder":         ToolInstallSpec("subfinder",         "go", "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
    "httpx":             ToolInstallSpec("httpx",             "go", "github.com/projectdiscovery/httpx/cmd/httpx@latest"),
    "dnsx":              ToolInstallSpec("dnsx",              "go", "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"),
    "shuffledns":        ToolInstallSpec("shuffledns",        "go", "github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest"),
    "nuclei":            ToolInstallSpec("nuclei",            "go", "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
    "naabu":             ToolInstallSpec("naabu",             "go", "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"),
    "interactsh-client": ToolInstallSpec("interactsh-client", "go", "github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest"),
    "katana":            ToolInstallSpec("katana",            "go", "github.com/projectdiscovery/katana/cmd/katana@latest"),
    "hakrawler":         ToolInstallSpec("hakrawler",         "go", "github.com/hakluke/hakrawler@latest"),
    "gospider":          ToolInstallSpec("gospider",          "go", "github.com/jaeles-project/gospider@latest"),
    "dalfox":            ToolInstallSpec("dalfox",            "go", "github.com/hahwul/dalfox/v2@latest"),
    "gau":               ToolInstallSpec("gau",               "go", "github.com/lc/gau/v2/cmd/gau@latest"),
    "waybackurls":       ToolInstallSpec("waybackurls",       "go", "github.com/tomnomnom/waybackurls@latest"),
    "cariddi":           ToolInstallSpec("cariddi",           "go", "github.com/edoardottt/cariddi/cmd/cariddi@latest"),
    "assetfinder":       ToolInstallSpec("assetfinder",       "go", "github.com/tomnomnom/assetfinder@latest"),
    "anew":              ToolInstallSpec("anew",              "go", "github.com/tomnomnom/anew@latest"),
    "qsreplace":         ToolInstallSpec("qsreplace",         "go", "github.com/tomnomnom/qsreplace@latest"),
    "chisel":            ToolInstallSpec("chisel",            "go", "github.com/jpillora/chisel@latest"),
    "ligolo-ng":         ToolInstallSpec("ligolo-ng",         "go", "github.com/nicocha30/ligolo-ng/cmd/proxy@latest", check_bin="proxy"),
    "afrog":             ToolInstallSpec("afrog",             "go", "github.com/zan8in/afrog/cmd/afrog@latest"),
    "jsluice":           ToolInstallSpec("jsluice",           "go", "github.com/BishopFox/jsluice/cmd/jsluice@latest"),
    "github-subdomains": ToolInstallSpec("github-subdomains", "go", "github.com/gwen001/github-subdomains@latest"),

    # ── pip (user site-packages) ──────────────────────────────────────────
    "arjun":          ToolInstallSpec("arjun",          "pip", "arjun"),
    "waymore":        ToolInstallSpec("waymore",        "pip", "waymore"),
    "sslyze":         ToolInstallSpec("sslyze",         "pip", "sslyze"),
    "bloodhound":     ToolInstallSpec("bloodhound",     "pip", "bloodhound",       check_bin="bloodhound-python"),
    "impacket":       ToolInstallSpec("impacket",       "pip", "impacket",         check_bin="impacket-secretsdump"),
    "netexec":        ToolInstallSpec("netexec",        "pip", "netexec",          check_bin="nxc"),
    "ldapdomaindump": ToolInstallSpec("ldapdomaindump", "pip", "ldapdomaindump"),
    # v4 pip tools
    "semgrep":        ToolInstallSpec("semgrep",        "pip", "semgrep"),
    "pypykatz":       ToolInstallSpec("pypykatz",       "pip", "pypykatz"),
    "certipy-ad":     ToolInstallSpec("certipy-ad",     "pip", "certipy-ad",       check_bin="certipy"),
    "atomic-operator":ToolInstallSpec("atomic-operator","pip", "atomic-operator",  check_bin="atomic-operator"),
    "recon-ng":       ToolInstallSpec("recon-ng",       "pip", "recon-ng",         check_bin="recon-ng"),
    "wpprobe":        ToolInstallSpec("wpprobe",        "pip", "wpprobe",          check_bin="wpprobe"),

    # ── git clone ─────────────────────────────────────────────────────────
    "xsstrike":    ToolInstallSpec("xsstrike",    "git", "https://github.com/s0md3v/XSStrike.git",            git_dest="/opt/xsstrike"),
    "commix":      ToolInstallSpec("commix",      "git", "https://github.com/commixproject/commix.git",       git_dest="/opt/commix"),
    "tplmap":      ToolInstallSpec("tplmap",      "git", "https://github.com/epinna/tplmap.git",              git_dest="/opt/tplmap"),
    "linpeas":     ToolInstallSpec("linpeas",     "git", "https://github.com/carlospolop/PEASS-ng.git",       git_dest="/opt/peass"),
    "testssl":     ToolInstallSpec("testssl",     "git", "https://github.com/drwetter/testssl.sh.git",        git_dest="/opt/testssl"),
    "dirsearch":   ToolInstallSpec("dirsearch",   "git", "https://github.com/maurosoria/dirsearch.git",       git_dest="/opt/dirsearch"),
    "ghauri":      ToolInstallSpec("ghauri",      "git", "https://github.com/r0oth3x49/ghauri.git",           git_dest="/opt/ghauri"),
    "paramspider": ToolInstallSpec("paramspider", "git", "https://github.com/devanshbatham/ParamSpider.git",  git_dest="/opt/paramspider"),
    "kiterunner":  ToolInstallSpec("kiterunner",  "git", "https://github.com/assetnote/kiterunner.git",       git_dest="/opt/kiterunner"),
    # v4 git tools
    "sstimap":     ToolInstallSpec("sstimap",     "git", "https://github.com/vladko312/SSTImap.git",          git_dest="/opt/sstimap"),
    "adaptix-c2":  ToolInstallSpec("adaptix-c2",  "git", "https://github.com/Adaptix-Framework/AdaptixC2.git", git_dest="/opt/adaptix-c2"),

    # ── curl binary download ──────────────────────────────────────────────
    "trufflehog": ToolInstallSpec(
        "trufflehog", "curl",
        "https://github.com/trufflesecurity/trufflehog/releases/latest/download/trufflehog_linux_amd64.tar.gz",
    ),
    # v4 curl tools
    "ysoserial": ToolInstallSpec(
        "ysoserial", "curl",
        "https://github.com/frohoff/ysoserial/releases/latest/download/ysoserial-all.jar",
        check_bin="ysoserial",
    ),
    "pspy": ToolInstallSpec(
        "pspy", "curl",
        "https://github.com/DominicBreuker/pspy/releases/latest/download/pspy64",
        check_bin="pspy64",
    ),
}


@dataclass
class InstallResult:
    tool: str
    status: Literal["installed", "not_installed", "skipped", "already_installed", "failed"]
    message: str = ""


class ToolInstaller:

    def __init__(self, *, logger: Logger, mode: str = "pro", auto_approve: bool = False) -> None:
        self._logger = logger
        self._mode = mode.lower()
        self._auto_approve = auto_approve

    def check_installed(self, tool_name: str) -> bool:
        """
        Returns True if the tool is available.
        - git tools: checks if /opt/toolname directory exists
        - curl JAR tools (ysoserial): checks /opt/ysoserial/ysoserial.jar
        - curl binary tools (pspy): checks PATH for pspy64/pspy
        - all others: checks binary on PATH
        """
        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if spec is None:
            return shutil.which(tool_name) is not None

        if spec.method == "git":
            dest = spec.git_dest or f"/opt/{spec.name}"
            return Path(dest).exists()

        # ysoserial is a JAR — check the jar file directly
        if tool_name == "ysoserial":
            return (
                Path("/opt/ysoserial/ysoserial.jar").exists()
                or Path("/usr/share/ysoserial/ysoserial.jar").exists()
                or shutil.which("ysoserial") is not None
            )

        # pspy: check pspy64 or pspy32 or /opt/pspy/pspy64
        if tool_name == "pspy":
            return (
                shutil.which("pspy64") is not None
                or shutil.which("pspy32") is not None
                or shutil.which("pspy") is not None
                or Path("/opt/pspy/pspy64").exists()
            )

        binary = spec.check_bin if spec.check_bin else spec.name
        return shutil.which(binary) is not None

    def get_install_status(self, tool_name: str) -> str:
        spec = TOOL_INSTALL_SPECS.get(tool_name)
        if self.check_installed(tool_name):
            if spec and spec.method == "git":
                return f"installed ({spec.git_dest})"
            return "installed"
        return "missing"

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
            return InstallResult(tool=tool_name, status="not_installed", message=f"No spec for '{tool_name}'")
        if not self._ask_permission(tool_name, spec):
            return InstallResult(tool=tool_name, status="skipped", message="User declined.")
        return self._install_and_verify(spec)

    def _ask_permission(self, tool_name: str, spec: ToolInstallSpec) -> bool:
        if self._auto_approve:
            return True
        # Also respect env var for non-interactive / scan mode
        if os.environ.get("HACKEMPIRE_AUTO_APPROVE", "").lower() in ("1", "true", "yes"):
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

        msg = "Not found after install."
        self._logger.warning(f"[installer] '{spec.name}': {msg}")
        return InstallResult(tool=spec.name, status="failed", message=msg)

    def _run_apt(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess(["sudo", "apt-get", "install", "-y", "--no-install-recommends", spec.package], spec.name)

    def _run_pip(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess([sys.executable, "-m", "pip", "install", "--quiet", "--user", spec.package], spec.name)

    def _run_git(self, spec: ToolInstallSpec) -> None:
        dest = spec.git_dest or f"/opt/{spec.name}"
        if Path(dest).exists():
            self._logger.info(f"[installer] '{spec.name}' already at {dest} — skipping.")
            return
        cmd = (["sudo"] if dest.startswith("/opt") else []) + ["git", "clone", "--depth=1", spec.package, dest]
        self._run_subprocess(cmd, spec.name)

    def _run_go(self, spec: ToolInstallSpec) -> None:
        if spec.name == "naabu":
            subprocess.run(["sudo", "apt-get", "install", "-y", "libpcap-dev"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        env = {**os.environ, "GOPATH": os.environ.get("GOPATH", str(Path.home() / "go"))}
        self._run_subprocess(["go", "install", spec.package], spec.name, env=env)

    def _run_gem(self, spec: ToolInstallSpec) -> None:
        self._run_subprocess(["gem", "install", spec.package], spec.name)

    def _run_curl(self, spec: ToolInstallSpec) -> None:
        import tempfile
        import tarfile

        url = spec.package
        is_jar = url.endswith(".jar")
        is_binary = not url.endswith((".tar.gz", ".tgz", ".zip"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            if is_jar:
                # ysoserial: download JAR to /opt/ysoserial/
                jar_dir = Path("/opt/ysoserial")
                jar_dest = jar_dir / "ysoserial.jar"
                try:
                    jar_dir.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    subprocess.run(["sudo", "mkdir", "-p", str(jar_dir)], check=True)
                self._run_subprocess(["curl", "-sSL", "-o", str(jar_dest), url], spec.name)
                try:
                    jar_dest.chmod(0o644)
                except PermissionError:
                    subprocess.run(["sudo", "chmod", "644", str(jar_dest)], check=True)
                # Create wrapper script
                wrapper = Path("/usr/local/bin/ysoserial")
                wrapper_content = f'#!/usr/bin/env bash\nexec java -jar {jar_dest} "$@"\n'
                try:
                    wrapper.write_text(wrapper_content)
                    wrapper.chmod(0o755)
                except PermissionError:
                    tmp_wrapper = tmp_path / "ysoserial"
                    tmp_wrapper.write_text(wrapper_content)
                    subprocess.run(["sudo", "cp", str(tmp_wrapper), str(wrapper)], check=True)
                    subprocess.run(["sudo", "chmod", "+x", str(wrapper)], check=True)
                return

            if is_binary and not url.endswith((".tar.gz", ".tgz")):
                # pspy: download raw binary
                bin_name = spec.check_bin or spec.name
                dest_path = Path("/usr/local/bin") / bin_name
                tmp_bin = tmp_path / bin_name
                self._run_subprocess(["curl", "-sSL", "-o", str(tmp_bin), url], spec.name)
                try:
                    shutil.copy2(str(tmp_bin), str(dest_path))
                    dest_path.chmod(0o755)
                except PermissionError:
                    subprocess.run(["sudo", "cp", str(tmp_bin), str(dest_path)], check=True)
                    subprocess.run(["sudo", "chmod", "+x", str(dest_path)], check=True)
                return

            # tar.gz archive (trufflehog etc.)
            archive = tmp_path / "tool.tar.gz"
            self._run_subprocess(["curl", "-sSL", "-o", str(archive), url], spec.name)
            with tarfile.open(archive) as tf:
                for member in tf.getmembers():
                    if member.isfile() and not member.name.endswith((".md", ".txt", ".sh")):
                        member.name = Path(member.name).name
                        tf.extract(member, tmp)
                        bin_path = tmp_path / member.name
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
