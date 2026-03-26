"""
DependencyResolver — orchestrates installation of all HackEmpire X tools.

Fixes:
- git clone: skip if dest already exists
- pip tools: installed into isolated venvs, binary symlinked to ~/.local/bin
- crackmapexec → netexec (maintained fork)
- ghauri/paramspider: git clone instead of pip
- trufflehog/kiterunner: curl binary download
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from installer.tool_installer import ToolInstaller, TOOL_INSTALL_SPECS, InstallResult
from installer.tool_venv_manager import ToolVenvManager
from utils.logger import Logger

# Pip tools that need isolated venvs + their correct PyPI packages + binary names
PIP_VENV_TOOLS: dict[str, dict] = {
    "arjun":         {"packages": ["arjun"],           "bin": "arjun"},
    "waymore":       {"packages": ["waymore"],          "bin": "waymore"},
    "sslyze":        {"packages": ["sslyze"],           "bin": "sslyze"},
    "bloodhound":    {"packages": ["bloodhound"],       "bin": "bloodhound-python"},
    "impacket":      {"packages": ["impacket"],         "bin": "impacket-secretsdump"},
    "netexec":       {"packages": ["netexec"],          "bin": "nxc"},
    "ldapdomaindump":{"packages": ["ldapdomaindump"],   "bin": "ldapdomaindump"},
}


class DependencyResolver:

    def __init__(self, logger: Logger, auto_approve: bool = False) -> None:
        self._logger = logger
        self._auto_approve = auto_approve
        self._installer = ToolInstaller(logger=logger, auto_approve=auto_approve)
        self._venv_manager = ToolVenvManager(logger=logger)

    def resolve(self, tool_names: list[str]) -> dict[str, str]:
        results: dict[str, str] = {}

        apt_tools  = self._filter_by_method(tool_names, "apt")
        go_tools   = self._filter_by_method(tool_names, "go")
        gem_tools  = self._filter_by_method(tool_names, "gem")
        git_tools  = self._filter_by_method(tool_names, "git")
        pip_tools  = self._filter_by_method(tool_names, "pip")
        curl_tools = self._filter_by_method(tool_names, "curl")

        # Unknown tools
        known = set(apt_tools + go_tools + gem_tools + git_tools + pip_tools + curl_tools)
        for name in tool_names:
            if name not in known:
                self._logger.warning(f"[resolver] No spec for '{name}' — skipping.")
                results[name] = "skipped"

        # 1. APT batch install
        if apt_tools:
            self._install_apt_group(apt_tools, results)

        # 2. Go tools
        if go_tools:
            if not shutil.which("go"):
                self._logger.warning("[resolver] 'go' not on PATH — skipping Go tools.")
                for n in go_tools: results[n] = "skipped"
            else:
                for n in go_tools:
                    results[n] = self._install_single(n)

        # 3. Gem tools
        if gem_tools:
            if not shutil.which("ruby"):
                for n in gem_tools: results[n] = "skipped"
            else:
                for n in gem_tools:
                    results[n] = self._install_single(n)

        # 4. Git tools (skip if already cloned)
        for n in git_tools:
            results[n] = self._install_git_tool(n)

        # 5. Pip tools → isolated venvs
        for n in pip_tools:
            results[n] = self._install_pip_venv_tool(n)

        # 6. Curl binary downloads
        for n in curl_tools:
            results[n] = self._install_single(n)

        return results

    def install_system_packages(self, packages: list[str]) -> bool:
        if not packages:
            return True
        cmd = ["apt-get", "install", "-y", "--no-install-recommends"] + packages
        self._logger.info(f"[resolver] apt-get install: {packages}")
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
            if r.returncode != 0:
                self._logger.error(f"[resolver] apt-get failed: {r.stderr.decode(errors='replace')[:300]}")
                return False
            return True
        except Exception as exc:
            self._logger.error(f"[resolver] apt-get exception: {exc}")
            return False

    # ── Internal ─────────────────────────────────────────────────────────────

    def _filter_by_method(self, names: list[str], method: str) -> list[str]:
        return [n for n in names if n in TOOL_INSTALL_SPECS and TOOL_INSTALL_SPECS[n].method == method]

    def _install_apt_group(self, apt_tools: list[str], results: dict[str, str]) -> None:
        to_install, packages = [], []
        for n in apt_tools:
            if self._installer.check_installed(n):
                results[n] = "already_installed"
            else:
                to_install.append(n)
                packages.append(TOOL_INSTALL_SPECS[n].package)
        if not to_install:
            return
        ok = self.install_system_packages(packages)
        for n in to_install:
            results[n] = "installed" if (ok and self._installer.check_installed(n)) else "failed"

    def _install_single(self, name: str) -> str:
        if self._installer.check_installed(name):
            return "already_installed"
        res = self._installer.ensure_tools([name])
        return res[0].status if res else "failed"

    def _install_git_tool(self, name: str) -> str:
        spec = TOOL_INSTALL_SPECS.get(name)
        if spec is None:
            return "skipped"
        dest = Path(spec.git_dest) if spec.git_dest else Path(f"/opt/{name}")

        # Skip if already cloned — this is the key fix
        if dest.exists():
            self._logger.info(f"[resolver] '{name}' already at {dest} — skipping clone.")
            # Still try to install requirements into venv
            self._maybe_install_requirements(name, dest)
            return "already_installed"

        self._logger.info(f"[resolver] Cloning '{name}' to {dest}...")
        cmd = ["sudo", "git", "clone", "--depth=1", spec.package, str(dest)]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            if r.returncode != 0:
                err = r.stderr.decode(errors="replace").strip()
                self._logger.error(f"[resolver] clone '{name}' failed: {err[:300]}")
                return "failed"
        except Exception as exc:
            self._logger.error(f"[resolver] clone '{name}' exception: {exc}")
            return "failed"

        self._maybe_install_requirements(name, dest)
        return "installed"

    def _maybe_install_requirements(self, name: str, dest: Path) -> None:
        req = dest / "requirements.txt"
        if req.exists():
            pkgs = [l.strip() for l in req.read_text(errors="replace").splitlines()
                    if l.strip() and not l.startswith("#")]
            if pkgs:
                self._venv_manager.ensure_venv(name, pkgs)

    def _install_pip_venv_tool(self, name: str) -> str:
        """Install pip tool into isolated venv and symlink binary to ~/.local/bin."""
        spec = TOOL_INSTALL_SPECS.get(name)
        if spec is None:
            return "skipped"

        venv_info = PIP_VENV_TOOLS.get(name, {"packages": [spec.package], "bin": spec.check_bin or name})
        packages = venv_info["packages"]
        bin_name = venv_info["bin"]

        # Check if already installed
        if shutil.which(bin_name):
            self._logger.info(f"[resolver] '{name}' ({bin_name}) already on PATH.")
            return "already_installed"

        self._logger.info(f"[resolver] Installing '{name}' into isolated venv...")
        venv_python = self._venv_manager.ensure_venv(name, packages)
        if venv_python is None:
            return "failed"

        # Symlink the binary to ~/.local/bin so it's on PATH
        venv_bin_dir = venv_python.parent
        bin_src = venv_bin_dir / bin_name
        if bin_src.exists():
            local_bin = Path.home() / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            link = local_bin / bin_name
            try:
                if link.exists() or link.is_symlink():
                    link.unlink()
                link.symlink_to(bin_src)
                self._logger.success(f"[resolver] '{bin_name}' linked to {link}")
            except Exception as exc:
                self._logger.warning(f"[resolver] Could not symlink '{bin_name}': {exc}")

        return "installed"
