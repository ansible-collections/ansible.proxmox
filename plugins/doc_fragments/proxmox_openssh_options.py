# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation for the Proxmox OpenSSH backend."""

    DOCUMENTATION = r"""
options:
  ssh_user:
    description:
      - SSH login name used when C(api_backend=openssh).
      - Uses the E(PROXMOX_SSH_USER) environment variable when omitted.
    type: str
  ssh_port:
    description:
      - SSH port used when C(api_backend=openssh).
      - When omitted, proxmoxer uses the OpenSSH default port, 22.
      - Uses the E(PROXMOX_SSH_PORT) environment variable when omitted.
    type: int
  ssh_config_file:
    description:
      - OpenSSH client configuration file.
      - Uses the E(PROXMOX_SSH_CONFIG_FILE) environment variable when omitted.
    type: path
  ssh_identity_file:
    description:
      - OpenSSH private identity file.
      - Uses the E(PROXMOX_SSH_IDENTITY_FILE) environment variable when omitted.
    type: path
  ssh_forward_agent:
    description:
      - Forward the SSH authentication agent when using OpenSSH.
      - Uses the E(PROXMOX_SSH_FORWARD_AGENT) environment variable when omitted.
    type: bool
    default: false
requirements:
  - openssh_wrapper
  - OpenSSH client
"""
