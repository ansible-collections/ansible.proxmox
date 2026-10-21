# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation shared by Proxmox modules."""

    DOCUMENTATION = r"""
options:
  api_host:
    description:
      - Proxmox server hostname or IP address.
      - Uses the E(PROXMOX_HOST) environment variable when omitted.
    type: str
    required: true
notes:
  - Explicit module parameters take precedence over their corresponding environment variables.
  - HTTPS authentication requires either O(api_password), or both O(api_token_id) and O(api_token_secret).
  - VM modules require the configured identity to have the C(Administrator) role propagated on C(/vms).
  - SSH authentication requires O(ssh_user) and an OpenSSH key or agent.
author:
  - Ansible Eco Content Team (@eco-ansible-content)
"""
