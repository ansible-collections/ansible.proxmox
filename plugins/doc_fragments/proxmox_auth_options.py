# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    """Documentation for Proxmox authentication options."""

    DOCUMENTATION = r"""
options:
  api_user:
    description:
      - Proxmox account name for HTTPS authentication.
      - Uses the E(PROXMOX_USER) environment variable when omitted.
      - May be omitted for token authentication when O(api_token_id) contains C(user@realm!token).
    type: str
  api_password:
    description:
      - Account password for HTTPS password authentication.
      - Uses the E(PROXMOX_PASSWORD) environment variable when omitted.
    type: str
  api_token_id:
    description:
      - API token name, or a complete C(user@realm!token) identifier.
      - Uses the E(PROXMOX_TOKEN_ID) environment variable when omitted.
    type: str
  api_token_secret:
    description:
      - API token secret for HTTPS token authentication.
      - Uses the E(PROXMOX_TOKEN_SECRET) environment variable when omitted.
    type: str
  api_otp:
    description:
      - One-time password used with HTTPS password authentication.
      - Uses the E(PROXMOX_OTP) environment variable when omitted.
    type: str
"""
