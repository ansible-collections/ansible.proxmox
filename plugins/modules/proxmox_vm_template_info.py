#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_vm_template_info
short_description: Retrieve QEMU/KVM virtual machine templates
description:
  - Retrieves template status information for QEMU/KVM virtual machines on a Proxmox VE node.
  - When I(vmid) is omitted, All the virtual machine templates are returned.
  - When I(vmid) is provided, returns that VM only if its current status marks it as a template.
  - Returns an empty list when the requested VM is missing or is not a template.
version_added: "1.0.0"
author:
  - Steve Fulmer (@stevefulme1)
  - Shahar Golshani (@shahargolshani)
options:
  node:
    description:
      - Proxmox VE node containing the virtual machine template(s).
    type: str
    required: true
  vmid:
    description:
      - Return information for only this VM, if it is a template.
      - Valid values range from 100 to 999999999.
    type: int
    required: false
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
seealso:
  - module: ansible.proxmox.proxmox_vm_template
    description: Convert a stopped QEMU/KVM VM into a template.
  - module: ansible.proxmox.proxmox_vm
    description: Update or delete VM templates.
notes:
  - The module requires all privileges of the C(Administrator) role, propagated on C(/vms).
  - Use M(ansible.proxmox.proxmox_vm) to update or delete templates, just as for regular VMs.
"""

EXAMPLES = r"""
- name: List templates on a node
  ansible.proxmox.proxmox_vm_template_info:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    node: pve01

- name: Check whether one VM is a template
  ansible.proxmox.proxmox_vm_template_info:
    api_host: proxmox.example.com
    api_user: root@pam
    api_token_id: mytoken
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    node: pve01
    vmid: 100
"""

RETURN = r"""
templates:
  description:
    - Current QEMU status records for templates on the requested node.
    - When C(vmid) is supplied, contains that VM only if C(template=1) is reported.
  returned: always
  type: list
  elements: dict
  sample: [{"vmid": 101, "status": "stopped", "template": 1}]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_argument_spec,
    proxmox_mutually_exclusive,
    proxmox_required_together,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_info import ProxmoxInfoModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_power import ProxmoxPower


class ProxmoxVmTemplateInfoModule(ProxmoxPower, ProxmoxInfoModule):
    """Retrieve template statuses through the shared read-only lifecycle."""

    result_key = "templates"

    @staticmethod
    def _is_template_status(status):
        """Return whether current VM status marks the VM as a template.

        Args:
            status: Current QEMU status mapping.

        Returns:
            Whether the response has template set to one.
        """
        return isinstance(status, dict) and status.get("template") in (1, "1", True)

    def get_info(self):
        """Retrieve template statuses for the selected node and optional VMID.

        Returns:
            A list of current-status records for matching templates.
        """
        node = self.module.params["node"]
        vmid = self.module.params.get("vmid")
        if vmid is not None and not 100 <= vmid <= 999999999:
            self.module.fail_json(msg="VMID must be between 100 and 999999999.")
        self.client.validate_pve_permissions(self.api, "/vms")
        self.validate_proxmox_resource_exist("node", node, self.api.nodes.get, resource_key="node")
        resources = self.call_api(
            "Retrieving VMs from node {0}".format(node),
            self.api.get,
            "nodes/{0}/qemu".format(node),
        )
        vm_records = [
            resource
            for resource in resources or []
            if isinstance(resource, dict) and resource.get("vmid") is not None
        ]
        if vmid is not None:
            vm_records = [
                resource for resource in vm_records if str(resource["vmid"]) == str(vmid)
            ]

        return [dict(resource) for resource in vm_records if self._is_template_status(resource)]


def main():
    """Parse module arguments and return matching VM templates."""
    module = AnsibleModule(
        argument_spec=proxmox_argument_spec({
            "node": {"type": "str", "required": True},
            "vmid": {"type": "int"},
        }),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxVmTemplateInfoModule(module).execute_info_module()


if __name__ == "__main__":
    main()
