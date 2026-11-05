"""Private command-line sign-in; no password appears in MCP arguments or logs."""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os

import httpx

from client import WorkbenchClient, session_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("login", "status", "logout"))
    parser.add_argument("--url", help="Workbench HTTPS origin")
    args = parser.parse_args()
    transport = WorkbenchClient(args.url)
    path = session_path()
    if args.action == "login":
        username = os.environ.get("WORKBENCH_USERNAME") or input("Workbench username: ").strip()
        password = os.environ.get("WORKBENCH_PASSWORD") or getpass("Workbench password: ")
        with httpx.Client(headers={"Origin": transport.origin}, timeout=30, trust_env=False) as client:
            response = client.post(transport.url("/api/auth/login"), json={"username": username, "password": password})
            transport.check(response)
            if not client.cookies:
                raise ValueError("Sign-in returned no session; use the service's authorized browser/private frontend sign-in")
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf8") as file:
                json.dump({"origin": transport.origin, "cookies": dict(client.cookies)}, file)
        print("Signed in. Private session saved to " + str(path))
    elif args.action == "logout":
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf8"))
            if value.get("origin") != transport.origin:
                raise ValueError("Session origin differs; select its WORKBENCH_URL before logging out")
            with httpx.Client(headers={"Origin": transport.origin}, cookies=value.get("cookies", {}), timeout=30, trust_env=False) as client:
                response = client.post(transport.url("/api/auth/logout"))
                transport.check(response)
            path.unlink()
        print("Signed out; local private session removed.")
    else:
        import asyncio
        async def status():
            try:
                result = await transport.request("GET", "/research/api/me")
                print(json.dumps({"signed_in": True, "username": result.get("username"), "origin": transport.origin}, ensure_ascii=False))
            finally:
                await transport.close()
        asyncio.run(status())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, httpx.HTTPError) as error:
        import sys
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
