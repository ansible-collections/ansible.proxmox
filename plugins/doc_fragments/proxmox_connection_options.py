# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation for options common to every Proxmox connection."""

    DOCUMENTATION = r"""
options:
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
  api_port:
    description:
      - HTTPS API port used when C(api_backend=https).
      - When omitted, proxmoxer selects the service default (8006 for PVE or
        8007 for PBS).
      - Uses the E(PROXMOX_PORT) environment variable when omitted.
    type: int
  api_timeout:
    description:
      - Connection and request timeout in seconds.
      - Uses the E(PROXMOX_API_TIMEOUT) environment variable when omitted.
    type: int
    default: 5
requirements:
  - proxmoxer >= 2.3.0
"""
