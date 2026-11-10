#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_vm_clone
short_description: Create a QEMU/KVM virtual machine or template clone
description:
  - Creates a clone of a QEMU/KVM virtual machine.
  - The source can be either a VM or template.
version_added: "1.0.0"
author:
  - Steve Fulmer (@stevefulme1)
  - Shahar Golshani (@shahargolshani)
options:
  node:
    description:
      - Proxmox VE node containing the source VM or template.
    type: str
    required: true
  vmid:
    description:
      - Identifier of the source QEMU/KVM VM or template.
      - Valid values range from 100 to 999999999.
    type: int
    required: true
  newid:
    description:
      - Identifier to assign to the new VM clone.
      - The identifier must not already be in use and must range from 100 to 999999999.
    type: int
    required: true
  description:
    description: Description for the cloned VM.
    type: str
  format:
    description:
      - Target disk format for a full clone.
      - If the target storage does not support the format, Proxmox uses the storage default.
      - Cannot be used with O(full=false).
    type: str
    choices: [raw, qcow2, vmdk]
  full:
    description:
      - Create a full copy of all disks.
      - Set to V(false) to request a linked clone, which requires support from the source disks and storage.
      - When omitted, Proxmox defaults to a full clone from a VM and a linked clone from a template.
    type: bool
  name:
    description: Name for the new VM.
    type: str
  pool:
    description: Add the cloned VM to this resource pool.
    type: str
  snapname:
    description: Snapshot name to use as the clone source.
    type: str
  storage:
    description: Target storage for a full clone.
    type: str
  target:
    description:
      - Target node for the clone.
      - This is allowed only when the source VM or template uses shared storage.
    type: str
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
  - ansible.proxmox.proxmox_task
attributes:
  check_mode:
    support: full
    description: Checks VMID availability, cross-node destination storage, and linked-clone disk support without cloning.
seealso:
  - module: ansible.proxmox.proxmox_vm
    description: Manage the VM after it has been cloned.
  - module: ansible.proxmox.proxmox_vm_info
    description: Retrieve VM information.
notes:
  - This module is not idempotent; a subsequent invocation fails if the clone already exists or O(newid) is in use.
  - The API identity must have permissions to clone the source VM or template on C(/vms).
"""

EXAMPLES = r"""
- name: Clone a VM
  ansible.proxmox.proxmox_vm_clone:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    node: pve01
    vmid: 100
    newid: 101
    name: my-linux-vm-copy
    task_timeout: 900

- name: Create a full clone with a requested disk format
  ansible.proxmox.proxmox_vm_clone:
    api_host: proxmox.example.com
    api_user: root@pam
    api_token_id: ansible_user_token
    api_token_secret: "{{ vault_proxmox_token_secret }}"
    node: pve01
    vmid: 200
    newid: 201
    full: true
    storage: local-lvm
    format: qcow2
"""

RETURN = r"""
clone:
  description: Identifier of the newly created VM clone.
  returned: success
  type: dict
  sample: {"vmid": 101}
task_upid:
  description: UPID of the completed Proxmox clone task.
  returned: when the clone request returns a task UPID
  type: str
  sample: 'UPID:pve01:00000001:00000001:00000001:qmclone:100:root@pam:'
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_mutually_exclusive,
    proxmox_required_together,
    proxmox_task_argument_spec,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_action import ProxmoxActionModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_power import ProxmoxPower
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask


