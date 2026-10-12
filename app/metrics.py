from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests by method, route template and status code.",
    ["method", "route", "status"],
)

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by method and route template.",
    ["method", "route"],
    # Up to 10 s: during a database outage requests took ~4 s, and with 2.5 s as the
    # top bucket every p95 above it was reported as exactly 2.5 s.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

LINKS_CREATED = Counter("kurz_links_created_total", "Short links created.")
REDIRECTS = Counter("kurz_redirects_total", "Redirects served.", ["result"])
