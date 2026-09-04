import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Mock dependencies
class MockSession:
    pass

async def get_mock_db():
    yield MockSession()

# Original dependency pattern (should work)
async def original_dependency(token: str = Depends(lambda: "test_token"), db: AsyncSession = Depends(get_mock_db)):
    return {"token": token, "db": db}

# Override that causes the issue (mimicking the test's incorrect override)
async def problematic_override(token: str, db: AsyncSession):  # NO DEFAULT VALUES
    return {"token": token, "db": db}

# Override that should work (mimicking correct override pattern)
async def correct_override(token: str = "test_token", db: AsyncSession = Depends(get_mock_db)):
    return {"token": token, "db": db}

app = FastAPI()

# Test with original dependency pattern
@app.get("/original")
async def original_endpoint(result: dict = Depends(original_dependency)):
    return result

# Test with problematic override (should fail)
app.dependency_overrides[original_dependency] = problematic_override
@app.get("/problematic")
async def problematic_endpoint(result: dict = Depends(original_dependency)):
    return result

# Test with correct override (should work)
# app.dependency_overrides[original_dependency] = correct_override
# @app.get("/correct")
# async def correct_endpoint(result: dict = Depends(original_dependency)):
#     return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
