from __future__ import annotations

import logging
from pathlib import Path
from vcase.providers.base import ApiIndex, ApiSignature
from vcase.service.ast_parser import AstParser

logger = logging.getLogger(__name__)


class WorkspaceScanner:
    """
    Scans the local repository to build an AST index of user-defined python modules,
    classes, and functions. This allows generating and validating code in interconnected codebases.
    """

    def __init__(self, ast_parser: AstParser | None = None) -> None:
        self._ast_parser = ast_parser or AstParser()

    def get_module_name(self, repo_path: Path, filepath: Path) -> str:
        """
        Determines the module import path for a given file relative to the repo root.
        e.g., app/services/db.py -> app.services.db
        """
        try:
            rel_path = filepath.resolve().relative_to(repo_path.resolve())
            parts = list(rel_path.parts)
            if parts:
                # Remove extension
                parts[-1] = Path(parts[-1]).stem
            if parts and parts[-1] == "__init__":
                # Drop __init__ for package imports
                parts.pop()
            return ".".join(parts)
        except Exception as e:
            logger.warning(f"Could not resolve module name for {filepath}: {e}")
            return filepath.stem

    def scan(self, repo_path: Path, max_files: int = 150) -> tuple[ApiIndex, list[str]]:
        """
        Scans all Python files in the workspace (excluding standard virtualenv and build paths),
        extracts signatures, and collects top-level module names.
        """
        resolved_repo = repo_path.resolve()
        py_files: list[Path] = []

        ignore_dirs = {
            ".git", ".venv", "venv", "env", ".pytest_cache", ".idea", ".vscode",
            "build", "dist", "__pycache__", "node_modules"
        }

        # Recursive traversal ignoring specfied paths
        def traverse(current_dir: Path):
            if len(py_files) >= max_files:
                return
            try:
                for entry in current_dir.iterdir():
                    if entry.is_dir():
                        if entry.name in ignore_dirs or entry.name.startswith("."):
                            continue
                        traverse(entry)
                    elif entry.is_file() and entry.suffix == ".py":
                        py_files.append(entry)
                        if len(py_files) >= max_files:
                            return
            except Exception as e:
                logger.warning(f"Error traversing directory {current_dir}: {e}")

        traverse(resolved_repo)

        all_signatures: list[ApiSignature] = []
        top_level_modules = set()

        for filepath in py_files:
            module_name = self.get_module_name(resolved_repo, filepath)
            if not module_name:
                continue

            # Track top-level module names for validators (e.g. 'app' from 'app.services.db')
            parts = module_name.split(".")
            if parts and parts[0]:
                top_level_modules.add(parts[0])

            # Extract signatures using the customized AstParser
            file_index = self._ast_parser.parse_file(
                package_name="local_workspace",
                package_version="0.1.0",
                filepath=filepath,
                module_prefix=module_name
            )
            all_signatures.extend(file_index.signatures)

        logger.info(f"Workspace scan completed. Indexed {len(py_files)} files, found {len(all_signatures)} signatures.")

        workspace_index = ApiIndex(
            package="local_workspace",
            version="0.1.0",
            signatures=tuple(all_signatures)
        )

        return workspace_index, list(top_level_modules)
