import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_simple():
    # Try to access a route that should exist
    response = client.get("/docs")  # FastAPI automatically adds this
    print(f"/docs Status: {response.status_code}")
    
    # Try to access our test endpoint if we can figure out how to import it
    # For now, just check if the app is working
    
if __name__ == "__main__":
    test_simple()
