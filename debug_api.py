#!/usr/bin/env python3
"""Debug script to probe EdgeSwitch API endpoints."""

import asyncio
import ssl
import aiohttp
import sys


async def probe_edgeswitch(host: str, username: str, password: str):
    """Probe the EdgeSwitch to find working API endpoints."""

    # Disable SSL verification for self-signed certs
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        base_url = f"https://{host}"

        print(f"\n{'='*60}")
        print(f"Probing EdgeSwitch at {base_url}")
        print(f"{'='*60}\n")

        # Step 1: Check basic connectivity
        print("[1] Testing basic connectivity...")
        try:
            async with session.get(f"{base_url}/") as resp:
                print(f"    GET / -> {resp.status}")
                text = await resp.text()
                print(f"    Response length: {len(text)} bytes")
                if "login" in text.lower():
                    print("    Contains login form: YES")
                # Check for common patterns
                if "htdocs" in text:
                    print("    Detected: Lua-based web interface")
                if "api" in text.lower():
                    print("    Detected: API references in page")
        except Exception as e:
            print(f"    ERROR: {e}")
            return

        # Step 2: Try various login endpoints
        print("\n[2] Testing login endpoints...")

        login_endpoints = [
            ("/api/v1.0/user/login", "json", {"username": username, "password": password}),
            ("/api/v1/user/login", "json", {"username": username, "password": password}),
            ("/api/auth", "json", {"username": username, "password": password}),
            ("/api/auth/login", "json", {"username": username, "password": password}),
            ("/htdocs/login/login.lua", "form", {"username": username, "password": password}),
            ("/login.cgi", "form", {"username": username, "password": password}),
            ("/", "form", {"username": username, "password": password, "action": "login"}),
        ]

        working_session = None
        auth_headers = {}

        for endpoint, method, data in login_endpoints:
            try:
                if method == "json":
                    async with session.post(f"{base_url}{endpoint}", json=data) as resp:
                        print(f"    POST {endpoint} (JSON) -> {resp.status}")
                        if resp.status == 200:
                            try:
                                json_resp = await resp.json()
                                print(f"        Response: {json_resp}")
                            except:
                                text = await resp.text()
                                print(f"        Response (text): {text[:200]}...")

                            # Check for auth token in headers
                            for header in ["x-auth-token", "authorization", "set-cookie"]:
                                if header in resp.headers:
                                    print(f"        Header {header}: {resp.headers[header][:50]}...")
                                    auth_headers[header] = resp.headers[header]
                else:
                    form = aiohttp.FormData()
                    for k, v in data.items():
                        form.add_field(k, v)
                    async with session.post(f"{base_url}{endpoint}", data=form) as resp:
                        print(f"    POST {endpoint} (FORM) -> {resp.status}")
                        if resp.status in (200, 302):
                            text = await resp.text()
                            if "logout" in text.lower() or "dashboard" in text.lower():
                                print("        Login appears successful!")
                                working_session = session
            except Exception as e:
                print(f"    POST {endpoint} -> ERROR: {e}")

        # Step 3: Try to find API endpoints
        print("\n[3] Probing API endpoints...")

        api_endpoints = [
            "/api/v1.0/system",
            "/api/v1/system",
            "/api/system",
            "/api/v1.0/interfaces",
            "/api/v1/interfaces",
            "/api/v1.0/ports",
            "/api/v1/ports",
            "/api/v1.0/poe",
            "/api/v1/poe",
            "/api/v1.0/device/status",
            "/htdocs/pages/base/dashboard.lsp",
            "/htdocs/pages/switching/port_summary.lsp",
            "/htdocs/pages/poe/poe_status.lsp",
            "/cgi-bin/status.cgi",
        ]

        headers = {"Accept": "application/json"}
        if auth_headers:
            headers.update(auth_headers)

        for endpoint in api_endpoints:
            try:
                async with session.get(f"{base_url}{endpoint}", headers=headers) as resp:
                    status_info = f"{resp.status}"
                    if resp.status == 200:
                        content_type = resp.headers.get("content-type", "")
                        if "json" in content_type:
                            data = await resp.json()
                            status_info += f" JSON: {str(data)[:100]}..."
                        else:
                            text = await resp.text()
                            status_info += f" HTML: {len(text)} bytes"
                    print(f"    GET {endpoint} -> {status_info}")
            except Exception as e:
                print(f"    GET {endpoint} -> ERROR: {e}")

        print("\n[4] Checking for cookie-based session...")
        print(f"    Cookies: {session.cookie_jar}")

        print("\n" + "="*60)
        print("Debug complete. Check output above for working endpoints.")
        print("="*60)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python debug_api.py <host> <username> <password>")
        print("Example: python debug_api.py 192.168.1.1 ubnt password123")
        sys.exit(1)

    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    asyncio.run(probe_edgeswitch(host, username, password))
