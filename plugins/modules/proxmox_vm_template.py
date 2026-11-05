#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_vm_template
short_description: Convert a QEMU/KVM virtual machine into a template
description:
  - Converts a QEMU/KVM virtual machine into a Proxmox VE template.
  - A running VM can be stopped automatically with this module before conversion.
  - This is a one-way operation and cannot be reversed.
  - This module only performs initial conversion. Use M(ansible.proxmox.proxmox_vm) for configuration updates and deletion.
version_added: "1.0.0"
author:
  - Steve Fulmer (@stevefulme1)
  - Shahar Golshani (@shahargolshani)
options:
  vmid:
    description:
      - Identifier of the QEMU/KVM virtual machine to convert.
      - Valid values range from 100 to 999999999.
    type: int
    required: true
  disk:
    description:
      - The disk to use as the base image for the template (e.g. C(scsi0), C(virtio0)).
      - When specified, only this disk is converted to a base image.
      - The disk must be configured on the VM, the operation fails if the disk does not exist.
      - Applies only during initial VM-to-template conversion. Existing templates are left unchanged.
      - CD-ROM devices cannot be selected.
    type: str
  power_cycle:
    description:
      - C(fail) fails if the VM is running or suspended.
      - C(off) powers off a running or suspended VM before conversion.
    type: str
    choices: [fail, 'off']
    default: fail
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
  - ansible.proxmox.proxmox_task
attributes:
  check_mode:
    support: full
    description: Predicts conversion without changing the VM.
seealso:
  - module: ansible.proxmox.proxmox_vm_template_info
    description: Retrieve templates from a node.
  - module: ansible.proxmox.proxmox_vm
    description: Update or delete a VM template after conversion.
notes:
  - Use C(proxmox_vm) to update or delete the template, just as for a regular VM.
  - The API identity must be able to discover the VM, read its status, and convert it on C(/vms).
"""

EXAMPLES = r"""
- name: Convert a stopped VM to a template
  ansible.proxmox.proxmox_vm_template:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    vmid: 100
    disk: scsi0
    power_cycle: fail
    task_timeout: 600

- name: Update a template after conversion
  ansible.proxmox.proxmox_vm:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    node: pve01
    vmid: 100
    memory: 4096

- name: Delete a template
  ansible.proxmox.proxmox_vm:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    node: pve01
    vmid: 100
    state: absent
"""

RETURN = r"""
template:
  description:
    - Whether the VM is a template after the operation.
    - In check mode, represents the predicted template state without modifying the VM.
  returned: success
  type: bool
  sample: true
task_upid:
  description: UPID of the completed Proxmox template-conversion task.
  returned: when conversion occurs
  type: str
  sample: 'UPID:pve01:00000001:00000001:00000001:qmtemplate:100:root@pam:'
"""

import re

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_mutually_exclusive,
    proxmox_required_together,
    proxmox_task_argument_spec,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_action import ProxmoxActionModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_power import ProxmoxPower
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask


class ProxmoxVmTemplateModule(ProxmoxPower, ProxmoxActionModule):
    """Convert one stopped QEMU/KVM VM through the shared action lifecycle."""

    result_key = "template"

    @staticmethod
    def _is_template_status(status):
        """Return whether current VM status marks the VM as a template.

        Args:
            status: Current QEMU status mapping.

        Returns:
            Whether the response has template set to one.
        """
        return isinstance(status, dict) and status.get("template") in (1, "1", True)

    def is_action_needed(self):
        """Read current VM status and decide whether conversion is needed.

        Returns:
            Whether the selected VM is not already a template.
        """
        self.client.validate_pve_permissions(self.api, "/vms")
        self._current_status = self.get_status()
        if self._is_template_status(self._current_status):
            return False
        if not isinstance(self._current_status, dict):
            self.module.fail_json(msg="Unable to determine VM status before template conversion.")

        status = self._current_status.get("status")
        if status not in ("running", "stopped"):
            self.module.fail_json(msg="Unable to determine VM power state before template conversion.")
        self._needs_stop = status != "stopped" or self._current_status.get("lock") == "suspended"
        if self._needs_stop and self.module.params.get("power_cycle", "fail") == "fail":
            self.module.fail_json(
                msg="VM {0} must be fully stopped before converting it to a template; set power_cycle=off to stop it.".format(
                    self.module.params["vmid"]
                )
            )
        self._validate_template_disk()
        return True

    def _validate_template_disk(self):
        """Verify the optional disk selector names a configured VM disk."""
        disk = self.module.params.get("disk")
        if disk is None:
            return
        vmid = self.module.params["vmid"]
        config = self.call_api(
            "Retrieving VM {0} configuration for template conversion".format(vmid),
            self.vm_resource().config.get,
        )
        drive = config.get(disk) if re.fullmatch(r"(?:ide|sata|scsi|virtio)\d+", disk) else None
        if not isinstance(drive, str) or not drive or "media=cdrom" in drive.split(","):
            self.module.fail_json(msg="Disk {0} is not a configured VM disk device on VM {1}.".format(disk, vmid))

    def perform_action(self):
        """Convert the VM and retain its completed task identifier.

        Returns:
            True after the VM has been verified as a template.
        """
        vmid = self.module.params["vmid"]
        node = self.node()
        if self._needs_stop:
            if self._current_status.get("lock") == "suspended":
                self.set_state("resume")
            self.set_state("stop")
        options = {}
        if self.module.params.get("disk") is not None:
            options["disk"] = self.module.params["disk"]
        self._task_upid = self.call_api(
            "Converting VM {0} on node {1} to a template".format(vmid, node),
            self.vm_resource().template.post,
            **options
        )
        if not isinstance(self._task_upid, str) or not self._task_upid.startswith("UPID:"):
            self.module.fail_json(msg="VM {0} template conversion did not return a task UPID.".format(vmid))
        ProxmoxTask(self.module, client=self.client).wait_for_task(self._task_upid)
        if not self._is_template_status(self.get_status()):
            self.module.fail_json(msg="VM {0} did not reach the template state.".format(vmid))
        return True

    def get_action_result(self):
        """Return the desired template state for no-op and check-mode results.

        Returns:
            True, indicating the desired state is a template.
        """
        return True

    def prepare_result(self, changed, resource=None, **values):
        """Include the completed conversion task UPID in the module result.

        Args:
            changed: Whether conversion occurred or is predicted.
            resource: Whether the VM is now or will be a template.
            **values: Additional top-level result fields.

        Returns:
            The action result with an optional task_upid.
        """
        result = super().prepare_result(changed, resource, **values)
        if getattr(self, "_task_upid", None) is not None:
            result["task_upid"] = self._task_upid
        return result


def main():
    """Parse arguments and convert the requested VM into a template."""
    module = AnsibleModule(
        argument_spec=proxmox_task_argument_spec({
            "vmid": {"type": "int", "required": True},
            "disk": {"type": "str"},
            "power_cycle": {"type": "str", "choices": ["fail", "off"], "default": "fail"},
        }),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxVmTemplateModule(module).execute_action_module()


if __name__ == "__main__":
    main()
