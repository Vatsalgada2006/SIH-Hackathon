import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_roads_endpoint():
    # Try to access the roads endpoint without authentication
    # This should fail with 401 or 403, not with a FastAPI error
    response = client.patch(
        "/api/v1/roads/segments/1/status",
        json={"status": "BLOCKED", "reason": "Test reason"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 500:
        print("ERROR: Got 500 Internal Server Error")
        # Try to get more details
        try:
            error_info = response.json()
            print(f"Error details: {error_info}")
        except:
            print("Could not parse error as JSON")

if __name__ == "__main__":
    test_roads_endpoint()
