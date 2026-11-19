#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_lxc_snapshot_info
short_description: Retrieve LXC container snapshots
description:
  - Returns all snapshot records for an LXC container, including the special V(current) entry.
  - Returns an empty list when the container does not exist.
version_added: "1.0.0"
author:
  - Steve Fulmer (@stevefulme1)
  - Shahar Golshani (@shahargolshani)
options:
  node:
    description: Proxmox VE node containing the container.
    type: str
    required: true
  vmid:
    description:
      - Identifier of the LXC container.
      - Valid values range from 100 to 999999999.
    type: int
    required: true
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
seealso:
  - module: ansible.proxmox.proxmox_lxc_snapshot
notes:
  - The API identity must have the C(Administrator) role privileges propagated on C(/vms).
"""

EXAMPLES = r"""
- name: Retrieve all snapshots of an LXC container
  ansible.proxmox.proxmox_lxc_snapshot_info:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    node: pve01
    vmid: 100
  register: lxc_snapshots
"""

RETURN = r"""
snapshots:
  description: Snapshot records returned by Proxmox, including the current configuration entry.
  returned: always
  type: list
  elements: dict
  contains:
    description:
      description: Snapshot description.
      returned: when reported by Proxmox
      type: str
    name:
      description: Snapshot identifier; V(current) identifies the current container.
      returned: always
      type: str
    parent:
      description: Parent snapshot identifier.
      returned: when reported by Proxmox
      type: str
    snaptime:
      description: Snapshot creation time as a Unix timestamp.
      returned: when reported by Proxmox
      type: int
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_argument_spec,
    proxmox_mutually_exclusive,
    proxmox_required_together,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_info import ProxmoxInfoModule


class ProxmoxLxcSnapshotInfoModule(ProxmoxInfoModule):
    """Retrieve all snapshots through the shared read-only lifecycle."""

    result_key = "snapshots"

    def get_info(self):
        """Return all LXC snapshot metadata, or an empty list for a missing container."""
        params = self.module.params
        vmid = params["vmid"]
        if not 100 <= vmid <= 999999999:
            self.module.fail_json(msg="VMID must be between 100 and 999999999.")
        node = params["node"]
        self.client.validate_pve_permissions(self.api, "/vms")
        self.validate_proxmox_resource_exist("node", node, self.api.nodes.get, resource_key="node")
        containers = self.call_api(
            "Retrieving LXC containers from node {0}".format(node),
            self.api.nodes(node).lxc.get,
        )
        if not self.validate_proxmox_resource_exist(
            "LXC container", vmid, lambda: containers, resource_key="vmid", fail_on_missing=False
        ):
            return []
        snapshots = self.call_api(
            "Retrieving snapshots of LXC container {0} on node {1}".format(vmid, node),
            self.api.nodes(node).lxc(vmid).snapshot.get,
        )
        return snapshots or []


def main():
    """Parse arguments and return all LXC snapshot information."""
    module = AnsibleModule(
        argument_spec=proxmox_argument_spec(
            {
                "node": {"type": "str", "required": True},
                "vmid": {"type": "int", "required": True},
            }
        ),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxLxcSnapshotInfoModule(module).execute_info_module()


if __name__ == "__main__":
    main()
