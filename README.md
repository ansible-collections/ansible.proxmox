# Ansible Proxmox Collection

Ansible automation for managing the Proxmox platform across Proxmox VE (PVE)
and Proxmox Backup Server (PBS).

## Description

The `ansible.proxmox` collection is intended to help Ansible operators automate
the broader Proxmox ecosystem: Proxmox VE (PVE), Proxmox Backup Server (PBS),
and Proxmox Datacenter Manager (PDM). Its planned module families span
datacenter, cluster and HA operations; nodes, pools, storage and Ceph;
networking, SDN, and firewalls; users, roles, tokens, certificates, and
notifications; VM and container lifecycles and advanced features; and backup,
restore, replication, and node services.

## Requirements

- **Ansible Core**: `>=2.16.0`.
- **Python**: `>=3.12`.
- **Proxmox permissions**: Administrator permissions on the target objects.
- `proxmoxer>=2.3.0` is required for all modules and backends.
- `requests` is required when using HTTPS (`api_backend: https`).
- `openssh_wrapper` and an OpenSSH client executable are required when using OpenSSH (`api_backend: openssh`).

Installing the collection does not install these Python or system dependencies.
They must be available in the execution environment where the modules run. The
collection declares them in `meta/ee-requirements.txt` and `meta/ee-bindep.txt`;
include this metadata when building an execution environment with
`ansible-builder`. The OpenSSH client package is `openssh-clients` on RPM-based systems.

## Installation

