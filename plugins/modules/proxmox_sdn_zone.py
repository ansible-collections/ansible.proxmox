#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_sdn_zone
short_description: Manage Proxmox SDN zones
description:
  - Creates, updates and deletes Proxmox Software-Defined Network zones.
  - Zone types are immutable; update the options supported by the existing type.
  - Omit an option to preserve it. Set an optional scalar to V("") or an optional list to V([]) to remove that setting.
  - Only options supported by the selected zone type can be used together in a task.
version_added: "1.0.0"
options:
  zone:
    description: Unique SDN zone ID, 2 to 8 alphanumeric characters starting with a letter.
    type: str
    required: true
  type:
    description:
      - SDN zone type. Required when O(state=present); a zone's type cannot be changed.
      - V(vlan) requires O(bridge), V(qinq) requires O(bridge) and O(tag), and V(vxlan) requires exactly one of O(peers) or O(fabric).
      - V(evpn) requires O(controller) and O(vrf_vxlan); V(faucet) requires O(controller) and O(dp_id).
    type: str
    choices: [evpn, faucet, qinq, simple, vlan, vxlan]
  state:
    description:
      - Whether the zone should exist.
      - Zone configuration options are ignored with V(absent). If O(type) is supplied, it must match the existing zone.
    type: str
    choices: [present, absent]
    default: present
  nodes:
    description: Node names enabled for the zone. Supported by all types. Omit to preserve; an empty list removes the restriction.
    type: list
    elements: str
  mtu:
    description: Integer MTU. Supported by simple, VLAN, QinQ, VXLAN and EVPN zones; set to V("") to clear.
    type: raw
  dns:
    description: ID of an existing DNS plugin for the zone. Supported by all types.
    type: str
  reversedns:
    description: ID of an existing reverse-DNS plugin for the zone. Supported by all types.
    type: str
  dnszone:
    description: DNS domain for the zone. Supported by all types.
    type: str
  ipam:
    description: ID of an existing IPAM plugin for the zone. Supported by all types.
    type: str
  dhcp:
    description: DHCP backend. Supported by simple zones only.
    type: str
  dedicated_vrf:
    description: Create a dedicated VRF. Supported by simple zones only.
    type: bool
  route:
    description: Static routes for simple zones only, encoded as Proxmox route property strings.
    type: list
    elements: str
  bridge:
    description: Bridge used by VLAN and QinQ zones. Required by VLAN and QinQ zone types.
    type: str
  bridge_disable_mac_learning:
    description: Disable automatic MAC learning. Supported by VLAN, QinQ and EVPN zones.
    type: bool
  tag:
    description: Service VLAN tag. Required by QinQ zone type.
    type: int
  vlan_protocol:
    description: VLAN protocol. Supported by QinQ zones only.
    type: str
    choices: [802.1q, 802.1ad]
  peers:
    description:
      - Comma-separated peer IP addresses. Supported by VXLAN zones only.
      - VXLAN zones require exactly one of O(peers) or O(fabric).
    type: str
  fabric:
    description:
      - Existing underlay fabric. Supported by VXLAN zones only.
      - VXLAN zones require exactly one of O(peers) or O(fabric).
    type: str
  vxlan_port:
    description: Integer UDP port for VXLAN tunnels. Supported by VXLAN and EVPN zones; V("") resets it to C(4789).
    type: raw
  controller:
    description: ID of an existing SDN controller. Required by EVPN and Faucet zone types.
    type: str
  vrf_vxlan:
    description: Required VNI for the zone VRF. Required by EVPN zone type; cannot be empty or removed.
    type: int
  secondary_controllers:
    description: IDs of additional existing controllers. Supported by EVPN zones only; an empty list removes all secondary controllers.
    type: list
    elements: str
  mac:
    description:
      - Anycast logical router MAC address. Supported by EVPN zones only.
      - Proxmox generates one if omitted; an empty string cannot clear it.
    type: str
  exitnodes:
    description: Node names used as exit nodes. Supported by EVPN zones only.
    type: list
    elements: str
  exitnodes_local_routing:
    description: Allow exit nodes to connect to EVPN guests. Supported by EVPN zones only.
    type: bool
  exitnodes_primary:
    description: Preferred exit node. Supported by EVPN zones only.
    type: str
  advertise_subnets:
    description: Advertise IP prefixes instead of MAC/IP pairs. Supported by EVPN zones only.
    type: bool
  disable_arp_nd_suppression:
    description: Disable ARP and Neighbor Discovery suppression. Supported by EVPN zones only.
    type: bool
  rt_import:
    description: Comma-separated route targets imported into the zone VRF. Supported by EVPN zones only.
    type: str
  dp_id:
    description: Faucet dataplane ID. Required by Faucet zone type.
    type: int
  digest:
    description: Optional current configuration digest for concurrent-update protection when updating an existing zone.
    type: str
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
  - ansible.proxmox.proxmox_task
