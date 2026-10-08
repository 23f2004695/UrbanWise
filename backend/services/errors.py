class BadRequest(ValueError):
    """Invalid input from the client (→ HTTP 400). Upstream problems use UpstreamError."""
