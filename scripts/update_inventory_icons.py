#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure ruamel.yaml is used to prevent wiping out comments or breaking YAML style formatting
try:
    from ruamel.yaml import YAML
except ImportError:
    sys.exit("Error: This script requires ruamel.yaml. Install it using: pip install ruamel.yaml")

# Pathing configuration matching project root setup
PROJECT_ROOT = Path(__file__).parent.parent
INVENTORY_PATH = PROJECT_ROOT / "inventory.yml"

def apply_host_rules(host_name, host_dict):
    """Applies conditional styling rules directly to a host's variable dictionary."""
    if host_dict is None:
        # If a host has no variables defined yet, initialize it as an empty dictionary mapping
        return

    if "9200" in host_name:
        host_dict["icon"] = "C9200-24P Front"
    elif "9500" in host_name:
        host_dict["icon"] = "C9500-24Q"
    elif "ASR1004" in host_name:
        host_dict["icon"] = "ASR1004 Front"
        host_dict["w"] = 230
        host_dict["h"] = 90

def walk_groups(group_dict):
    """Recursively traverses the inventory tree to find and modify hosts blocks."""
    if not isinstance(group_dict, dict):
        return

    # Process any hosts explicitly defined inside this group context
    if "hosts" in group_dict and isinstance(group_dict["hosts"], dict):
        for host_name, host_vars in group_dict["hosts"].items():
            # Handle edge case where a host entry is blank/null instead of a dict mapping
            if host_vars is None:
                group_dict["hosts"][host_name] = {}
                host_vars = group_dict["hosts"][host_name]
            apply_host_rules(host_name, host_vars)

    # Drill down further into nested child groups (e.g. cisco_nodes, alpine_nodes)
    if "children" in group_dict and isinstance(group_dict["children"], dict):
        for child_group in group_dict["children"].values():
            walk_groups(child_group)

def main():
    if not INVENTORY_PATH.exists():
        sys.exit(f"Error: Could not locate inventory file at {INVENTORY_PATH}")

    # Set up round-trip YAML processor to preserve structural layout
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    print(f"Reading inventory layout from {INVENTORY_PATH.name}...")
    with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
        data = yaml.load(f)

    # Initiate global search-and-replace loop across all groups
    if data and "all" in data:
        walk_groups(data["all"])
    else:
        sys.exit("Error: Root elements must match standard 'all' topology containers.")

    print("Updating values and writing shifts back safely to disk...")
    with open(INVENTORY_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(data, f)

    print("Success! Host node profiles matched and synchronized cleanly.")

if __name__ == "__main__":
    main()
