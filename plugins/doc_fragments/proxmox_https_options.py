# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation for the Proxmox HTTPS backend."""

    DOCUMENTATION = r"""
options:
  validate_certs:
    description:
      - Validate the remote HTTPS certificate.
      - Uses the E(PROXMOX_VALIDATE_CERTS) environment variable when omitted.
    type: bool
    default: true
  ca_path:
    description:
      - CA bundle used to validate HTTPS certificates.
      - Uses the E(PROXMOX_CA_PATH) environment variable when omitted.
      - Valid only when O(api_backend=https) and O(validate_certs=true).
    type: path
requirements:
  - requests
"""
