#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_sdn_zone_info
short_description: Retrieve Proxmox SDN zone information
description:
  - Lists SDN zones, or retrieves one zone's configuration when O(zone) is supplied.
  - Returns an empty list when the requested zone does not exist.
  - O(running) and O(pending) select configuration views; they do not filter zones by running status.
  - When both are V(false) or omitted, the saved configuration is returned, including changes not yet applied.
  - When both are V(true), the API returns the pending view, which is computed relative to the running configuration.
version_added: "1.0.0"
options:
  zone:
    description: Zone ID. Omit to return all zones.
    type: str
  type:
    description: Filter the list by SDN zone type. Cannot be used with O(zone).
    type: str
    choices: [evpn, faucet, qinq, simple, vlan, vxlan]
  running:
    description:
      - When V(true), return the currently applied running configuration.
      - When V(false) or omitted, do not select the running view; this is not a filter for stopped zones.
    type: bool
  pending:
    description:
      - When V(true), return pending changes relative to the running configuration.
      - When V(false) or omitted, do not select the pending view; saved configuration may still contain unapplied changes.
      - Takes precedence over O(running) when both are V(true).
    type: bool
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
attributes:
  check_mode:
    support: full
    description: Retrieves zone information without modifying the server.
seealso:
  - module: ansible.proxmox.proxmox_sdn_zone
notes:
  - The API identity must have the C(Administrator) role privileges propagated on C(/sdn/zones).
"""

EXAMPLES = r"""
- name: List all SDN zones
  ansible.proxmox.proxmox_sdn_zone_info:
    api_host: pve.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"

- name: Retrieve one SDN zone
  ansible.proxmox.proxmox_sdn_zone_info:
    api_host: pve.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    zone: vxlan1
"""

RETURN = r"""
zones:
  description: All SDN zones or a one-item list containing the requested zone configuration.
  returned: always
  type: list
  elements: dict
  contains:
    zone:
      description: SDN zone ID.
      type: str
      returned: always
    type:
      description: SDN zone type.
      type: str
      returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_argument_spec,
    proxmox_mutually_exclusive,
    proxmox_required_together,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_info import ProxmoxInfoModule


class ProxmoxSdnZoneInfoModule(ProxmoxInfoModule):
    """Retrieve all SDN zones or a selected zone configuration."""

    result_key = "zones"

    def get_info(self):
        """Return all zone records or the selected zone configuration."""
        params = self.module.params
        self.client.validate_pve_permissions(self.api, "/sdn/zones")

        query = {}
        for parameter in ("running", "pending"):
            value = params.get(parameter)
            if value is not None:
                query[parameter] = int(value)

        zone = params.get("zone")
        zone_type = params.get("type")
        if zone_type is not None:
            query["type"] = zone_type
        zones = self.call_api("Retrieving SDN zones", self.api.cluster.sdn.zones.get, **query)
        if zones is None:
            return []
        if not isinstance(zones, list):
            self.client.fail_request("SDN zones endpoint returned an unexpected response.")
        if any(not isinstance(item, dict) for item in zones):
            self.client.fail_request("SDN zones endpoint returned an unexpected response.")
        if zone is not None:
            zone_info = next((item for item in zones if item.get("zone") == zone), None)
            return [zone_info] if zone_info is not None else []
        return zones


def main():
    module = AnsibleModule(
        argument_spec=proxmox_argument_spec({
            "zone": {"type": "str"},
            "type": {"type": "str", "choices": ["evpn", "faucet", "qinq", "simple", "vlan", "vxlan"]},
            "running": {"type": "bool"},
            "pending": {"type": "bool"},
        }),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive([["zone", "type"]]),
    )
    ProxmoxSdnZoneInfoModule(module).execute_info_module()


if __name__ == "__main__":
    main()
