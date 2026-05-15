import os


USER_BASE_URL = os.getenv("USER_BASE_URL", "http://localhost:3001").rstrip("/")
ADMIN_BASE_URL = os.getenv("ADMIN_BASE_URL", "http://localhost:3002").rstrip("/")

USER_EMAIL = os.getenv("USER_EMAIL", "tranxuanthanhpbe@gmail.com")
USER_PASSWORD = os.getenv("USER_PASSWORD", "123123")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "seed_admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "12345")

