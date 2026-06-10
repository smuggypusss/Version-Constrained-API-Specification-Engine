from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from vcase.providers.base import ApiIndex, ApiParameter, ApiSignature
from vcase.service.ast_parser import AstParser

logger = logging.getLogger(__name__)

# Default disk cache location: ~/.cache/vcase/{package}/{version}/api_index.json
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "vcase"


class ApiIndexCache:
    """
    Two-layer cache for ApiIndex objects.

    Layer 1 — In-memory dict keyed by (package, version).
              Zero cost after the first hit in a process lifetime.

    Layer 2 — Disk cache at ~/.cache/vcase/{package}/{version}/api_index.json.
              Survives process restarts. Built once per unique package+version.

    On a full cache miss the service:
        1. Downloads the .whl or .tar.gz from PyPI.
        2. Extracts it to a temp directory.
        3. Runs AstParser over every .py file.
        4. Serialises the resulting ApiIndex to disk.
        5. Returns the ApiIndex and stores it in memory.
    """

    def __init__(self, http_client: httpx.AsyncClient, cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
        self._client = http_client
        self._cache_dir = cache_dir
        self._memory: dict[tuple[str, str], ApiIndex] = {}
        self._adapter = AstParser()

    # ── Public API ────────────────────────────────────────────────────────────

    async def get(self, package: str, version: str) -> ApiIndex | None:
        """
        Main entry point.
        Returns an ApiIndex for the given package+version, or None on failure.
        Checks memory → disk → network in that order.
        """
        index = self._check_memory(package, version)
        if index:
            logger.info(f"Cache HIT (memory) for {package}@{version}")
            return index

        index = self._check_disk(package, version)
        if index:
            logger.info(f"Cache HIT (disk) for {package}@{version}")
            self._memory[(package, version)] = index
            return index

        logger.info(f"Cache MISS for {package}@{version}. Fetching and parsing...")
        index = await self._fetch_and_parse(package, version)
        if index:
            self._memory[(package, version)] = index
            self._save_to_disk(package, version, index)
            return index

        return None

    # ── Cache Layers ─────────────────────────────────────────────────────────

    def _check_memory(self, package: str, version: str) -> ApiIndex | None:
        """
        Layer 1 check.
        Returns the cached ApiIndex if present, else None.
        """
        return self._memory.get((package, version))

    def _check_disk(self, package: str, version: str) -> ApiIndex | None:
        """
        Layer 2 check.
        Reads ~/.cache/vcase/{package}/{version}/api_index.json if it exists.
        Deserialises and returns an ApiIndex, or None if not found.
        """
        path = self._cache_dir / package / version / "api_index.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Failed to read disk cache at {path}: {e}")
            return None

    def _save_to_disk(self, package: str, version: str, index: ApiIndex) -> None:
        """
        Serialises an ApiIndex to JSON and writes it to the disk cache.
        Creates parent directories as needed.
        """
        path = self._cache_dir / package / version / "api_index.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = self._serialize(index)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write disk cache to {path}: {e}")

    # ── Network + Parsing ────────────────────────────────────────────────────

    async def _fetch_and_parse(self, package: str, version: str) -> ApiIndex | None:
        """
        Full cache-miss path.
        """
        url = await self._get_download_url(package, version)
        if not url:
            logger.warning(f"Could not find download URL for {package}@{version}")
            return None

        archive_bytes = await self._download_archive(url)
        if not archive_bytes:
            logger.warning(f"Could not download package archive from {url}")
            return None

        try:
            return self._extract_and_parse(archive_bytes, package, version)
        except Exception as e:
            logger.error(f"Failed to extract and parse archive for {package}@{version}: {e}")
            return None

    async def _get_download_url(self, package: str, version: str) -> str | None:
        """
        Queries https://pypi.org/pypi/{package}/{version}/json
        and extracts the best download URL:
            - Prefers .whl (zip format, faster to extract)
            - Falls back to .tar.gz
        Returns the URL string, or None if not found.
        """
        url = f"https://pypi.org/pypi/{package}/{version}/json"
        try:
            resp = await self._client.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            urls = resp.json().get("urls", [])
            for u in urls:
                if u.get("filename", "").endswith(".whl"):
                    return u["url"]
            for u in urls:
                if u.get("filename", "").endswith(".tar.gz"):
                    return u["url"]
        except Exception as e:
            logger.error(f"Error querying PyPI for download URL of {package}@{version}: {e}")
        return None

    async def _download_archive(self, url: str) -> bytes | None:
        """
        Downloads the archive at the given URL and returns its raw bytes.
        Returns None on any network failure.
        """
        try:
            resp = await self._client.get(url, timeout=60)
            if resp.status_code != 200:
                logger.warning(f"Failed to download archive from {url} (status={resp.status_code})")
                return None
            return resp.content
        except Exception as e:
            logger.error(f"Error downloading package archive from {url}: {e}")
        return None

    def _extract_and_parse(self, archive_bytes: bytes, package: str, version: str) -> ApiIndex:
        """
        Extracts the archive (auto-detects .whl vs .tar.gz from content).
        Runs AstParser.parse_file() over every .py file in the extracted tree.
        Aggregates all CallIR/function signatures into a single ApiIndex.
        """
        import io
        import zipfile
        import tarfile
        import tempfile
        from pathlib import Path

        all_signatures: list[ApiSignature] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            try:
                if zipfile.is_zipfile(io.BytesIO(archive_bytes)):
                    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                        zf.extractall(tmpdir)
                else:
                    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tf:
                        tf.extractall(tmpdir)
            except Exception as e:
                logger.error(f"Failed to extract archive for {package}@{version}: {e}")
                return ApiIndex(package=package, version=version, signatures=())

            # Find the main package directory
            package_dir = None
            for p in tmpdir_path.glob(f"**/{package}"):
                if p.is_dir() and (p / "__init__.py").exists():
                    package_dir = p
                    break
            if not package_dir:
                for p in tmpdir_path.glob("**/__init__.py"):
                    package_dir = p.parent
                    break
            if not package_dir:
                package_dir = tmpdir_path

            # Walk package_dir and parse python files
            for py_file in package_dir.glob("**/*.py"):
                try:
                    file_index = self._adapter.parse_file(package, version, py_file)
                    all_signatures.extend(file_index.signatures)
                except Exception as e:
                    logger.warning(f"Error parsing AST of {py_file} under package {package}: {e}")

        return ApiIndex(
            package=package,
            version=version,
            signatures=tuple(all_signatures)
        )

    # ── Serialisation ────────────────────────────────────────────────────────

    def _serialize(self, index: ApiIndex) -> dict:
        """
        Converts an ApiIndex (frozen dataclass) to a JSON-serialisable dict.
        """
        return {
            "package": index.package,
            "version": index.version,
            "signatures": [
                {
                    "qualified_name": sig.qualified_name,
                    "return_type": sig.return_type,
                    "available_since": sig.available_since,
                    "deprecated": sig.deprecated,
                    "deprecation_note": sig.deprecation_note,
                    "parameters": [
                        {
                            "name": param.name,
                            "type_hint": param.type_hint,
                            "required": param.required,
                            "description": param.description
                        }
                        for param in sig.parameters
                    ]
                }
                for sig in index.signatures
            ]
        }

    def _deserialize(self, data: dict) -> ApiIndex:
        """
        Reconstructs an ApiIndex from a dict loaded from disk.
        """
        signatures = []
        for sig_data in data.get("signatures", []):
            parameters = []
            for param_data in sig_data.get("parameters", []):
                parameters.append(ApiParameter(
                    name=param_data["name"],
                    type_hint=param_data["type_hint"],
                    required=param_data["required"],
                    description=param_data.get("description", "")
                ))
            signatures.append(ApiSignature(
                qualified_name=sig_data["qualified_name"],
                parameters=tuple(parameters),
                return_type=sig_data["return_type"],
                available_since=sig_data.get("available_since", ""),
                deprecated=sig_data.get("deprecated", False),
                deprecation_note=sig_data.get("deprecation_note", "")
            ))
        return ApiIndex(
            package=data["package"],
            version=data["version"],
            signatures=tuple(signatures)
        )
