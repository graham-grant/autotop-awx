# Basic Ansible -> drawio topology

Generates a `.drawio` diagram showing how the devices in your Ansible
inventory connect to each other. Links are derived from directly-connected
subnets: any two inventory hosts with an interface IP in the same network
are linked, the same as a directly-connected route would show. This is the
"basic" version: nodes and links only, no tunnels yet.

The diagram-building side of the project lives in `scripts/` as five
small modules rather than one big script:

- `config.py` — paths, excluded networks, styling, and router tuning constants
- `parser.py` — reads the JSON facts and layout.yml, derives links from subnets
- `pathfinder.py` — the Hanan-grid A* router that finds each link's actual path
- `renderer.py` — turns routed nodes/links into draw.io XML, with IP/interface labels and status dots
- `main.py` — the entry point; run this one (`python3 scripts/main.py`)

## Layout

`group_vars/` lives inside `playbooks/`, not at the project root — Ansible
only auto-loads `group_vars/`/`host_vars/` from the directory containing
the playbook file itself (or the inventory file's directory), so it has to
sit next to `gather_topology.yml` for `napalm_username`/`napalm_password`
to resolve.

## How it works

1. `playbooks/gather_topology.yml` connects to every host in the
   `network_devices` group via NAPALM (works across Cisco IOS/IOS-XE/NX-OS,
   Arista EOS, Juniper Junos, and other NAPALM-supported platforms) and
   pulls each device's hostname, interface status, and interface IP
   addresses. One JSON file per host gets written to `output/facts/`.
2. `scripts/parser.py` reads those JSON files and groups every interface's
   IPv4 address by network (address + prefix). Any network shared by
   exactly two inventory hosts becomes a link between them — this is
   exactly what a directly-connected/local route represents, so no LLDP
   or CDP needs to be enabled on the devices at all. A network with only
   one inventory member (e.g. an uplink to a device you don't manage) is
   skipped, since there's no second endpoint to draw. A network shared by
   three or more inventory hosts is drawn as a full mesh between them, with
   a note printed, since that's a shared segment rather than the usual
   point-to-point /30 or /31 design.
   Each link shows the IP address of each end's interface next to that end
   and a small green/red dot indicating whether both ends report the
   interface as up — a side with no status data is treated as up, since
   this is a display simplification, not a real health check.

## Link routing

Links are routed by `pathfinder.py`, a true pathfinding engine rather than
a heuristic: every node edge and port position forms a grid (a Hanan
grid), and each link is routed across it with A* search, one link at a
time, "stamping" its path into a shared congestion map so every
later link can see and avoid the ones already placed. This is what
actually guarantees two links never run on top of each other, rather than
just making it unlikely — links only get bent around each other where the
search genuinely needs to, and stay as straight as the turn penalty allows
otherwise.

A node whose side doesn't have room for all its ports at a safe minimum
spacing is grown automatically — by the exact amount needed, not a rough
estimate — before routing starts. `pathfinder.py` doesn't decide *which*
side of a node a link uses in the first place, though: that choice is
still made the way it always was, by a per-node majority vote over that
node's own links (so a hub with links at slightly different angles ends up
with all of them on one consistent side), with `scripts/layout.yml` able
to override it per node:

```yaml
9500-1: {x: 400, y: 100, side: bottom}
```

Each link's interface ID (abbreviated, e.g. "GigabitEthernet0/1" ->
"Gi0/1") is shown rotated next to each end, close to the parent node. The
IP address label sits a bit further in along the link.

The constants `HANAN_BUFFER` (minimum spacing between lanes),
`HANAN_TURN_PENALTY` (how strongly the router prefers straight runs over
extra bends), and `HANAN_MARGIN` (inset from a node's corners when placing
ports) in `config.py` control routing if the defaults look too tight, too
bendy, or too loose for a particular topology.

## Keeping node positions stable

For a production network with a fixed set of devices, the automatic
force-directed layout can place the same nodes differently between runs —
fine for discovering an unfamiliar topology, but not what you want for a
diagram people reference repeatedly. `scripts/layout.yml` lets you pin
specific nodes to fixed coordinates:

```yaml
core-sw1: {x: 200, y: 150}
core-sw2: {x: 500, y: 150}
```

Nodes listed there are placed at those exact coordinates every run; nodes
not listed fall back to automatic placement (and the script prints a note
naming them, so newly-added devices are easy to spot and pin once you're
happy with where they've landed). The diagram itself is still regenerated
fresh from live data every time — only positions are fixed, not status,
IPs, or link state.

## Setup

```bash
pip install ansible-core napalm N2G python-igraph pyyaml
ansible-galaxy collection install napalm.napalm
export NAPALM_USERNAME=admin
export NAPALM_PASSWORD=secret
```

Edit `inventory.yml` with your actual devices — each host needs
`ansible_host` and `ansible_network_os` (the NAPALM driver name: `ios`,
`eos`, `junos`, `nxos`, `iosxr`, etc.).

## Running this in AWX

Since AWX job containers are ephemeral, don't try to manually copy
`output/facts/*.json` off the execution environment between runs — the
playbook now does the whole pipeline (gather → build → publish) in a single
job. After the gather play writes each host's JSON, a third play runs
`scripts/main.py` and publishes the resulting `topology.drawio` file,
base64-encoded, as an AWX job artifact via `set_stats`.

To get the file after a successful run:
1. Open the completed job in AWX and go to its **Details** tab (or fetch
   `/api/v2/jobs/<id>/` from the API) — look for the `artifacts` field,
   which will contain a key `topology_drawio_b64`.
2. Copy that base64 string, then decode it locally:
   ```bash
   echo "<paste the base64 string>" | base64 -d > topology.drawio
   ```
   or in Python:
   ```python
   import base64
   open("topology.drawio", "wb").write(base64.b64decode("<paste>"))
   ```
3. Open `topology.drawio` in draw.io.

## Running this locally (without AWX)

```bash
ansible-playbook -i inventory.yml playbooks/gather_topology.yml
python3 scripts/main.py
```

Open `output/topology.drawio` in draw.io (desktop app, web app, or the VS
Code extension).

## Notes

- Each host needs at least one interface IP for any link to be drawn at
  all — a device with no `interfaces_ip` data (e.g. only unnumbered
  interfaces, or NAPALM couldn't read it) won't connect to anything in the
  diagram even if it's physically cabled to other inventory hosts.
- `EXCLUDED_NETWORKS` in `config.py` lets you ignore specific subnets
  entirely — e.g. end-host/access VLANs that happen to be configured on a
  router/switch interface but shouldn't be drawn as an inter-device link.
  A more specific subnet within an excluded one (e.g. a /30 carved out of
  an excluded /24) is excluded too.
- This assumes a fairly clean point-to-point addressing scheme (a distinct
  /30 or /31 per link, which is what the directly-connected-route approach
  is built around). A shared multi-access subnet with three or more
  inventory hosts on it still gets drawn (as a full mesh, with a note
  printed), but that's a different physical topology shape than a true
  shared-segment diagram would normally use.
- Palo Alto firewalls work via the community `napalm-panos` driver
  (`ansible_network_os: panos`) — it's a separate pip package from core
  NAPALM, so add `napalm-panos` to your execution environment's
  dependencies.
- This is intentionally minimal so it's easy to extend — tunnel detection
  (GRE/IPsec) on top of this is a matter of pulling NAPALM's `interfaces`
  data for tunnel interfaces specifically and adding the corresponding
  style/label logic to `renderer.py`.