Red Hat customers should install certified collections from [Red Hat Ansible
Automation Hub](https://console.redhat.com/ansible/automation-hub). Red Hat does
not support installing collections from GitHub. Installing this collection
does not require Proxmox credentials; configure API or SSH credentials when
running its modules.

### Installing a collection

Install this collection with the Ansible Galaxy command-line tool:

```bash
ansible-galaxy collection install ansible.proxmox
```

### Installing from a requirements file

You can include this collection in a `requirements.yml` file and install it
with `ansible-galaxy collection install -r requirements.yml`:

```yaml
collections:
  - name: ansible.proxmox
```

## Use cases

### Retrieve VM information over HTTPS

Use `proxmox_vm_info` to inspect VMs on a PVE node. Set `api_host` to the PVE
hostname or address. For VM operations, set `api_service` to `PVE` (the
default). HTTPS is the default `api_backend`. Set `api_timeout` to change the
default five-second timeout.

For authentication, use either `api_user` with `api_password`, or
`api_token_id` with `api_token_secret`. A token ID may include its user as
`user@realm!token`, in which case `api_user` can be omitted. `api_otp` is
available for password authentication. Keep secrets in Ansible Vault or another
secret manager. TLS certificate validation is enabled by default; set
`ca_path` to a custom CA bundle when needed. `api_port` overrides the service
port, which otherwise defaults to 8006 for PVE or 8007 for PBS.

```yaml
- name: Retrieve VM information from PVE
  ansible.proxmox.proxmox_vm_info:
    api_host: "{{ proxmox_api_host }}"
    api_service: PVE
    api_backend: https
    api_user: "{{ proxmox_api_user }}"
    api_token_id: "{{ proxmox_api_token_id }}"
    api_token_secret: "{{ vault_proxmox_api_token_secret }}"
    validate_certs: true
    ca_path: "{{ proxmox_ca_path }}"
    node: pve01
```

### Retrieve VM information over OpenSSH

OpenSSH is an alternative transport for VM operations. Set `api_backend` to
`openssh` and provide `ssh_user`; `api_host`, `api_service`, and `api_timeout`
retain their shared meanings. Authenticate with `ssh_password` (also available
through `PROXMOX_SSH_PASSWORD`), or configure an SSH key or agent with
`ssh_identity_file`, `ssh_config_file`, or `ssh_forward_agent`. `ssh_port`
overrides the default port 22. HTTPS credentials, OTP, and CA settings are not
used by this backend.

```yaml
- name: Retrieve VM information over SSH
  ansible.proxmox.proxmox_vm_info:
    api_host: "{{ proxmox_api_host }}"
    api_service: PVE
    api_backend: openssh
    ssh_user: root
    ssh_password: "{{ vault_proxmox_ssh_password }}"
    node: pve01
```

### Create a VM

Use `proxmox_vm` to create, update, or remove a QEMU/KVM VM. The basic lifecycle
requires the PVE `node` and a unique `vmid`; `state` defaults to `present`.
Connection and authentication parameters are the same as for VM information.

```yaml
- name: Ensure a basic VM exists
  ansible.proxmox.proxmox_vm:
    api_host: "{{ proxmox_api_host }}"
    api_user: "{{ vault_proxmox_api_user }}"
    api_password: "{{ vault_proxmox_api_password }}"
    node: pve01
    vmid: 100
    name: app01
    state: present

```

## Testing

The collection's test suite has unit tests for shared utilities and
module-specific behavior, plus integration targets for exercising modules
against configured Proxmox services.

### Platforms and versions

- Ansible Core 2.16 or later is required. CI unit tests cover Python 3.11
  through 3.13; integration CI covers Ansible Core 2.16, 2.18, 2.20, and 2.21.
- Current live integration coverage targets Proxmox VE (PVE). The repository
  does not declare a fixed PVE or PBS product-version support range, and there
  is currently no PBS resource integration target.

### Unit tests

Unit tests live under `tests/unit/` and run without a Proxmox server. They cover
shared connection and resource utilities as well as module behavior. Run them
from the collection layout with:

```bash
ansible-test units
```

### Integration tests

Integration targets live under `tests/integration/targets/` and exercise
modules against a live, configured Proxmox environment. The current PVE target
is `proxmox_vm`; it requires a reachable server, a configured node and storage,
and credentials with the required privileges. Generate
`tests/integration/integration_config.yml` as described under Development
checks, then run:

```bash
ansible-test integration --allow-unsupported
```

## Contributing

Before contributing, read the
[collection contribution guidelines](https://github.com/ansible-collections/ansible.proxmox/blob/main/CONTRIBUTING.md)
and the [Ansible Community Code of Conduct](https://github.com/ansible-collections/ansible.proxmox/blob/main/CODE_OF_CONDUCT.md).

For community questions and discussion, use the Ansible Forum's
[Proxmox tag](https://forum.ansible.com/tag/proxmox) or
[collections tag](https://forum.ansible.com/tag/collections). Report bugs and
request changes through the [GitHub issue tracker](https://github.com/ansible-collections/ansible.proxmox/issues).

## Support

This collection is maintained by Red Hat eco-ansible-content.

As Red Hat Ansible Certified Content, this collection is entitled to support
through Ansible Automation Platform (AAP) using the **Create issue** button on
the top right corner. If a support case cannot be opened with Red Hat and the
collection has been obtained either from Galaxy or GitHub, there may be
community help available on the [Ansible Forum](https://forum.ansible.com/).

Support team contacts:

- GitHub: [eco-ansible-content](https://github.com/orgs/ansible-collections/teams/eco-ansible-content)
- Email: [eco-ansible@redhat.com](mailto:eco-ansible@redhat.com)

## Release notes and roadmap

Release notes are published in the collection's generated
[changelog](https://github.com/ansible-collections/ansible.proxmox/blob/main/CHANGELOG.md).
No public roadmap is currently available. For Ansible Automation Platform
support timelines, see the [Red Hat Ansible Automation Platform Life Cycle](https://access.redhat.com/support/policy/updates/ansible-automation-platform).

## Related Information

- [Proxmox VE documentation](https://pve.proxmox.com/pve-docs/)
- [Proxmox Backup Server documentation](https://pbs.proxmox.com/docs/)
- [Ansible user guide](https://docs.ansible.com/projects/ansible/latest/user_guide/index.html)
- [Ansible collection requirements](https://docs.ansible.com/projects/ansible/latest/community/collection_contributors/collection_requirements.html)
- [Important announcements for collection maintainers](https://github.com/ansible-collections/news-for-maintainers)

## License

GNU General Public License v3.0 or later. See [LICENSE](https://github.com/ansible-collections/ansible.proxmox/blob/main/LICENSE).
