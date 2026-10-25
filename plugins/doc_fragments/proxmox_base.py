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
  api_service:
    description:
      - Proxmox API service to access.
      - Uses the E(PROXMOX_SERVICE) environment variable when omitted.
    type: str
    choices: [PVE, PBS]
    default: PVE
  api_backend:
    description:
      - Transport backend used by proxmoxer.
      - Uses the E(PROXMOX_BACKEND) environment variable when omitted.
    type: str
    choices: [https, openssh]
    default: https
notes:
  - Explicit module parameters take precedence over their corresponding environment variables.
  - Modules require the configured identity to have the C(Administrator) role propagated.
  - HTTPS authentication requires either O(api_password), or both O(api_token_id) and O(api_token_secret).
  - SSH authentication requires O(ssh_user) and an OpenSSH key, agent, or O(ssh_password).
author:
  - Ansible Eco Content Team (@eco-ansible-content)
requirements:
  - proxmoxer >= 2.3.0
  - requests
"""
