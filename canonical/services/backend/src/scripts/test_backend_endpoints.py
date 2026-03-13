import requests
import time
import base64
import json

API_BASE = "http://localhost:8000/api"

results = []

def record_result(endpoint, method, payload, response, elapsed):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "payload": payload,
        "status_code": response.status_code,
        "elapsed": elapsed,
        "content": response.json() if response.headers.get('content-type','').startswith('application/json') else response.text
    })

# 1. Health check
start = time.time()
r = requests.get(f"{API_BASE}/health")
elapsed = time.time() - start
record_result("/health", "GET", None, r, elapsed)

# 2. Tree (minimal)
start = time.time()
r = requests.get(f"{API_BASE}/tree")
elapsed = time.time() - start
record_result("/tree", "GET", None, r, elapsed)

# 3. Tree (complete)
params = {"format": "flat", "include_hidden": True, "max_depth": 5, "file_type": "file"}
start = time.time()
r = requests.get(f"{API_BASE}/tree", params=params)
elapsed = time.time() - start
record_result("/tree", "GET", params, r, elapsed)

# 4. Tree-refresh
start = time.time()
r = requests.post(f"{API_BASE}/tree-refresh")
elapsed = time.time() - start
record_result("/tree-refresh", "POST", None, r, elapsed)

# 5. Persist single file (minimal)
file_content = base64.b64encode(b"hello world").decode()
payload = {"content": file_content}
start = time.time()
r = requests.post(f"{API_BASE}/persist/testdir/test.txt", json=payload)
elapsed = time.time() - start
record_result("/persist/testdir/test.txt", "POST", payload, r, elapsed)

# 6. Persist single file (complete)
file_content = base64.b64encode(b"full payload test").decode()
payload = {"content": file_content}
start = time.time()
r = requests.post(f"{API_BASE}/persist/testdir/test_full.txt", json=payload)
elapsed = time.time() - start
record_result("/persist/testdir/test_full.txt", "POST", payload, r, elapsed)

# 7. Persist batch (minimal)
batch_payload = {"files": [{"path": "batchdir", "filename": "batch.txt", "content": base64.b64encode(b"batch").decode()}]}
start = time.time()
r = requests.post(f"{API_BASE}/persist-batch", json=batch_payload)
elapsed = time.time() - start
record_result("/persist-batch", "POST", batch_payload, r, elapsed)

# 8. Persist batch (complete)
batch_payload = {"files": [
    {"path": "batchdir", "filename": "batch1.txt", "content": base64.b64encode(b"batch1").decode()},
    {"path": "batchdir", "filename": "batch2.txt", "content": base64.b64encode(b"batch2").decode()}
]}
start = time.time()
r = requests.post(f"{API_BASE}/persist-batch", json=batch_payload)
elapsed = time.time() - start
record_result("/persist-batch", "POST", batch_payload, r, elapsed)

# 9. Serve file (minimal)
start = time.time()
r = requests.get(f"{API_BASE}/ScareFeraLab/testdir/test.txt")
elapsed = time.time() - start
record_result("/ScareFeraLab/testdir/test.txt", "GET", None, r, elapsed)

# 10. Serve file (complete)
start = time.time()
r = requests.get(f"{API_BASE}/ScareFeraLab/batchdir/batch1.txt")
elapsed = time.time() - start
record_result("/ScareFeraLab/batchdir/batch1.txt", "GET", None, r, elapsed)

# Save results
with open("backend_endpoint_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Test results saved to backend_endpoint_test_results.json")
