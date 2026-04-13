"""Custom build hook to build the frontend before packaging."""

import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    """Build the frontend using bun/npm before packaging."""

    PLUGIN_NAME = "frontend"

    def initialize(self, version: str, build_data: dict) -> None:
        """Build the frontend before the Python package is built.

        Parameters
        ----------
        version : str
            The build type ('standard' or 'editable'), not the package version.
        build_data : dict
            Build metadata passed by hatchling.

        Raises
        ------
        RuntimeError
            If the frontend directory or a package manager is not found.
        """
        app_dir = Path(self.root) / "frontend"

        if not app_dir.is_dir():
            msg = (
                f"Frontend directory not found: {app_dir}. "
                "Every build must include the frontend."
            )
            raise RuntimeError(msg)

        bun_path = shutil.which("bun")
        npm_path = shutil.which("npm")
        npx_path = shutil.which("npx")

        if bun_path:
            pkg_manager = "bun"
            install_cmd = [bun_path, "install"]
            build_cmd = [bun_path, "vite", "build"]
        elif npm_path and npx_path:
            pkg_manager = "npm"
            install_cmd = [npm_path, "install"]
            build_cmd = [npx_path, "vite", "build"]
        else:
            msg = "Neither bun nor npm found. Cannot build frontend."
            raise RuntimeError(msg)

        pkg_version = self.metadata.version
        self.app.display_info(
            f"Building frontend with {pkg_manager} (version={pkg_version})..."
        )

        env = os.environ.copy()
        subprocess.run(install_cmd, cwd=app_dir, check=True, env=env)  # noqa: S603

        env["VITE_APP_VERSION"] = pkg_version
        subprocess.run(build_cmd, cwd=app_dir, check=True, env=env)  # noqa: S603

        self.app.display_info("Frontend build complete.")