attributes:
  check_mode:
    support: full
    description: Predicts create, update and delete operations without modifying the server.
notes:
  - Requires propagated C(Administrator) role privileges on C(/sdn/zones), including in check mode.
  - O(type) cannot be changed after a zone is created.
  - Referenced controllers, fabrics, DNS plugins and IPAM plugins must already exist in Proxmox; this module does not create them.
  - A zone can be deleted only when no VNet refers to it. Check mode cannot verify this constraint; the API rejects an invalid deletion.
  - Updates are synchronous; O(task_timeout) does not affect them. O(api_timeout) controls each HTTPS request.
  - Proxmox validates plugin-specific values when applying changes. Check mode validates module-level requirements only.
seealso:
  - module: ansible.proxmox.proxmox_sdn_zone_info
"""

EXAMPLES = r"""
- name: Create a simple zone with its supported options
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: office
    type: simple
    state: present
    nodes: [pve01, pve02]
    mtu: 1500
    dns: powerdns
    reversedns: powerdns
    dnszone: example.com
    ipam: pve
    dhcp: dnsmasq
    dedicated_vrf: true
    route:
      - "prefix=198.51.100.0/24,via=192.0.2.1"

- name: Create a VLAN zone
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: vlan1
    type: vlan
    bridge: vmbr0

- name: Create a QinQ zone with its type-specific options
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: qinq1
    type: qinq
    bridge: vmbr0
    bridge_disable_mac_learning: true
    tag: 100
    vlan_protocol: 802.1ad
    mtu: 1500

- name: Create a VXLAN zone using peer addresses
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: vxlan1
    type: vxlan
    peers: 192.0.2.10,192.0.2.11
    vxlan_port: 4789

- name: Create a VXLAN zone using an underlay fabric instead of peers
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: vxlan2
    type: vxlan
    fabric: fabric1

- name: Create an EVPN zone with EVPN-only options
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: evpn1
    type: evpn
    controller: ansible
    vrf_vxlan: 1000
    secondary_controllers: []
    mac: "02:00:00:00:00:01"
    exitnodes: [pve01, pve02]
    exitnodes_local_routing: true
    exitnodes_primary: pve01
    advertise_subnets: true
    disable_arp_nd_suppression: false
    rt_import: 65000:100,65000:101
    vxlan_port: 4789
    bridge_disable_mac_learning: true

- name: Create a Faucet zone
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: faucet1
    type: faucet
    controller: faucet1
    dp_id: 1

- name: Clear the DNS-zone setting by passing an empty string
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: office
    type: simple
    dnszone: ""

- name: Remove a zone
  ansible.proxmox.proxmox_sdn_zone:
    api_host: pve.example.com
    api_token_id: ansible@pve!automation
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    zone: office
    state: absent
"""

RETURN = r"""
zone:
  description: Current or predicted SDN zone configuration, or null when absent.
  returned: always
  type: dict
  contains:
    zone:
      description: SDN zone ID.
      type: str
      returned: when the zone exists
    type:
      description: SDN zone type.
      type: str
      returned: when the zone exists
    digest:
      description: Current API configuration digest. Omitted for predicted changes in check mode.
      type: str
      returned: when supplied by the API
