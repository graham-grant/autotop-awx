#!/usr/bin/env python3
"""
Transforms `ip -j addr show` output (iproute2 JSON) into the same fact
schema NAPALM's get_interfaces() + get_interfaces_ip() produce for the
Cisco vIOS hosts, so Alpine nodes can drop straight into the same
facts_dir as the Cisco devices for parser.py / main.py to consume.

Usage:
    ip -j addr show | python3 build_facts_json.py <hostname>
"""
import json
import sys


def build_facts(ip_addr_json, hostname):
    interfaces = {}
    interfaces_ip = {}

    for iface in ip_addr_json:
        name = iface.get("ifname")
        if name == "lo":
            continue  # loopback isn't a real link-bearing interface -
                       # every node shares 127.0.0.0/8, which would make
                       # parser.py draw a bogus full mesh across the lab

        flags = iface.get("flags", [])
        interfaces[name] = {
            "description": "",
            "is_enabled": "UP" in flags,       # administrative state
            "is_up": "LOWER_UP" in flags,      # carrier/operational state
            "last_flapped": -1.0,              # not tracked, same convention as the NAPALM example
            "mac_address": iface.get("address", "00:00:00:00:00:00"),
            "mtu": iface.get("mtu", 1500),
            "speed": 1000.0,                   # placeholder - emulated NICs don't report a real value
        }

        v4 = {
            a["local"]: {"prefix_length": a["prefixlen"]}
            for a in iface.get("addr_info", [])
            if a.get("family") == "inet"
        }
        if v4:
            interfaces_ip[name] = {"ipv4": v4}

    return {
        "hostname": hostname,
        "interfaces": interfaces,
        "interfaces_ip": interfaces_ip,
        "inventory_name": hostname,
    }


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: build_facts_json.py <hostname>")
    hostname = sys.argv[1]
    ip_addr_json = json.load(sys.stdin)
    facts = build_facts(ip_addr_json, hostname)
    json.dump(facts, sys.stdout, indent=4)


if __name__ == "__main__":
    main()
