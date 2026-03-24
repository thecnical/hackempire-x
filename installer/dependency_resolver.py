"""
DependencyResolver — orchestrates installation of all HackEmpire X tools.

Install order:
  1. System packages (apt) — abort remaining steps on failure
  2. Go tools — skipped if `go` not on PATH
  3. Ruby/gem tools — skipped if `ruby` not on PATH
  4. Git-cloned tools — installs requirements.txt into per-tool venv if present
  5. pip tools — installed into isolated venvs via ToolVenvManager
  6. reconftw — cloned and installed last via install.sh
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from installer.tool_installer import ToolInstaller, TOOL_INSTALL_SPECS
from installer.tool_venv_manager import ToolVenvManager
from utils.logger import Logger


# ---------------------------------------------------------------------------
# DependencyResolver
# ---------------------------------------------------------------------------

class DependencyResolver:
    """
    Resolves and installs all tools required by HackEmpire X.

    Usage:
        resolver = DependencyResolver(logger=logger, auto_approve=True)
        results = resolver.resolve(["nmap", "httpx", "xsstrike", "arjun"])
    """

    RECONFTW_REPO = "https://github.com/six2dez/reconftw.git"
    RECONFTW_DEST = "/opt/reconftw"

    def __init__(self, logger: Logger, auto_approve: bool = False) -> None:
        self._logger = logger
        self._auto_approve = auto_approve
        self._installer = ToolInstaller(logger=logger, auto_approve=auto_approve)
        self._venv_manager = ToolVenvManager(logger=logger)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, tool_names: list[str]) -> dict[str, str]:
        """
        Install all requested tools in the correct order.

        Returns a dict mapping tool_name -> status:
          "installed" | "already_installed" | "skipped" | "failed"
        """
        results: dict[str, str] = {}

        # Partition tools by install method
        apt_tools = self._filter_by_method(tool_names, "apt")
        go_tools = self._filter_by_method(tool_names, "go")
        gem_tools = self._filter_by_method(tool_names, "gem")
        git_tools = self._filter_by_method(tool_names, "git")
        pip_tools = self._filter_by_method(tool_names, "pip")

        # Separate reconftw from git tools — handled last
        reconftw_requested = "reconftw" in tool_names
        git_tools = [t for t in git_tools if t != "reconftw"]

        # Unknown tools (no spec)
        known = set(apt_tools + go_tools + gem_tools + git_tools + pip_tools)
        if reconftw_requested:
            known.add("reconftw")
        for name in tool_names:
            if name not in known:
                self._logger.warning(f"[resolver] No install spec for '{name}' — skipping.")
                results[name] = "skipped"

        # --- Step 1: apt (system packages) ---
        if apt_tools:
            apt_ok = self._install_apt_group(apt_tools, results)
            if not apt_ok:
                # Abort remaining steps
                remaining = [t for t in tool_names if t not in results]
                for name in remaining:
                    results[name] = "failed"
                self._logger.error("[resolver] System package install failed — aborting remaining steps.")
                return results

        # --- Step 2: Go tools ---
        if go_tools:
            if not shutil.which("go"):
                self._logger.warning("[resolver] 'go' not found on PATH — skipping Go tools.")
                for name in go_tools:
                    results[name] = "skipped"
            else:
                for name in go_tools:
                    results[name] = self._install_single(name)

        # --- Step 3: Ruby/gem tools ---
        if gem_tools:
            if not shutil.which("ruby"):
                self._logger.warning("[resolver] 'ruby' not found on PATH — skipping Ruby/gem tools.")
                for name in gem_tools:
                    results[name] = "skipped"
            else:
                for name in gem_tools:
                    results[name] = self._install_single(name)

        # --- Step 4: Git-cloned tools ---
        for name in git_tools:
            results[name] = self._install_git_tool(name)

        # --- Step 5: pip tools ---
        for name in pip_tools:
            results[name] = self._install_pip_tool(name)

        # --- Step 6: reconftw (last) ---
        if reconftw_requested:
            results["reconftw"] = self.install_reconftw()

        return results

    def install_system_packages(self, packages: list[str]) -> bool:
        """
        Run a single batched `apt-get install -y` for all *packages*.

        Returns True on success, False on any failure.
        """
        if not packages:
            return True

        cmd = ["apt-get", "install", "-y"] + packages
        self._logger.info(f"[resolver] apt-get install: {packages}")
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                self._logger.error(f"[resolver] apt-get failed (exit {result.returncode}): {stderr[:500]}")
                return False
            self._logger.success(f"[resolver] apt-get installed: {packages}")
            return True
        except Exception as exc:
            self._logger.error(f"[resolver] apt-get exception: {exc}")
            return False

    def install_reconftw(self) -> str:
        """
        Clone reconftw and run its install.sh script.

        Returns "installed" on success, "failed" on any error.
        """
        dest = Path(self.RECONFTW_DEST)

        # Clone if not already present
        if not dest.exists():
            self._logger.info(f"[resolver] Cloning reconftw to {dest}")
            try:
                result = subprocess.run(
                    ["git", "clone", self.RECONFTW_REPO, str(dest)],
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                )
                if result.returncode != 0:
                    stderr = result.stderr.decode(errors="replace").strip()
                    self._logger.error(f"[resolver] reconftw clone failed: {stderr[:500]}")
                    return "failed"
            except Exception as exc:
                self._logger.error(f"[resolver] reconftw clone exception: {exc}")
                return "failed"
        else:
            self._logger.info(f"[resolver] reconftw already cloned at {dest}")

        # Run install.sh
        install_script = dest / "install.sh"
        self._logger.info(f"[resolver] Running reconftw install.sh")
        try:
            result = subprocess.run(
                [str(install_script)],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1800,  # 30-minute cap for reconftw
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                self._logger.error(f"[resolver] reconftw install.sh failed: {stderr[:500]}")
                return "failed"
            self._logger.success("[resolver] reconftw installed successfully.")
            return "installed"
        except Exception as exc:
            self._logger.error(f"[resolver] reconftw install.sh exception: {exc}")
            return "failed"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filter_by_method(self, tool_names: list[str], method: str) -> list[str]:
        """Return tool names whose install spec matches *method*."""
        return [
            name for name in tool_names
            if name in TOOL_INSTALL_SPECS and TOOL_INSTALL_SPECS[name].method == method
        ]

    def _install_apt_group(self, apt_tools: list[str], results: dict[str, str]) -> bool:
        """
        Check which apt tools are already installed, batch-install the rest.
        Populates *results* for all apt tools. Returns False if batch install fails.
        """
        to_install: list[str] = []
        packages: list[str] = []

        for name in apt_tools:
            if self._installer.check_installed(name):
                self._logger.info(f"[resolver] '{name}' already installed.")
                results[name] = "already_installed"
            else:
                to_install.append(name)
                packages.append(TOOL_INSTALL_SPECS[name].package)

        if not to_install:
            return True

        ok = self.install_system_packages(packages)
        if not ok:
            for name in to_install:
                results[name] = "failed"
            return False

        # Verify each tool after batch install
        for name in to_install:
            if self._installer.check_installed(name):
                results[name] = "installed"
            else:
                self._logger.warning(f"[resolver] '{name}' not found on PATH after apt install.")
                results[name] = "failed"

        return True

    def _install_single(self, name: str) -> str:
        """Delegate to ToolInstaller for a single tool; return status string."""
        if self._installer.check_installed(name):
            return "already_installed"
        install_results = self._installer.ensure_tools([name])
        if not install_results:
            return "failed"
        return install_results[0].status

    def _install_git_tool(self, name: str) -> str:
        """
        Clone a git tool and, if requirements.txt exists in the clone dest,
        install dependencies into a per-tool venv via ToolVenvManager.
        """
        spec = TOOL_INSTALL_SPECS.get(name)
        if spec is None:
            return "skipped"

        # Check if already cloned
        dest = Path(spec.git_dest) if spec.git_dest else Path(f"/opt/{name}")
        if not dest.exists():
            self._logger.info(f"[resolver] Cloning '{name}' from {spec.package} to {dest}")
            try:
                result = subprocess.run(
                    ["git", "clone", spec.package, str(dest)],
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                )
                if result.returncode != 0:
                    stderr = result.stderr.decode(errors="replace").strip()
                    self._logger.error(f"[resolver] git clone '{name}' failed: {stderr[:500]}")
                    return "failed"
            except Exception as exc:
                self._logger.error(f"[resolver] git clone '{name}' exception: {exc}")
                return "failed"
        else:
            self._logger.info(f"[resolver] '{name}' already cloned at {dest}")

        # Install requirements.txt into venv if present
        req_file = dest / "requirements.txt"
        if req_file.exists():
            self._logger.info(f"[resolver] Installing requirements.txt for '{name}' into venv")
            pip_packages = self._read_requirements(req_file)
            venv_python = self._venv_manager.ensure_venv(name, pip_packages)
            if venv_python is None:
                self._logger.warning(f"[resolver] venv setup failed for '{name}'")
                return "failed"

        return "installed"

    def _install_pip_tool(self, name: str) -> str:
        """Install a pip tool into its isolated venv via ToolVenvManager."""
        spec = TOOL_INSTALL_SPECS.get(name)
        if spec is None:
            return "skipped"

        if self._installer.check_installed(name):
            return "already_installed"

        pip_packages = [spec.package]
        self._logger.info(f"[resolver] Installing pip tool '{name}' into venv")
        venv_python = self._venv_manager.ensure_venv(name, pip_packages)
        if venv_python is None:
            return "failed"
        return "installed"

    @staticmethod
    def _read_requirements(req_file: Path) -> list[str]:
        """Parse a requirements.txt, ignoring comments and blank lines."""
        packages: list[str] = []
        try:
            for line in req_file.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    packages.append(line)
        except Exception:
            pass
        return packages
