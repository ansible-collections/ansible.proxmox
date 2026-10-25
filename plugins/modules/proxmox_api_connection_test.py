#!/usr/bin/python
# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: proxmox_api_connection_test
short_description: Verify API access to Proxmox VE or Proxmox Backup Server
version_added: "1.0.0"
description:
  - Opens a connection using the shared Proxmox collection connection options.
  - Retrieves the API version to verify that authentication and transport work.
  - Before using OpenSSH, establish non-interactive SSH access from the Ansible execution environment to O(api_host) as O(ssh_user).
  - Configure access with an identity file or agent before running the module.
  - Use O(api_port) to override the HTTPS port and O(ssh_port) to override the OpenSSH port.
author:
  - Steve Fulmer (@stevefulme1)
  - Shahar Golshani (@shahargolshani)
extends_documentation_fragment:
  - ansible.proxmox.proxmox_base
  - ansible.proxmox.proxmox_https_options
  - ansible.proxmox.proxmox_openssh_options
"""

EXAMPLES = r"""
- name: Check PVE over HTTPS with a username and password
  ansible.proxmox.proxmox_api_connection_test:
    api_host: "{{ proxmox_api_host }}"
    api_user: "{{ proxmox_api_user }}"
    api_password: "{{ vault_proxmox_api_password }}"
    api_service: PVE
    api_backend: https
    validate_certs: true
    ca_path: "{{ proxmox_ca_path }}"

- name: Check PVE over HTTPS with an API token
  ansible.proxmox.proxmox_api_connection_test:
    api_host: "{{ proxmox_api_host }}"
    api_user: "{{ proxmox_api_user }}"
    api_token_id: "{{ proxmox_api_token_id }}"
    api_token_secret: "{{ vault_proxmox_api_token_secret }}"
    api_service: PVE
    api_backend: https
    validate_certs: true
    ca_path: "{{ proxmox_ca_path }}"

- name: Check PVE over OpenSSH with an SSH key
  ansible.proxmox.proxmox_api_connection_test:
    api_host: "{{ proxmox_api_host }}"
    api_service: PVE
    api_backend: openssh
    ssh_user: "{{ proxmox_ssh_user }}"
    ssh_identity_file: "{{ proxmox_ssh_identity_file }}"
"""

RETURN = r"""
version:
  description: Version data returned by the Proxmox API.
  returned: success
  type: dict
  sample: {"version": "9.2", "release": "9.2.2", "repoid": "..."}
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox import (
    proxmox_argument_spec,
    proxmox_mutually_exclusive,
    proxmox_required_together,
)
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_info import ProxmoxInfoModule


class ProxmoxConnectionInfoModule(ProxmoxInfoModule):
    """Retrieve version information through any supported connection."""

    result_key = "version"

    def get_info(self):
        return self.call_api("Retrieving the Proxmox API version", self.api.version.get)


def main():
    module = AnsibleModule(
        argument_spec=proxmox_argument_spec(),
        supports_check_mode=True,
        required_together=proxmox_required_together(),
        mutually_exclusive=proxmox_mutually_exclusive(),
    )
    ProxmoxConnectionInfoModule(module).execute()


if __name__ == "__main__":
    main()
