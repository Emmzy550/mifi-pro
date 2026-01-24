"""
Minimal Firebase Functions entry point.
All heavy imports happen at runtime, not during deployment analysis.
"""
from firebase_functions import https_fn, options

@https_fn.on_request(
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=300,
    min_instances=0,
    max_instances=10
)
def api(req: https_fn.Request) -> https_fn.Response:
    """API endpoint - imports FastAPI at runtime."""
    # ALL imports happen here, not at module level
    import sys
    import os
    
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Now import the heavy stuff
    from api import app
    import asyncio
    
    # Safe encode helper
    def to_bytes(s):
        if s is None: return b""
        if isinstance(s, bytes): return s
        return str(s).encode()

    # Build ASGI scope
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": req.method,
        "path": req.path.replace("/api", "", 1) if req.path.startswith("/api") else req.path,
        "query_string": req.query_string if isinstance(req.query_string, bytes) else to_bytes(req.query_string),
        "headers": [(to_bytes(k.lower()), to_bytes(v)) for k, v in req.headers.items()],
        "server": ("cloudfunctions.net", 443),
        "client": (req.remote_addr or "127.0.0.1", 0),
    }
    
    body = req.get_data()
    
    async def receive():
        return {"type": "http.request", "body": body}
    
    status_code = 200
    response_headers = []
    response_body = []
    
    async def send(message):
        nonlocal status_code, response_headers, response_body
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))
    
    # Execute
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(app(scope, receive, send))
    finally:
        loop.close()
    
    # Return
    return https_fn.Response(
        response=b"".join(response_body),
        status=status_code,
        headers={k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v 
                 for k, v in response_headers}
    )
