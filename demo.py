"""Run and inspect the blue-green demo."""

import http.client
import json
import os
import shutil
import sys
import threading
import time

from app import HERE, MANIFEST, load_manifest, make_router, make_server

ROUTER_PORT = 8080
DEPLOYED = os.path.join(HERE, ".deployed", "deploy.json")
SHOP_TRAFFIC = (
    ["/checkout?items=2&user=asha"] * 3
    + ["/checkout?items=2"] * 3
)


def get(port, path):
    connection = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=3
    )
    connection.request("GET", path)
    response = connection.getresponse()
    status = response.status
    body = response.read()
    served_by = response.getheader("X-Served-By")
    connection.close()

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"error": "invalid response"}

    return status, data, served_by


def apply():
    os.makedirs(os.path.dirname(DEPLOYED), exist_ok=True)
    shutil.copy2(MANIFEST, DEPLOYED)
    print("Deployment manifest applied.")


def probe():
    status, data, served_by = get(ROUTER_PORT, "/info")
    print(f"Router: HTTP {status}, served by {served_by}")
    print(json.dumps(data, indent=2))


def traffic():
    success = 0
    errors = 0

    for path in SHOP_TRAFFIC:
        status, data, served_by = get(ROUTER_PORT, path)

        if status == 200:
            success += 1
        else:
            errors += 1

        print(
            f"{path} -> HTTP {status}, "
            f"served by {served_by}, response: {data}"
        )

    print(f"\nTraffic summary: {success} successful, {errors} errors")


def smoke(env_name):
    manifest = load_manifest()
    port = manifest["environments"][env_name]["port"]

    status, data, _ = get(port, "/health")
    print(f"{env_name} health: HTTP {status}, {data}")

    status, data, _ = get(port, "/checkout?items=2&user=asha")
    print(f"{env_name} checkout: HTTP {status}, {data}")

    if status != 200:
        raise SystemExit("Smoke test failed")

    print(f"{env_name} smoke test passed.")


def up():
    manifest = load_manifest()
    servers = []

    for env_name in ("blue", "green"):
        server = make_server(env_name)
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True
        )
        thread.start()
        servers.append(server)
        print(
            f"{env_name} running on port "
            f"{manifest['environments'][env_name]['port']}"
        )

    router = make_router(ROUTER_PORT)
    thread = threading.Thread(
        target=router.serve_forever,
        daemon=True
    )
    thread.start()
    servers.append(router)

    print(f"Router running on port {ROUTER_PORT}")
    print("Press Ctrl+C to stop all servers.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    commands = {
        "up": up,
        "apply": apply,
        "probe": probe,
        "traffic": traffic,
    }

    if len(sys.argv) < 2:
        print("Usage: python demo.py up|apply|probe|traffic|smoke")
        raise SystemExit(1)

    command = sys.argv[1]

    if command == "smoke":
        if len(sys.argv) < 3:
            print("Usage: python demo.py smoke blue|green")
            raise SystemExit(1)
        smoke(sys.argv[2])

    elif command in commands:
        commands[command]()

    else:
        print("Unknown command:", command)
        raise SystemExit(1)