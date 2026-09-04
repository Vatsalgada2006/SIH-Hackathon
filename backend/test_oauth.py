import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from starlette.requests import Request
from starlette.datastructures import URL, Headers

# Create a mock request with no authorization header
class MockRequest:
    def __init__(self):
        self.url = URL("http://example.com")
        self.headers = Headers({})
    
    def __getitem__(self, key):
        return self.headers[key]

# Create the oauth2_scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def test_oauth():
    try:
        # Create a mock request
        request = MockRequest()
        # Try to get the token
        token = await oauth2_scheme(request)
        print(f"Token: {token}")
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
        if hasattr(e, 'status_code'):
            print(f"Status code: {e.status_code}")
        if hasattr(e, 'detail'):
            print(f"Detail: {e.detail}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_oauth())
