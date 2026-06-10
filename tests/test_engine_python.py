import asyncio
import logging
import sys
import os
from pathlib import Path
import httpx

# Fix the path before importing our internal modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
# 1. Import exactly the names we gave our classes
from vcase.api.pypi_client import PypiClient
from vcase.providers.python_provider import PythonProvider
from vcase.service.resolver import DependencyResolver

@pytest.mark.asyncio
async def test_engine_python():
    logging.basicConfig(level=logging.INFO)
    
    # 2. Assign the client to a variable!
    # (If you don't, you can't close it later!)
    http_client=httpx.AsyncClient()
    api_client = PypiClient(client=http_client)
    
    # 3. Pass the client variable into the provider
    provider = PythonProvider(api_client)
    
    # 4. Our class was named DependencyResolver, and it takes providers in its initialization
    resolver = DependencyResolver(providers=[provider])
    
    repo_path = Path(__file__).parent
    
    # 5. Call the actual method we built: "resolve"
    print("Executing resolution pipeline...")
    resolved_deps = await resolver.resolve(repo_path)
    
    # 6. We need to print them to prove it worked!
    for dep in resolved_deps:
         print(f"{dep.name}: {dep.version} ({dep.resolution_tier.name})")
         
    # 7. Now we safely close the variable we created in step 2
    await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_engine_python())
