import asyncio
from fastapi.testclient import TestClient
from ml.url_model.api import app

client = TestClient(app)

sample_url = "http://example.com/login"
response = client.post("/predict", json={"url": sample_url})
print("Status code:", response.status_code)
print("Response JSON:", response.json())
