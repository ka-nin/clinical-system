"""`python -m gunicorn <anything> [--bind HOST:PORT]` -> serve config.asgi:app with uvicorn. See __init__.py."""
import os
import sys


def _address(argv):
    bind = None
    for i, arg in enumerate(argv):
        if arg in ("-b", "--bind") and i + 1 < len(argv):
            bind = argv[i + 1]
        elif arg.startswith("--bind="):
            bind = arg.split("=", 1)[1]
    if bind and not bind.startswith("unix:"):
        host, _, port = bind.rpartition(":")
        return (host or "0.0.0.0").strip("[]"), int(port)
    return "0.0.0.0", int(os.environ.get("PORT", "8000"))


def main(argv=None):
    import uvicorn

    host, port = _address(sys.argv[1:] if argv is None else argv)
    print(f"[careboard] starting uvicorn on {host}:{port} (stand-in for gunicorn)", flush=True)
    uvicorn.run("config.asgi:app", host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