"""

import copy
import re

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_mutually_exclusive,
    proxmox_required_together,
    proxmox_resource_argument_spec,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_resource import ProxmoxResourceModule


ZONE_TYPES = ["evpn", "faucet", "qinq", "simple", "vlan", "vxlan"]

ZONE_OPTION_API_NAMES = {
    "nodes": "nodes",
    "mtu": "mtu",
    "dns": "dns",
    "reversedns": "reversedns",
    "dnszone": "dnszone",
    "ipam": "ipam",
    "dhcp": "dhcp",
    "dedicated_vrf": "dedicated-vrf",
    "route": "route",
    "bridge": "bridge",
    "bridge_disable_mac_learning": "bridge-disable-mac-learning",
    "tag": "tag",
    "vlan_protocol": "vlan-protocol",
    "peers": "peers",
    "fabric": "fabric",
    "vxlan_port": "vxlan-port",
    "controller": "controller",
    "vrf_vxlan": "vrf-vxlan",
    "secondary_controllers": "secondary-controllers",
    "mac": "mac",
    "exitnodes": "exitnodes",
    "exitnodes_local_routing": "exitnodes-local-routing",
    "exitnodes_primary": "exitnodes-primary",
    "advertise_subnets": "advertise-subnets",
    "disable_arp_nd_suppression": "disable-arp-nd-suppression",
    "rt_import": "rt-import",
    "dp_id": "dp-id",
}

COMMON_OPTIONS = {"nodes", "dns", "reversedns", "dnszone", "ipam"}
ZONE_TYPE_OPTIONS = {
    "simple": COMMON_OPTIONS | {"mtu", "dhcp", "dedicated_vrf", "route"},
    "vlan": COMMON_OPTIONS | {"mtu", "bridge", "bridge_disable_mac_learning"},
    "qinq": COMMON_OPTIONS | {"mtu", "bridge", "bridge_disable_mac_learning", "tag", "vlan_protocol"},
    "vxlan": COMMON_OPTIONS | {"mtu", "peers", "fabric", "vxlan_port"},
    "evpn": COMMON_OPTIONS | {
        "mtu", "bridge_disable_mac_learning", "vxlan_port", "controller", "vrf_vxlan",
        "secondary_controllers", "mac", "exitnodes", "exitnodes_local_routing",
        "exitnodes_primary", "advertise_subnets", "disable_arp_nd_suppression", "rt_import",
    },
    "faucet": COMMON_OPTIONS | {"controller", "dp_id"},
}
ZONE_REQUIRED_OPTIONS = {
    "vlan": ("bridge",),
    "qinq": ("bridge", "tag"),
    "evpn": ("controller", "vrf_vxlan"),
    "faucet": ("controller", "dp_id"),
}
ZONE_DEFAULTS = {"dedicated-vrf": 0, "vlan-protocol": "802.1q", "vxlan-port": 4789}
COMMA_LIST_OPTIONS = {"nodes", "exitnodes"}
ARRAY_OPTIONS = {"route", "secondary_controllers"}
CLEARABLE_INTEGER_OPTIONS = {"mtu", "vxlan_port"}

ZONE_ARGUMENTS = {
    "nodes": {"type": "list", "elements": "str"},
    "mtu": {"type": "raw"},
    "dns": {"type": "str"},
    "reversedns": {"type": "str"},
    "dnszone": {"type": "str"},
    "ipam": {"type": "str"},
    "dhcp": {"type": "str"},
    "dedicated_vrf": {"type": "bool"},
    "route": {"type": "list", "elements": "str"},
    "bridge": {"type": "str"},
    "bridge_disable_mac_learning": {"type": "bool"},
    "tag": {"type": "int"},
    "vlan_protocol": {"type": "str", "choices": ["802.1q", "802.1ad"]},
    "peers": {"type": "str"},
    "fabric": {"type": "str"},
    "vxlan_port": {"type": "raw"},
    "controller": {"type": "str"},
    "vrf_vxlan": {"type": "int"},
    "secondary_controllers": {"type": "list", "elements": "str"},
    "mac": {"type": "str"},
    "exitnodes": {"type": "list", "elements": "str"},
    "exitnodes_local_routing": {"type": "bool"},
    "exitnodes_primary": {"type": "str"},
    "advertise_subnets": {"type": "bool"},
    "disable_arp_nd_suppression": {"type": "bool"},
    "rt_import": {"type": "str"},
    "dp_id": {"type": "int"},
}


class ProxmoxSdnZoneModule(ProxmoxResourceModule):
    """Reconcile SDN zone configuration through the shared resource lifecycle."""

    result_key = "zone"

    def get_resource(self):
        """Validate the request and retrieve the selected zone if present."""
        params = self.module.params
        zone = params["zone"]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,6}[A-Za-z0-9]", zone) is None:
            self.module.fail_json(msg="zone must be 2 to 8 alphanumeric characters and start with a letter.")
        self._validate_state_parameters()
        self.client.validate_pve_permissions(self.api, "/sdn/zones")
        resource = self._get_zone()
        if resource is None:
            if params["state"] == "present":
                if params.get("digest") is not None:
                    self.module.fail_json(msg="digest can only be used when updating an existing zone.")
                self._validate_zone_configuration(params["type"])
            return None

        if params["state"] == "absent":
            if params.get("type") is not None and params["type"] != resource.get("type"):
                self.module.fail_json(msg="The existing SDN zone has a different type; zone type is immutable.")
            return resource
        if params["type"] != resource.get("type"):
            self.module.fail_json(msg="The existing SDN zone has a different type; zone type is immutable.")
        digest = params.get("digest")
        if digest is not None and digest != resource.get("digest"):
            self.module.fail_json(msg="SDN zone digest does not match; read the current configuration before retrying.")
        self._validate_zone_configuration(resource["type"], resource=resource)
        return resource

    def _validate_state_parameters(self):
        """Reject update-only parameters that cannot apply to deletion."""
        params = self.module.params
        if params["state"] != "absent":
            return
        if params.get("digest") is not None:
            self.module.fail_json(msg="digest cannot be supplied with state=absent.")

    def _get_zone(self):
        """Find one zone in the collection endpoint's complete configuration list."""
        zone = self.module.params["zone"]
        zones = self.call_api("Listing SDN zones", self.api.cluster.sdn.zones.get)
        if not isinstance(zones, list):
            self.client.fail_request("SDN zones endpoint returned an unexpected response.")
        for resource in zones:
            if not isinstance(resource, dict):
                self.client.fail_request("SDN zones endpoint returned an unexpected response.")
            if resource.get("zone") == zone:
                return resource
        return None

    def _canonical_values(self, value, split_strings):
        """Normalize API list values, optionally splitting comma-delimited strings."""
        if value is None:
            return []
        if isinstance(value, str):
            values = value.split(",") if split_strings else [value]
        elif split_strings and isinstance(value, dict):
            values = [name for name, enabled in value.items() if enabled]
        elif isinstance(value, (list, tuple, set)):
            values = value
        else:
            self.client.fail_request("SDN zone list option returned an unexpected response.")
        return sorted({str(item).strip() for item in values if str(item).strip()})

    def _canonical_list(self, value):
        """Normalize comma-delimited list fields such as nodes and exitnodes."""
        return self._canonical_values(value, split_strings=True)

    def _canonical_array(self, value):
        """Normalize array-valued fields without splitting property strings."""
        return self._canonical_values(value, split_strings=False)

    def _api_configuration(self):
        """Map supplied options to API keys and record empty-value clears."""
        parameters = {}
        clear_fields = []
        for option, api_name in ZONE_OPTION_API_NAMES.items():
            value = self.module.params.get(option)
            if value is None:
                continue
            if option in COMMA_LIST_OPTIONS or option in ARRAY_OPTIONS:
                canonicalize = self._canonical_list if option in COMMA_LIST_OPTIONS else self._canonical_array
                values = canonicalize(value)
                if not values:
                    clear_fields.append(api_name)
                    continue
                value = ",".join(values) if option in COMMA_LIST_OPTIONS else values
            elif option in CLEARABLE_INTEGER_OPTIONS:
                if value == "":
                    clear_fields.append(api_name)
                    continue
                if isinstance(value, bool):
                    self.module.fail_json(msg="{0} must be an integer or an empty string.".format(option))
                if isinstance(value, str):
                    try:
                        value = int(value, 10)
                    except ValueError:
                        self.module.fail_json(msg="{0} must be an integer or an empty string.".format(option))
                elif not isinstance(value, int):
                    self.module.fail_json(msg="{0} must be an integer or an empty string.".format(option))
            elif isinstance(value, str) and not value:
                clear_fields.append(api_name)
                continue
            elif isinstance(value, bool):
                value = int(value)
            parameters[api_name] = value
        return parameters, clear_fields

    def _validate_zone_configuration(self, zone_type, resource=None):
        """Validate type-specific parameters and required fields before mutation."""
        if zone_type not in ZONE_TYPE_OPTIONS:
            self.module.fail_json(msg="Unsupported SDN zone type: {0}.".format(zone_type))
        params = self.module.params
        for option in ZONE_OPTION_API_NAMES:
            if params.get(option) is not None and option not in ZONE_TYPE_OPTIONS[zone_type]:
                self.module.fail_json(msg="Option {0} is not supported for SDN zone type {1}.".format(option, zone_type))
        if zone_type == "evpn" and params.get("mac") == "":
            self.module.fail_json(
                msg="mac cannot be cleared for EVPN zones; omit it to keep or generate the MAC, or provide a replacement."
            )

        desired, clear_fields = self._api_configuration()
        effective = dict(resource or {})
        effective.update(desired)
        for api_name in clear_fields:
            effective.pop(api_name, None)
        for option in ZONE_REQUIRED_OPTIONS.get(zone_type, ()):
            api_name = ZONE_OPTION_API_NAMES[option]
            value = effective.get(api_name)
            if value is None or value == "":
                self.module.fail_json(msg="SDN zone type {0} requires {1}.".format(zone_type, option))
        if zone_type == "vxlan":
            has_peers = bool(effective.get("peers"))
            has_fabric = bool(effective.get("fabric"))
            if has_peers == has_fabric:
                self.module.fail_json(msg="VXLAN zones require exactly one of peers or fabric.")

    def get_update_parameters(self, resource):
        """Return only changed API values and explicit/default resets."""
        desired, clear_fields = self._api_configuration()
        updates = self.get_parameter_updates(self._comparison_resource(resource), desired, ZONE_DEFAULTS)
        deletions = [value for value in updates.get("delete", "").split(",") if value]
        for api_name in clear_fields:
            current = resource.get(api_name)
            default = ZONE_DEFAULTS.get(api_name)
            if current in (None, "") or (default is not None and self.parameter_values_equal(current, default)):
                continue
            if api_name not in deletions:
                deletions.append(api_name)
        if deletions:
            updates["delete"] = ",".join(deletions)
        return updates

    def _comparison_resource(self, resource):
        """Normalize API list representations for stable idempotency comparisons."""
        comparable = dict(resource)
        for option in COMMA_LIST_OPTIONS:
            api_name = ZONE_OPTION_API_NAMES[option]
            if api_name in comparable:
                comparable[api_name] = ",".join(self._canonical_list(comparable[api_name]))
        for option in ARRAY_OPTIONS:
            api_name = ZONE_OPTION_API_NAMES[option]
            if api_name in comparable:
                comparable[api_name] = self._canonical_array(comparable[api_name])
        return comparable

    def create_resource(self):
        """Create a zone and verify the resulting API configuration."""
        parameters = self._api_configuration()[0]
        parameters = self.omit_default_parameters(parameters, ZONE_DEFAULTS)
        parameters.update({"zone": self.module.params["zone"], "type": self.module.params["type"]})
        zone = self.module.params["zone"]
        self.call_mutation("Creating SDN zone {0}".format(zone), self.api.cluster.sdn.zones.post, **parameters)
        resource = self._get_zone()
        if resource is None:
            self.client.fail_request("Created SDN zone could not be read back.")
        if self.get_update_parameters(resource):
            self.client.fail_request("Created SDN zone does not match the requested configuration.")
        return resource

    def update_resource(self, resource, updates):
        """Apply a digest-protected update and verify its readback."""
        parameters = dict(updates)
        digest = self.module.params.get("digest") or resource.get("digest")
        if digest is not None:
            parameters["digest"] = digest
        zone = self.module.params["zone"]
        self.call_mutation("Updating SDN zone {0}".format(zone), self.api.cluster.sdn.zones(zone).put, **parameters)
        updated = self._get_zone()
        if updated is None:
            self.client.fail_request("Updated SDN zone could not be read back.")
        if self.get_update_parameters(updated):
            self.client.fail_request("Updated SDN zone does not match the requested configuration.")
        return updated

    def delete_resource(self, _resource):
        """Delete the zone and verify that it no longer exists."""
        zone = self.module.params["zone"]
        self.call_mutation("Deleting SDN zone {0}".format(zone), self.api.cluster.sdn.zones(zone).delete)
        if self._get_zone() is not None:
            self.client.fail_request("SDN zone deletion could not be verified.")
        return None

    def get_check_mode_resource(self, operation, resource=None, updates=None):
        """Predict the requested configuration without retaining stale digests."""
        if operation == "delete":
            return None
        if operation == "create":
            parameters = self._api_configuration()[0]
            parameters = self.omit_default_parameters(parameters, ZONE_DEFAULTS)
            return {"zone": self.module.params["zone"], "type": self.module.params["type"], **parameters}
        predicted = self.apply_parameter_updates(resource, updates)
        predicted.pop("digest", None)
        return predicted


def main():
    arguments = {
        "zone": {"type": "str", "required": True},
        "type": {"type": "str", "choices": ZONE_TYPES},
        "digest": {"type": "str"},
    }
    arguments.update(copy.deepcopy(ZONE_ARGUMENTS))
    module = AnsibleModule(
        argument_spec=proxmox_resource_argument_spec(arguments),
        supports_check_mode=True,
        required_if=[("state", "present", ["type"])],
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxSdnZoneModule(module).execute()


if __name__ == "__main__":
    main()
