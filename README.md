# Ansible Proxmox Collection

The `ansible.proxmox` collection provides Ansible modules for Proxmox VE (PVE)
and Proxmox Backup Server (PBS). Its shared connection layer supports HTTPS
with password or API-token authentication, and OpenSSH using a password, SSH
agent, or identity file.

## Requirements

Install these Python packages in the environment used by Ansible on the
controller:

```bash
python -m pip install -r requirements.txt
```

OpenSSH connections also require an OpenSSH client executable. The collection's
execution-environment metadata declares the Python and system package
dependencies.

Installing the collection with `ansible-galaxy` does not install Python packages.
Install `requirements.txt` in the controller environment, or build an execution
environment with `ansible-builder` to install the dependencies declared under
`meta/`.

## Install from a checkout

Build and install the collection archive:

```bash
ansible-galaxy collection build
ansible-galaxy collection install ansible-proxmox-1.0.0.tar.gz
```

## Test a connection

The `proxmox_connection_test` module retrieves the API version, which verifies
that the selected service, transport, and credentials work:

```yaml
---
- name: Test Proxmox API access
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Test PVE over HTTPS with an API token
      ansible.proxmox.proxmox_connection_test:
        api_host: "{{ proxmox_api_host }}"
        api_user: "{{ proxmox_api_user }}"
        api_token_id: "{{ proxmox_api_token_id }}"
        api_token_secret: "{{ proxmox_api_token_secret }}"
        api_service: PVE
        api_backend: https
        validate_certs: true
      register: proxmox_connection

    - name: Display the API version
      ansible.builtin.debug:
        var: proxmox_connection.version
```

For a private CA, provide `ca_path`. Keep credentials in Ansible Vault or a
secret manager. HTTPS password authentication uses `api_password` instead of
the token fields. For OpenSSH, set `api_backend: openssh` and `ssh_user` to the
SSH login. Authenticate with `ssh_password`, an SSH agent, or an identity file;
the password can also be supplied through `PROXMOX_SSH_PASSWORD`. `api_password`
remains exclusive to HTTPS, and `api_user` remains the HTTPS account name, so
both identities can be configured in shared defaults without changing variable
names.

Use `api_port` (or `PROXMOX_PORT`) to override the HTTPS port and
`ssh_port` (or `PROXMOX_SSH_PORT`) to override the SSH port. If omitted,
the HTTPS backend uses the service default (PVE: 8006, PBS: 8007) and OpenSSH
uses port 22.

Connection options can be shared with `module_defaults` under the
`group/ansible.proxmox.proxmox` action group. Backend-specific defaults can be
scoped to a block when a play uses more than one transport.

## Development checks

Install local development and test dependencies with:

```bash
python -m pip install -r tests/unit/requirements.txt
```

Run the collection checks from its collection layout with:

```bash
ansible-test sanity
ansible-test units
ansible-test integration proxmox_module_utils
```

Live integration tests load credentials and environment details from
`tests/integration/integration_config.yml`. Generate it from environment
variables before running a Proxmox integration target:

```bash
PROXMOX_HOST=pve.example.test \
PROXMOX_USER=root@pam \
PROXMOX_PASSWORD=secret \
tests/integration/generate_integration_config.sh
ansible-test integration proxmox_vm --allow-unsupported
```

The `proxmox_dummy_resource` module in `plugins/modules/` is a development
example used by the non-networked integration target. It is not intended as a
production Proxmox resource module.

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
