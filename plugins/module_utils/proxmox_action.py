# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from .proxmox_base import ProxmoxBase


class ProxmoxActionModule(ProxmoxBase):
    """Template method for idempotent imperative actions."""

    def is_action_needed(self):
        return True

    def perform_action(self):
        raise NotImplementedError("perform_action must be implemented")

    def get_action_result(self):
        return {}

    def execute_action_module(self):
        if not self.is_action_needed():
            self.exit(changed=False, resource=self.get_action_result())

        if self.module.check_mode:
            self.exit(changed=True, resource=self.get_action_result())

        result = self.perform_action()
        if result is None:
            result = self.get_action_result()
        self.exit(changed=True, resource=result)

    def execute(self):
        self.execute_action_module()
