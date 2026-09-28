"""NOT the real gunicorn.

Wasmer Edge's Python preset starts Django apps with `python -m gunicorn ...`, but real gunicorn cannot run
inside Wasmer's sandbox (it needs Unix sockets). This small stand-in takes that same command and starts the app
with uvicorn instead, on the address Wasmer asked for. Locally, run `uvicorn config.asgi:app` or `manage.py runserver`.
"""
