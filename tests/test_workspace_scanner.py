from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from vcase.main import app
from vcase.service.workspace_scanner import WorkspaceScanner
from vcase.providers.base import ApiIndex, ValidationResult

client = TestClient(app)


def test_get_module_name():
    scanner = WorkspaceScanner()
    repo_path = Path("/workspace/my_project")
    
    # Standard file
    filepath = Path("/workspace/my_project/app/services/db.py")
    assert scanner.get_module_name(repo_path, filepath) == "app.services.db"
    
    # Init file
    filepath = Path("/workspace/my_project/app/models/__init__.py")
    assert scanner.get_module_name(repo_path, filepath) == "app.models"


def test_workspace_scanning():
    # Set up a temporary workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        
        # Create a package module
        pkg_dir = repo_path / "app"
        pkg_dir.mkdir()
        
        code = """
def calculate_price(qty: int, price: float = 10.0) -> float:
    return qty * price

class OrderService:
    def create_order(self, order_id: str) -> bool:
        return True
"""
        (pkg_dir / "services.py").write_text(code, encoding="utf-8")
        
        scanner = WorkspaceScanner()
        workspace_idx, top_level_modules = scanner.scan(repo_path)
        
        assert "app" in top_level_modules
        assert workspace_idx.package == "local_workspace"
        
        # Verify extracted signatures
        signatures = {sig.qualified_name: sig for sig in workspace_idx.signatures}
        assert "app.services.calculate_price" in signatures
        assert "app.services.OrderService.create_order" in signatures
        
        # Check params
        calc_sig = signatures["app.services.calculate_price"]
        assert calc_sig.return_type == "float"
        assert len(calc_sig.parameters) == 2
        assert calc_sig.parameters[0].name == "qty"
        assert calc_sig.parameters[0].type_hint == "int"


def test_context_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Create a mock requirements file to resolve
        (repo_path / "requirements.txt").write_text("fastapi>=0.110.0", encoding="utf-8")
        
        response = client.post("/api/v1/context", json={
            "prompt": "Write a fastapi route handler",
            "repo_path": str(repo_path)
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "context_prompt" in data
        assert "resolved_dependencies" in data
        assert any(dep["name"] == "fastapi" for dep in data["resolved_dependencies"])


def test_validate_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Create a mock internal module
        app_dir = repo_path / "app"
        app_dir.mkdir()
        (app_dir / "models.py").write_text("class User: pass", encoding="utf-8")
        
        # Test code that imports from local module
        code_with_local_import = """
from app.models import User
print(User)
"""
        response = client.post("/api/v1/validate", json={
            "code": code_with_local_import,
            "repo_path": str(repo_path)
        })
        
        assert response.status_code == 200
        data = response.json()
        print("\nDEBUG VALIDATE RESPONSE:", data)
        assert data["passed"] is True
        assert len(data["violations"]) == 0