class ProxmoxVmCloneModule(ProxmoxPower, ProxmoxActionModule):
    """Create a non-idempotent clone through Proxmox's QEMU clone endpoint."""

    result_key = "clone"
    CLONE_OPTIONS = ("description", "format", "full", "name", "pool", "snapname", "storage", "target")

    def is_action_needed(self):
        """Validate clone identifiers and authorize the non-idempotent action.

        Returns:
            bool: True because every invocation attempts a new clone.
        """
        self._validate_vmids()
        self.client.validate_pve_permissions(self.api, "/vms")
        self._validate_check_mode()
        return True

    def _validate_check_mode(self):
        """Validate clone options and destination availability before cloning.

        Reject format with explicit full=false in both modes. Check source,
        storage, and linked-clone constraints only when predicting the action.
        """
        self._validate_clone_options()
        self._validate_destination_vmid()
        if not self.module.check_mode:
            return

        source = self._validate_source_vm()
        self._validate_target_storage()
        self._validate_linked_clone_support(source)

    def _validate_clone_options(self):
        """Reject incompatible clone options in both normal and check mode."""
        params = self.module.params
        if params.get("full") is False and params.get("format") is not None:
            self.module.fail_json(msg="format cannot be used with full=false.")

    def _validate_destination_vmid(self):
        """Verify that the destination VMID is unused across the cluster."""
        newid = self.module.params["newid"]
        resources = self.call_api(
            "Checking whether VMID {0} is available for cloning".format(newid),
            self.api.cluster.resources.get,
            type="vm",
        ) or []
        if any(
            isinstance(resource, dict) and str(resource.get("vmid")) == str(newid)
            for resource in resources
        ):
            self.module.fail_json(msg="VMID {0} is already in use.".format(newid))

    def _validate_source_vm(self):
        """Verify that the source QEMU VM exists on the requested node.

        Returns:
            dict: Source VM metadata, including its template flag when present.
        """
        vmid = self.module.params["vmid"]
        node = self.module.params["node"]
        source_vms = self.call_api(
            "Retrieving VMs from node {0}".format(node),
            self.api.get,
            "nodes/{0}/qemu".format(node),
        )
        source = next(
            (
                resource
                for resource in source_vms or []
                if isinstance(resource, dict) and str(resource.get("vmid")) == str(vmid)
            ),
            None,
        )
        if source is None:
            self.module.fail_json(msg="QEMU VM {0} is not available on node {1}.".format(vmid, node))
        return source

    def _validate_target_storage(self):
        """Require shared destination storage when cloning to another node."""
        params = self.module.params
        storage = params.get("storage")
        target = params.get("target")
        if not storage or not target or target in (params["node"], "localhost"):
            return

        storage_config = self.call_api(
            "Retrieving configuration for storage {0}".format(storage),
            self.api.storage(storage).get,
        )
        if not isinstance(storage_config, dict):
            self.module.fail_json(
                msg="Unable to determine whether storage '{0}' is shared.".format(storage)
            )
        if storage_config.get("shared", 0) not in (1, "1", True):
            self.module.fail_json(msg="can't clone to non-shared storage '{0}'".format(storage))

    def _validate_linked_clone_support(self, source):
        """Verify source disk support when the request uses a linked clone.

        Args:
            source (dict): Source VM metadata used to determine the default clone mode.
        """
        params = self.module.params
        full = params.get("full")
        if full is True or (full is None and source.get("template") not in (1, "1", True)):
            return

        vmid = params["vmid"]
        node = params["node"]
        options = {"feature": "clone"}
        if params.get("snapname") is not None:
            options["snapname"] = params["snapname"]
        features = self.call_api(
            "Checking linked clone support for VM {0} on node {1}".format(vmid, node),
            self.vm_resource().feature.get,
            **options
        )
        if not isinstance(features, dict) or features.get("hasFeature") not in (0, "0", 1, "1"):
            self.module.fail_json(
                msg="Unable to determine linked clone support for VM {0} on node {1}.".format(vmid, node)
            )
        if features["hasFeature"] not in (1, "1", True):
            self.module.fail_json(
                msg=(
                    "Linked clone feature is not supported for one or more disks of VM {0} on node {1}. "
                    "Use full=true to create a full clone."
                ).format(vmid, node)
            )

    def _validate_vmids(self):
        """Validate the source and destination VMIDs before calling Proxmox."""
        vmid = self.module.params["vmid"]
        newid = self.module.params["newid"]
        for parameter, value in (("vmid", vmid), ("newid", newid)):
            if not 100 <= value <= 999999999:
                self.module.fail_json(msg="{0} must be between 100 and 999999999.".format(parameter))
        if vmid == newid:
            self.module.fail_json(msg="newid must be different from vmid.")

    def perform_action(self):
        """Submit the clone request and wait for its asynchronous task.

        Returns:
            dict: Mapping containing the new VMID.
        """
        params = self.module.params
        vmid = params["vmid"]
        node = params["node"]
        newid = params["newid"]
        options = {"newid": newid}
        options.update(
            {option: params[option] for option in self.CLONE_OPTIONS if params.get(option) is not None}
        )
        if "full" in options:
            options["full"] = int(options["full"])
        self._task_upid = self.call_mutation(
            "Cloning VM {0} on node {1} as VM {2}".format(vmid, node, newid),
            self.vm_resource().clone.post,
            **options
        )
        if not isinstance(self._task_upid, str) or not self._task_upid.startswith("UPID:"):
            self.module.fail_json(msg="VM {0} clone request did not return a task UPID.".format(vmid))
        ProxmoxTask(self.module, client=self.client).wait_for_task(self._task_upid)
        return self.get_action_result()

    def get_action_result(self):
        """Return the destination VMID for a real or predicted clone.

        Returns:
            dict: Mapping containing the new VMID.
        """
        return {"vmid": self.module.params["newid"]}

    def prepare_result(self, changed, resource=None, **values):
        """Include the completed clone task UPID in the action result.

        Args:
            changed (bool): Whether a clone was performed or is predicted.
            resource (dict, optional): Clone result containing the new VMID.
            **values: Additional top-level result fields.

        Returns:
            dict: Action result with an optional task_upid.
        """
        result = super().prepare_result(changed, resource, **values)
        if getattr(self, "_task_upid", None) is not None:
            result["task_upid"] = self._task_upid
        return result


def main():
    """Parse clone arguments and create a VM or template copy."""
    module = AnsibleModule(
        argument_spec=proxmox_task_argument_spec(
            {
                "node": {"type": "str", "required": True},
                "vmid": {"type": "int", "required": True},
                "newid": {"type": "int", "required": True},
                "description": {"type": "str"},
                "format": {"type": "str", "choices": ["raw", "qcow2", "vmdk"]},
                "full": {"type": "bool"},
                "name": {"type": "str"},
                "pool": {"type": "str"},
                "snapname": {"type": "str"},
                "storage": {"type": "str"},
                "target": {"type": "str"},
            }
        ),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxVmCloneModule(module).execute_action_module()


if __name__ == "__main__":
    main()
