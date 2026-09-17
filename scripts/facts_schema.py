"""
The facts JSON contract every collector must satisfy, regardless of host
type or how the data was gathered. Both the Ansible write step
(validate-before-write, via the __main__ CLI below) and
parser.load_nodes() (validate-on-read, via a direct import) use this, so
the contract can't silently drift between collectors, and a bad collector
fails loudly at gather time instead of producing a cryptic KeyError three
stages downstream in pathfinder.py or renderer.py.

Usage as a CLI (from Ansible):
    echo '<facts json>' | python3 facts_schema.py

Usage as a library (from parser.py):
    from facts_schema import validate
    errors = validate(facts_dict)
"""
import json
import sys

REQUIRED_TOP_LEVEL = {"hostname", "interfaces", "interfaces_ip", "inventory_name"}
REQUIRED_INTERFACE_FIELDS = {
    "description", "is_enabled", "is_up", "last_flapped", "mac_address", "mtu", "speed"
}


def validate(facts: dict) -> list:
    """Returns a list of human-readable error strings. Empty list = valid."""
    errors = []

    if not isinstance(facts, dict):
        return [f"facts must be a JSON object, got {type(facts).__name__}"]

    missing = REQUIRED_TOP_LEVEL - facts.keys()
    if missing:
        errors.append(f"missing top-level field(s): {sorted(missing)}")
        return errors  # nothing else below is safe to check

    if not facts["hostname"] or not isinstance(facts["hostname"], str):
        errors.append("'hostname' must be a non-empty string")

    if not isinstance(facts["interfaces"], dict):
        errors.append("'interfaces' must be an object")
    else:
        for ifname, idata in facts["interfaces"].items():
            if not isinstance(idata, dict):
                errors.append(f"interfaces['{ifname}'] must be an object")
                continue
            missing_fields = REQUIRED_INTERFACE_FIELDS - idata.keys()
            if missing_fields:
                errors.append(f"interfaces['{ifname}'] missing field(s): {sorted(missing_fields)}")

    if not isinstance(facts["interfaces_ip"], dict):
        errors.append("'interfaces_ip' must be an object")
    else:
        for ifname, idata in facts["interfaces_ip"].items():
            if "ipv4" not in idata:
                errors.append(f"interfaces_ip['{ifname}'] missing 'ipv4'")
                continue
            for addr, addrdata in idata["ipv4"].items():
                if "prefix_length" not in addrdata:
                    errors.append(
                        f"interfaces_ip['{ifname}']['ipv4']['{addr}'] missing 'prefix_length'"
                    )

    return errors


def main():
    try:
        facts = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"facts JSON did not parse: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate(facts)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
