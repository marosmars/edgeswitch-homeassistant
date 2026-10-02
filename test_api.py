#!/usr/bin/env python3
"""Standalone test script for EdgeSwitch API."""

import asyncio
import argparse
import sys
import os
import importlib.util

import aiohttp

# Load api.py directly without importing the full package (avoids HA dependencies)
api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "custom_components", "edgeswitch", "api.py")
spec = importlib.util.spec_from_file_location("api", api_path)
api_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_module)
EdgeSwitchAPI = api_module.EdgeSwitchAPI


async def test_api(host: str, username: str, password: str, action: str = None, port: int = None):
    """Test the EdgeSwitch API."""
    print(f"\n{'='*60}")
    print(f"EdgeSwitch API Test - {host}")
    print(f"{'='*60}\n")

    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    api = EdgeSwitchAPI(host=host, username=username, password=password, session=session)

    try:
        # Test authentication
        print("[1] Authenticating...")
        try:
            await api.authenticate()
        except api_module.EdgeSwitchError as err:
            print(f"    ✗ Authentication failed: {err}")
            return False
        print(f"    ✓ Success! Token: {api._auth_token[:20]}...")

        # Get system info
        print("\n[2] Getting system info...")
        system_info = await api.get_system_info()
        print(f"    Hostname: {system_info.get('hostname', 'unknown')}")
        print(f"    Timezone: {system_info.get('timezone', 'unknown')}")
        stp = system_info.get('stp', {})
        print(f"    STP: {'enabled' if stp.get('enabled') else 'disabled'} ({stp.get('version', '?')})")

        # Management info
        mgmt = system_info.get('management', {})
        mgmt_addrs = mgmt.get('addresses', [])
        for addr in mgmt_addrs:
            if addr.get('version') == 'v4':
                print(f"    Management IP: {addr.get('cidr')} (VLAN {mgmt.get('vlanID', '?')})")

        # DNS and Gateway
        dns = system_info.get('dnsServers', [])
        if dns:
            print(f"    DNS: {', '.join(d.get('address', '?') for d in dns)}")
        gw = system_info.get('defaultGateway', [])
        if gw:
            print(f"    Gateway: {gw[0].get('address', '?')}")

        # Get device info
        print("\n[3] Getting device info...")
        device_info = await api.get_device_info()
        identification = device_info.get("identification", {})
        print(f"    Model: {identification.get('product', 'unknown')}")
        print(f"    Firmware: {identification.get('firmwareVersion', 'unknown')}")
        print(f"    MAC: {identification.get('mac', 'unknown')}")

        # Get statistics
        print("\n[4] Getting system statistics...")
        stats = await api.get_statistics()
        device = stats.get("device", {})

        # CPU
        cpus = device.get("cpu", [])
        if cpus:
            print(f"    CPU: {cpus[0].get('usage', '?')}% ({cpus[0].get('identifier', 'Unknown')})")

        # RAM
        ram = device.get("ram", {})
        if ram:
            total_mb = ram.get("total", 0) / 1024 / 1024
            free_mb = ram.get("free", 0) / 1024 / 1024
            print(f"    RAM: {ram.get('usage', '?')}% (Free: {free_mb:.1f} MB / Total: {total_mb:.1f} MB)")

        # Temperatures
        temps = device.get("temperatures", [])
        if temps:
            print("    Temperatures:")
            for t in temps:
                print(f"      - {t.get('name', '?')}: {t.get('value', '?')}°C ({t.get('type', '?')})")

        # Uptime
        uptime = device.get("uptime")
        if uptime:
            days = uptime // 86400
            hours = (uptime % 86400) // 3600
            mins = (uptime % 3600) // 60
            print(f"    Uptime: {days}d {hours}h {mins}m")

        # PoE Power per port
        interfaces = stats.get("interfaces", [])
        total_poe = 0.0
        poe_ports = []
        for iface in interfaces:
            iface_id = iface.get("id", "")
            if not iface_id.startswith("0/"):
                continue
            try:
                port_num = int(iface_id.split("/")[1])
                if port_num > 16:
                    continue
            except:
                continue
            poe_power = iface.get("statistics", {}).get("poePower", 0) or 0
            total_poe += poe_power
            if poe_power > 0:
                poe_ports.append((port_num, iface.get("name", ""), poe_power))

        print(f"\n    PoE Power: {total_poe:.2f}W total (150W budget)")
        if poe_ports:
            for port_num, name, power in sorted(poe_ports):
                print(f"      - Port {port_num} ({name or 'unnamed'}): {power:.2f}W")

        # Get VLANs
        print("\n[5] Getting VLAN configuration...")
        vlans_data = await api.get_vlans()

        trunks = vlans_data.get("trunks", [])
        trunk_ids = set()
        for trunk in trunks:
            iface = trunk.get("interface", {})
            if iface.get("type") == "port":
                trunk_ids.add(iface.get("id"))

        print(f"    Trunk ports: {sorted(trunk_ids) if trunk_ids else 'None'}")

        vlans = vlans_data.get("vlans", [])
        print(f"    Found {len(vlans)} VLANs:\n")

        for vlan in vlans:
            vlan_id = vlan.get("id")
            vlan_name = vlan.get("name", "")
            participation = vlan.get("participation", [])

            tagged = []
            untagged = []
            for part in participation:
                iface = part.get("interface", {})
                if iface.get("type") != "port":
                    continue
                port_id = iface.get("id")
                mode = part.get("mode")
                if mode == "tagged":
                    tagged.append(port_id)
                else:
                    untagged.append(port_id)

            print(f"    VLAN {vlan_id} ({vlan_name}):")
            print(f"      Tagged:   {sorted(tagged) if tagged else 'None'}")
            print(f"      Untagged: {sorted(untagged) if untagged else 'None'}")
            print()

        # Get ports
        print("[6] Getting port status...")
        ports = await api.get_ports()
        print(f"    Found {len(ports)} ports\n")

        # Build port VLAN membership for display
        port_vlans = {}
        for vlan in vlans:
            vlan_id = vlan.get("id")
            vlan_name = vlan.get("name", "")
            for part in vlan.get("participation", []):
                iface = part.get("interface", {})
                if iface.get("type") != "port":
                    continue
                port_id = iface.get("id")
                if port_id not in port_vlans:
                    port_vlans[port_id] = []
                mode = part.get("mode", "untagged")
                port_vlans[port_id].append(f"{vlan_id}{'T' if mode == 'tagged' else 'U'}")

        print(f"    {'Port':<6} {'Name':<25} {'Enabled':<8} {'Link':<8} {'Speed':<10} {'PoE':<8} {'Trunk':<6} {'VLANs':<20}")
        print(f"    {'-'*6} {'-'*25} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*6} {'-'*20}")

        for p in ports:
            port_num = p.get('port_number', '?')
            port_id = p.get('port_id', '')
            name = (p.get('name', '') or '-')[:23]
            enabled = '✓ ON' if p.get('enabled') else '✗ OFF'
            link = '↑ UP' if p.get('plugged') else '↓ DOWN'
            speed = (p.get('speed') or '-')[:8]
            poe = p.get('poe', 'off')
            is_trunk = '✓' if port_id in trunk_ids else '-'
            vlan_info = ','.join(port_vlans.get(port_id, []))[:18] or '-'
            print(f"    {port_num:<6} {name:<25} {enabled:<8} {link:<8} {speed:<10} {poe:<8} {is_trunk:<6} {vlan_info:<20}")

        # Execute action if specified
        if action and port:
            port_id = f"0/{port}"
            print(f"\n[7] Executing action: {action} on port {port} ({port_id})...")

            if action == "poe-on":
                success = await api.set_poe_enabled(port_id, True)
                print(f"    {'✓ PoE enabled' if success else '✗ Failed to enable PoE'}")

            elif action == "poe-off":
                success = await api.set_poe_enabled(port_id, False)
                print(f"    {'✓ PoE disabled' if success else '✗ Failed to disable PoE'}")

            elif action == "port-on":
                success = await api.set_port_enabled(port_id, True)
                print(f"    {'✓ Port enabled' if success else '✗ Failed to enable port'}")

            elif action == "port-off":
                success = await api.set_port_enabled(port_id, False)
                print(f"    {'✓ Port disabled' if success else '✗ Failed to disable port'}")

            elif action.startswith("speed-"):
                speed = action.replace("speed-", "")
                success = await api.set_port_speed(port_id, speed)
                print(f"    {'✓ Speed set to ' + speed if success else '✗ Failed to set speed'}")

            elif action.startswith("name-"):
                name = action.replace("name-", "")
                success = await api.set_port_name(port_id, name)
                print(f"    {'✓ Name set to ' + name if success else '✗ Failed to set name'}")

            # Refresh port status after action
            if action:
                print("\n[8] Refreshing port status...")
                ports = await api.get_ports()
                for p in ports:
                    if p.get('port_number') == port:
                        print(f"    Port {port}: enabled={p.get('enabled')}, poe={p.get('poe')}, speed={p.get('configured_speed')}, name={p.get('name') or '(none)'}")

        print(f"\n{'='*60}")
        print("Test completed successfully!")
        print(f"{'='*60}\n")
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Test EdgeSwitch API",
        epilog="""
Actions:
  poe-on, poe-off       Enable/disable PoE on port
  port-on, port-off     Enable/disable port
  speed-auto            Set port speed to auto
  speed-1000-full       Set port speed to 1Gbps
  speed-100-full        Set port speed to 100Mbps
  name-MyPort           Set port name to 'MyPort'

Examples:
  %(prog)s 192.168.1.1 ubnt password
  %(prog)s 192.168.1.1 ubnt password --action poe-off --port 5
  %(prog)s 192.168.1.1 ubnt password --action speed-auto --port 3
  %(prog)s 192.168.1.1 ubnt password --action name-Server --port 2
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("host", help="EdgeSwitch IP address or hostname")
    parser.add_argument("username", help="Username (default: ubnt)", nargs="?", default="ubnt")
    parser.add_argument("password", help="Password")
    parser.add_argument(
        "--action",
        help="Action to perform (see below for options)"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port number for action (1-18)"
    )

    args = parser.parse_args()

    if args.action and not args.port:
        parser.error("--port is required when using --action")

    asyncio.run(test_api(
        host=args.host,
        username=args.username,
        password=args.password,
        action=args.action,
        port=args.port
    ))


if __name__ == "__main__":
    main()
