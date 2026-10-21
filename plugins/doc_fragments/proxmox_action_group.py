# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation for the collection's module-defaults action group."""

    DOCUMENTATION = r"""
options: {}
attributes:
  action_group:
    description: Use C(group/ansible.proxmox.proxmox) in C(module_defaults) to set shared defaults.
    support: full
    membership:
      - ansible.proxmox.proxmox
"""
