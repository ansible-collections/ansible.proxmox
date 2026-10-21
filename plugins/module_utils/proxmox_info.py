# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from .proxmox_base import ProxmoxBase


class ProxmoxInfoModule(ProxmoxBase):
    """Template method for read-only modules."""

    def get_info(self):
        raise NotImplementedError("get_info must be implemented")

    def execute_info_module(self):
        self.exit(changed=False, resource=self.get_info())

    def execute(self):
        self.execute_info_module()
