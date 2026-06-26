import os

# Disable rate limiting during test runs.
# Must be set before any jobplatform module is imported (root conftest loads first).
os.environ.setdefault("TESTING", "true")
