# ANSTRAT-2121: Proxmox collection project plan

- **Analysis date:** 2026-10-26.
- **Project:** `ansible.proxmox`.
- **Working repository:** `ansible-collections/ansible.proxmox`.
- **Strategy item:** [ANSTRAT-2121](https://redhat.atlassian.net/browse/ANSTRAT-2121).
- **Implementation baseline:** [PR #1 — Initial Code base](https://github.com/ansible-collections/ansible.proxmox/pull/1), inspected at commit `38ef0e19a1e45315edf87164b42da11d860f19f5`.
- **Review scope:** The strategy item, all 21 actual child epics, their 125 child work items, the collection PR, the older prototype referenced by Jira, public user reports, and vendor documentation.
- **Status:** Proposed delivery plan. Recommended sequencing and lab architecture are engineering conclusions; customer-specific requirements still need confirmation.

## 1. Purpose and intended outcomes

The project should deliver reliable, supported Ansible automation across Proxmox VE (PVE), Proxmox Backup Server (PBS), and Proxmox Datacenter Manager (PDM).

The [strategy item](https://redhat.atlassian.net/browse/ANSTRAT-2121) identifies enterprise adoption of Proxmox, including organizations reconsidering VMware, as the business opportunity. The collection should let those organizations provision infrastructure, operate workloads, protect data, and recover services through consistent automation.

The strongest current justification is supported enterprise automation with predictable behavior across the ecosystem. The strategy item's comparison with `community.proxmox` needs updating: the community collection now includes SDN, Ceph, identity, certificates, and HA functionality. Historical claims such as approximately 15 modules or no SDN coverage should not drive present-day scope decisions. Use the [current community module inventory](https://github.com/ansible-collections/community.proxmox/tree/main/plugins/modules) to distinguish remaining coverage gaps from quality, consistency, and support requirements.

### Success criteria

1. A usable workload can be provisioned repeatedly without duplicates or unnecessary changes.
2. Operators can reconcile configuration after manual changes and perform maintenance predictably.
3. Long-running operations report actual completion or failure, with useful task information.
4. A backup can be restored into a working guest, with its data and connectivity verified.
5. Automation works from the intended execution environment with realistic credentials, CA trust, permissions, and network paths.
6. Each delivered capability has documentation, meaningful unit coverage, live integration coverage, check-mode behavior, and an explicit compatibility contract.

The VMware business motivation does not establish a complete VMware-to-Proxmox migration workflow. Source discovery, conversion/import, guest drivers, networking, cutover, and rollback require a separate requirements assessment before promising that outcome.

## 2. Evidence and implementation baseline

### Current collection PR

PR #1 provides:

- Shared connection, base, resource, information, action, and asynchronous-task utilities.
- `proxmox_api_connection_test`.
- `proxmox_vm` and `proxmox_vm_info`.
- Unit tests and a live VM integration target.
- PVE/PBS service selection and HTTPS/OpenSSH connection options, subject to backend support.

At the analysis snapshot, GitHub reported successful integration checks across ansible-core 2.16, 2.18, 2.20, and 2.21. This is evidence for the initial VM integration target, not proof of the remaining domains. See the [integration run](https://github.com/ansible-collections/ansible.proxmox/actions/runs/40292139165).

The local checkout was clean on `main` at `bb94e30` when inspected. It contained the collection scaffold; PR #1's implementation was not present in that checkout.

### Scope reconciliation required

| Finding | Required planning action |
|---|---|
| The parent description claims 106 implemented modules and contains an outdated epic list with incorrect IDs. | Use actual Jira parent relationships and the target collection as the delivery baseline. |
| There are 21 actual child epics and 125 child tickets. | Reconcile estimates and progress reporting against this hierarchy. Ticket counts are not equivalent to completed module counts. |
| PBS specifies 25 modules but has 18 child tickets. | Add or explicitly defer the seven unmatched module requirements. |
| PDM adds 19 modules. | Treat it as a distinct product workstream with its own connection, identity, and integration requirements. |
| VM lifecycle includes a new power-state task, while the PR introduces `proxmox_vm` rather than the older `proxmox_vm_config` name. | Agree on module names and responsibility boundaries before expanding implementation. |
| None of the 21 inspected epics has explicit dependency links. | Record the engineering dependencies from this plan in Jira after team agreement. |
| Jira refers to the older `ProxmoxModule` pattern. | Align requirements with the resource/info/action/task hierarchy introduced by the current PR. |

The older [prototype repository](https://github.com/stevefulme1/ansible-proxmox-modules) is reference material. Its file inventory and implementation claims are not delivery evidence for the target collection. PR #1 already replaces several prototype patterns, including service selection and task waiting.

The seven additional PBS requirements without matching child tickets in the inspected hierarchy are:

- `proxmox_pbs_tape_changer`.
- `proxmox_pbs_tape_encryption_key`.
- `proxmox_pbs_tfa`.
- `proxmox_pbs_notification_endpoint`.
- `proxmox_pbs_notification_matcher`.
- `proxmox_pbs_node_config`.
- `proxmox_pbs_certificate`.

## 3. Delivery approach

Deliver complete customer workflows incrementally. Begin with the existing PR and a preconfigured lab; infrastructure fixtures can be prepared before the collection automates their setup.

Treat the sequence below as dependency-aware ordering, not a requirement to finish each broad epic before starting the next. Several epics combine foundational tasks with specialized features and should be split into smaller delivery slices.

### Foundation milestone: validate PR #1

Before widening module development:

- Reproduce the existing VM integration target from the intended execution environment.
- Confirm the common resource/info/action/task contracts using the current implementation.
- Define the PVE/PBS product-version support range and supported transport combinations.
- Establish VMID reservations, cleanup, fixture ownership, and test-run isolation.
- Verify task completion/failure behavior and define configurable operation timeouts for future long-running modules.
- Decide whether broad Administrator permissions are an initial support constraint or whether operation-specific privilege checks are required for the first release.

### Recommended epic order

The order is derived from integration-test fixture dependencies, not from Jira numbering, ticket count, or the priority implied by an epic name. For every module, classify its role as one of:

- **Foundation:** connection, error handling, asynchronous task polling, comparison, check mode, and cleanup behavior used by all later modules.
- **Observer:** an `_info` module used to discover the lab and independently assert the state produced by another module.
- **Producer:** a resource module that creates a reusable test fixture such as a user, storage, network, VM, datastore, or remote.
- **Consumer/action:** a module that needs an existing fixture, such as clone, migrate, backup, restore, HA, replication, or cross-cluster operations.

An earlier module may prepare and clean up a later module's test fixtures. A later module must not be required to prove that an earlier module works. For example, `proxmox_vm_info` can verify `proxmox_vm_config`; `proxmox_vm_agent` must not be the only way to verify VM creation because it additionally depends on a booted guest, networking, and the guest agent.

This rule means the table is an order of **epic entry points**, not a mandate to complete an entire epic before starting the next. `proxmox_task_info`, `proxmox_cluster_info`, and `proxmox_node_disks_info` move into early foundation waves even though their epics contain later features. Conversely, HA, replication, tape, and PDM migration remain late even when their epics contain some simple information modules.

| Order | Epic | Child tickets | Dependency rationale and delivery slice |
|---:|---|---:|---|
| 1 | [ACA-5581 — Pool & Node Management](https://redhat.atlassian.net/browse/ACA-5581) | 7 | Node discovery, DNS, time, and pools establish reliable fixtures, resource identity, and placement. |
| 2 | [ACA-5554 — User & Identity](https://redhat.atlassian.net/browse/ACA-5554) | 4 | Establish automation users, groups, roles, and tokens. Bootstrap credentials are needed before these modules can manage steady-state access. |
| 3 | [ACA-5585 — Access & Security Advanced](https://redhat.atlassian.net/browse/ACA-5585) | 6 | Pull ACLs and permission inspection forward: creating a token alone does not grant usable access. Realms, TFA, and firewall inspection can follow their respective prerequisites. |
| 4 | [ACA-5588 — Lower Priority PVE](https://redhat.atlassian.net/browse/ACA-5588) | 14 | Pull task inspection, disk discovery, SDN state inspection, and pending-change handling forward. Device mappings, subscriptions, and wake-on-LAN can remain later. |
| 5 | [ACA-5553 — Certificates](https://redhat.atlassian.net/browse/ACA-5553) | 2 | Establish trusted API access. ACME additionally depends on working DNS and challenge infrastructure. A pretrusted lab CA can bootstrap earlier tests. |
| 6 | [ACA-5555 — Node Network](https://redhat.atlassian.net/browse/ACA-5555) | 1 | Bridges, bonds, and VLANs underpin guest connectivity and SDN. Preserve a management path while testing changes. |
| 7 | [ACA-5577 — Storage Management](https://redhat.atlassian.net/browse/ACA-5577) | 4 | Images, disks, templates, migration, and backups require correctly configured storage. Register Ceph-backed storage only after its Ceph prerequisites exist. |
| 8 | [ACA-5582 — Cluster Operations](https://redhat.atlassian.net/browse/ACA-5582) | 3 | Establish cluster configuration and observability before multi-node operations. This epic includes join information, not a complete cluster-formation implementation. |
| 9 | [ACA-5578 — VM Lifecycle](https://redhat.atlassian.net/browse/ACA-5578) | 7 | Continue from PR #1. Prioritize power operations, then templates, cloning, snapshots, and migration. Reconcile the old configuration-module scope with `proxmox_vm`. |
| 10 | [ACA-5586 — VM Advanced Features](https://redhat.atlassian.net/browse/ACA-5586) | 5 | Cloud-init, guest agent, disks, and pending changes turn VM creation into usable workload provisioning. |
| 11 | [ACA-5579 — Container Lifecycle](https://redhat.atlassian.net/browse/ACA-5579) | 4 | Reuse shared patterns while validating LXC-specific templates, storage, networking, and migration behavior. |
| 12 | [ACA-5551 — Firewall](https://redhat.atlassian.net/browse/ACA-5551) | 5 | Validate cluster, host, and guest scopes against real resources. Create referenced aliases, IP sets, and groups before rules that consume them. |
| 13 | [ACA-5556 — Notifications](https://redhat.atlassian.net/browse/ACA-5556) | 2 | Configure endpoints before matchers and establish observable failures before protection and maintenance workflows expand. |
| 14 | [ACA-5589 — PBS](https://redhat.atlassian.net/browse/ACA-5589) | 18 | Start with PBS identity, ACLs, datastores, and namespaces. Then add retention, verification, synchronization, and tape. Reconcile the 25-module epic scope first. |
| 15 | [ACA-5580 — Backup & Restore](https://redhat.atlassian.net/browse/ACA-5580) | 3 | Requires workloads and backup storage. PVE backups may use other storage; the PBS scenario additionally depends on PBS foundations and PVE storage registration. |
| 16 | [ACA-5550 — SDN](https://redhat.atlassian.net/browse/ACA-5550) | 3 | Begin with Simple/VLAN zones, then VNets and subnets. Verify configuration activation and guest connectivity. |
| 17 | [ACA-5584 — SDN Advanced](https://redhat.atlassian.net/browse/ACA-5584) | 4 | Add controllers and external DNS/IPAM integrations. Pull the controller prerequisite ahead of EVPN-zone tests in ACA-5550. |
| 18 | [ACA-5583 — Ceph](https://redhat.atlassian.net/browse/ACA-5583) | 7 | Requires suitable nodes, disks, networks, installed packages, and initialization. Establish monitors/managers/OSDs and pools before consuming their storage. |
| 19 | [ACA-5552 — Cluster & HA](https://redhat.atlassian.net/browse/ACA-5552) | 3 | Pull `cluster_info` forward. HA behavior follows proven quorum, workload mobility, and suitable storage. Resolve legacy groups versus current affinity rules. |
| 20 | [ACA-5587 — Replication, Tags & Node Services](https://redhat.atlassian.net/browse/ACA-5587) | 4 | Tags and package/service helpers can move earlier. Replication needs its own supported storage and multi-node scenario. |
| 21 | [ACA-7279 — PDM](https://redhat.atlassian.net/browse/ACA-7279) | 19 | Deliver fleet operations after single-cluster behavior is reliable. Start with connections, identity, remotes, and inventory, followed by cross-cluster actions. |

### Module-level build and test order

This is the working implementation sequence. Items in the same wave can be developed in parallel only when they do not depend on each other's fixtures.

| Wave | Build first | Fixtures or assertions enabled | Modules that can follow |
|---:|---|---|---|
| 0 | Shared connection/resource/info/action/task utilities; `proxmox_api_connection_test` | Authenticated API session, normalized results, check mode, task completion and failure handling | Every module family |
| 1 | `proxmox_node_info`, `proxmox_cluster_info`, `proxmox_task_info`, `proxmox_storage_info`, `proxmox_storage_status_info`, `proxmox_storage_content`, `proxmox_node_disks_info`, `proxmox_node_certs_info` | Lab discovery and independent read-back assertions without changing infrastructure | Node, storage, certificate, cluster, workload, and long-running action tests |
| 2 | `proxmox_user` → `proxmox_group` and `proxmox_role` → `proxmox_token` → `proxmox_acl`; then `proxmox_permission_info` | Least-privilege test principal with an independently verifiable effective permission set | All steady-state tests using collection-created credentials; realms and TFA as separate security scenarios |
| 3 | `proxmox_node_dns`, `proxmox_node_time`, `proxmox_node_hosts`, `proxmox_certificate`; `proxmox_node_network`; `proxmox_storage`; `proxmox_pool`/`proxmox_pool_info` | Trusted endpoint, bridge/VLAN, target storage, and placement fixtures | VM/LXC creation, templates, migration, ACME, SDN, backup and HA |
| 4 | Existing `proxmox_vm_config`/`proxmox_vm` and `proxmox_vm_info`; then `proxmox_vm_powerstate` | A uniquely named/numbered workload that can be created, read, stopped, started, and cleaned up | Snapshot, template, clone, disk, cloud-init, agent, firewall, backup, migration, pool and tag tests |
| 5 | `proxmox_vm_cloudinit`, `proxmox_vm_pending_info` → `proxmox_vm_pending_apply`, `proxmox_vm_disk`; then `proxmox_vm_template` → `proxmox_vm_clone`; `proxmox_vm_snapshot` | Bootable repeatable guest/template, mutable disks, pending-change assertions, clone and snapshot fixtures | Guest-agent validation, concurrency, restore, migration and HA |
| 6 | `proxmox_vm_agent`; `proxmox_tag`; `proxmox_firewall_alias`, `proxmox_firewall_ipset`, `proxmox_firewall_group` → `proxmox_firewall_rule`; firewall options/info modules | End-to-end guest reachability and higher-level resource references | Workload configuration, drift, firewall ordering and log tests |
| 7 | LXC template in storage → `proxmox_lxc_config` → snapshot/clone → migrate; SDN controller when needed → zone → VNet → subnet → apply/`proxmox_sdn_info`; DNS/IPAM/DHCP integrations afterward | Container and software-defined network fixtures with connectivity assertions | Advanced networking and multi-node workload tests |
| 8 | Backup-capable storage and booted VM → `proxmox_backup_job` → `proxmox_backup_info` → `proxmox_backup_restore` | A restored VM under a different VMID whose boot, data, and network can be verified | Recovery and failure-injection scenarios |
| 9 | Quorate cluster + shared storage + migratable VM → `proxmox_vm_migrate`; current HA placement primitive → `proxmox_ha_resource`; ZFS on two nodes → `proxmox_replication` | Proven workload mobility and failure recovery prerequisites | HA evacuation/failover and replication tests |
| 10 | PBS node/connection info; PBS realm/user → token → ACL; datastore → datastore info → namespace; then prune/GC/verify jobs | Authorized backup target with independently visible content and maintenance state | PVE-to-PBS backup/restore, retention and verification |
| 11 | Second PBS + `proxmox_pbs_remote` → sync job; tape drive → media pool → tape job; notification endpoint → matcher | Cross-PBS and hardware-backed fixtures | Off-site copy, ownership/filter, notification and tape recovery tests |
| 12 | Ceph bootstrap prerequisites → monitor/manager → OSD → pool → filesystem/MDS; `proxmox_ceph_info` throughout | Healthy Ceph storage fixture | Ceph-backed VM, migration, HA and backup scenarios |
| 13 | PDM connection support → PDM user/token/ACL and remote registration → remote/node/guest info → guest power → guest migration; PDM SDN/view/Ceph/update features afterward | Multiple registered remotes and cross-remote inventory with product-specific task handling | Fleet-wide and cross-cluster validation |

The arrows above mean a real test dependency. They do not mean the implementation should call one Ansible module from another. Modules should share `module_utils` code where appropriate, while integration playbooks compose modules to prepare fixtures and verify outcomes.

### Integration-test fixture rules

Each test target should declare its prerequisite fixtures and use the lowest-level reliable module available to create them. Use the matching `_info` module or direct API read-back for assertions. Cleanup must run in an `always` block and use the same resource module that owns the fixture.

| Test target | Prepare with | Verify with | Must already exist outside the target |
|---|---|---|---|
| Identity and ACL | Bootstrap administrator; user, group, role, token, ACL modules | `proxmox_permission_info` and authentication using the new token | One bootstrap credential and a reserved ACL path |
| VM lifecycle | Storage, bridge, optional pool; VM resource module | `proxmox_vm_info`, task status, and power state | Node, image/template source, VMID range, storage and bridge |
| Cloud-init and guest agent | VM/template, cloud-init data, power module | VM info plus guest-agent response and guest connectivity | Bootable cloud image, DHCP/static route, guest agent in image |
| Firewall | Alias/IP set/group before a rule that references them | Firewall reference/info/log APIs and traffic outcome | Reachable source and destination test guests |
| Migration and HA | VM, shared storage, network on both nodes | VM/cluster info plus node placement and connectivity | Quorate cluster and at least two compatible nodes |
| Backup and restore | VM with a marker file; backup target/job | Backup info, restored VM info, boot, marker file and connectivity | Backup-capable storage or PBS datastore |
| PBS synchronization | Users/ACLs and datastores on two PBS servers; remote registration | Datastore content/info on destination | Two independently reachable PBS installations |
| PDM cross-cluster migration | Two PVE remotes, source VM, network/storage mappings | PDM guest info and destination PVE VM info | PDM plus two compatible PVE remotes |

This structure prevents circular tests. For instance, VM migration is tested with a VM produced by the already-proven VM module, while the VM module is tested on one node and does not require migration. Backup restore is tested with an already-proven VM and backup target; neither VM creation nor datastore creation depends on restore.

### Important dependency chains

- Bootstrap access → automation identity → ACLs → steady-state automation credentials.
- Node network and storage fixtures → VM lifecycle → guest configuration → booted guest connectivity.
- Controller, where required → zone → VNet → subnet → apply configuration → verify guest traffic.
- PBS identity and ACLs → datastore → namespace → PVE PBS storage registration → backup → restore validation.
- PBS remote credentials and datastores on both sides → remote registration → synchronization and ownership/filter tests.
- Quorate PVE cluster and suitable storage → migratable workloads → HA placement and failure recovery.
- PDM connection and identity → remote registration → cross-remote inventory → cross-cluster guest operations.

Proxmox records SDN changes as pending before applying them cluster-wide. CRUD success alone does not establish that the network is active. See the [vendor SDN documentation](https://github.com/proxmox/pve-docs/blob/master/pvesdn.adoc).

Cluster installation, cluster formation, Ceph package installation/initialization, and external-service deployment are lab-bootstrap responsibilities unless explicitly added to collection scope. Do not infer these capabilities from information-only module requirements.

## 4. Client workflows and evidence

The following public reports are primary evidence of actual usage patterns. They are examples, not a profile of a confirmed target customer.

| Observed usage | Evidence | Required development scenario |
|---|---|---|
| Multiple template clones run concurrently; a failed operation continues waiting until timeout. | [Community issue #540](https://github.com/ansible-collections/community.proxmox/issues/540) | Concurrent provisioning, task failure detection, resource locks, and prompt failure reporting. |
| Repeated cloud-init reconciliation produces false changes due to encoding and comparison behavior. | [Community issue #200](https://github.com/ansible-collections/community.proxmox/issues/200) | Repeated runs, SSH-key normalization, IP configuration, defaults, and removal of settings. |
| Inventory is queried while nodes undergo maintenance or become unreachable. | [Community issue #463](https://github.com/ansible-collections/community.proxmox/issues/463) | Multi-node discovery with an unavailable node and an explicit partial-result/error contract. |
| GUI changes and automation both modify firewall rules. | [Community issue #501](https://github.com/ansible-collections/community.proxmox/issues/501) | Out-of-band edits, reordered rules, stable identity, and drift reconciliation. |
| Hardened deployments rotate bootstrap passwords and rely on SSH trust. | [Community issue #503](https://github.com/ansible-collections/community.proxmox/issues/503) | Separate bootstrap and steady-state credentials; verify transport and endpoint authentication limitations. |

### First complete customer journey

1. Prepare or select a guest image/template and its target storage/network.
2. Create or clone a VM with a stable identity.
3. Configure networking, cloud-init, and guest-agent support.
4. Boot the guest and obtain its reachable address.
5. Connect from the automation execution environment and verify the guest's intended configuration.
6. Rerun the desired configuration without unnecessary changes.
7. Back up the workload.
8. Restore under another VMID and verify data, boot, and connectivity.
9. Remove test resources and verify cleanup.

Subsequent journeys should cover maintenance migration, manual drift, concurrent requests, node failures, container lifecycle, retention/verification, and PDM cross-cluster operations.

### Customer discovery still required

Confirm these points before calling the lab a customer replica:

- Target PVE/PBS/PDM versions and upgrade plans.
- Node count, cluster count, sites, and expected inventory size.
- Storage backends, snapshot support, shared/local storage, and replication requirements.
- Bridges, VLANs, overlay networking, MTU, routing, DNS, and IPAM.
- Authentication realms, token policies, permission boundaries, CA trust, and SSH restrictions.
- Guest operating systems, firmware/machine types, templates, guest agents, and cloud-init usage.
- AAP/CLI execution model, execution-environment image, proxies, and network reachability.
- Backup ownership, namespaces, retention, recovery objectives, off-site synchronization, and tape usage.
- Existing playbooks, manual GUI operations, representative failures, and required coexistence with other tools.

No target-customer topology or hardware capacity was supplied during this analysis. The lab below is a proposed reference environment.

## 5. Development environment

### Environment layers

| Layer | Proposed setup | Validation purpose |
|---|---|---|
| Initial PR reproduction | Linux runner/EE with Python 3.12; one reachable PVE node; trusted CA; automation credentials; `local-lvm`; `vmbr0`; reserved VMIDs. | Reproduce PR #1 and establish repeatable tests. |
| Core customer workflows | Three PVE nodes; local and shared storage; Linux cloud image with cloud-init/guest agent; LXC template; Windows guest scenario. | Booted workloads, connectivity, snapshots, cloning, migration, maintenance, and HA. |
| Protection | PBS with dedicated datastore storage; second PBS for remote synchronization. | Backup/restore, retention, verification, ownership, namespaces, and off-site synchronization. |
| Fleet operations | PDM plus a second independent PVE remote; a second multi-node cluster when the chosen scenario requires one. | Cross-remote inventory, migration, network/storage mappings, and remote failures. |
| Specialized extensions | Ceph disks; DNS/IPAM and identity services; ACME test infrastructure; dedicated tape/passthrough hardware as required. | Capabilities that ordinary guest fixtures do not adequately validate. |

Three PVE nodes provide the recommended basis for reliable HA quorum. Model cluster, storage/migration, management, and guest traffic separately in the lab. Virtual network separation does not establish physical fault isolation. See [vendor cluster requirements](https://github.com/proxmox/pve-docs/blob/master/pvecm.adoc).

A nested lab can support development scenarios when the required virtualization capabilities are exposed. Hardware-sensitive features and production fault/performance claims require appropriate dedicated validation.

### Connection and execution matrix

| Product | HTTPS port | Identity considerations | Transport baseline |
|---|---:|---|---|
| PVE | 8006 | PVE users, realms, roles, ACLs, and tokens. | HTTPS; OpenSSH where supported and authorized. |
| PBS | 8007 | Separate PBS identity and role model; token permissions are constrained by the owning user. | HTTPS. Do not infer OpenSSH support from PVE support. |
| PDM | 8443 | Separate PDM identity, ACLs, remote credentials, and trust relationships. | HTTPS after the collection/library support decision. |

Install dependencies where modules execute. The PR declares `proxmoxer>=2.3.0`, `requests`, and `openssh_wrapper`; OpenSSH use also requires an SSH client executable. Reproduce CA bundles, mounted SSH identities/configuration, DNS, proxies, and network paths inside the execution environment. Installing the collection alone does not install these dependencies. See the [PR README](https://github.com/shahargolshani/ansible.proxmox/blob/38ef0e19a1e45315edf87164b42da11d860f19f5/README.md).

Test HTTPS token authentication, the supported password path, and PVE OpenSSH independently. Human MFA enrollment and automated token access need separate scenarios.

### Exact initial PR fixtures

The inspected integration defaults use:

| Fixture | Value |
|---|---|
| PVE node | `pve01` |
| Storage | `local-lvm` |
| Bridge | `vmbr0` |
| Test VMIDs | `999` and `1000` |
| VLAN tags | `105` and `106` |
| Explicit QEMU machine type | `pc-i440fx-10.0` |
| CPU configurations | Include `x86-64-v3` and `x86-64-v4` |

The tests remove and recreate their reserved VMIDs. Keep them isolated from unrelated workloads. The `10.0` value is a QEMU machine version, not a PVE product version. These fixtures must be checked against the selected PVE/QEMU versions and the CPU capabilities required when guests are actually booted.

The current target verifies configuration, idempotency, and check-mode behavior. It does not establish booted guest operating systems, VLAN connectivity, migration, PBS, HA, or PDM behavior. See the [integration defaults](https://github.com/shahargolshani/ansible.proxmox/blob/38ef0e19a1e45315edf87164b42da11d860f19f5/tests/integration/targets/proxmox_vm/defaults/main.yml) and [integration tasks](https://github.com/shahargolshani/ansible.proxmox/blob/38ef0e19a1e45315edf87164b42da11d860f19f5/tests/integration/targets/proxmox_vm/tasks/main.yml).

### PBS integration sequence

Configure PBS as a separate service, with its own credentials and permissions. Create the datastore and namespace first, then register PBS as PVE storage, then exercise backup and restore. Use a second PBS for real remote synchronization tests. See [PVE/PBS integration](https://pbs.proxmox.com/docs/pve-integration.html), [PBS access control](https://pbs.proxmox.com/docs/user-management.html), and [PBS remotes and synchronization](https://pbs.proxmox.com/docs/managing-remotes.html).

## 6. API feasibility and compatibility decisions

### Initial VM pair

PR #1 implements VM list/configuration reads, creation, configuration updates, deletion, and task waiting. It deliberately limits disks to creation-time behavior and requires a stopped VM for configuration changes and deletion. The first customer workflow must respect those boundaries until dedicated disk, power, and pending-change capabilities are delivered.

The current VM helpers enforce broad Administrator privileges, including at `/` for VM management. Reproduce this requirement initially, then explicitly decide whether to retain it or implement operation-specific permissions. Restricted-token support cannot be assumed from token authentication support.

### HA compatibility

HA groups are deprecated in favor of node-affinity rules since PVE 9.0. ACA-5552's group-focused scope needs a supported-version and API decision before implementation. Do not advertise current-version HA coverage solely through legacy group operations. See [vendor HA documentation](https://github.com/proxmox/pve-docs/blob/master/ha-manager.adoc).

### PDM prerequisites and API gaps

The current PR accepts `PVE` and `PBS` as service choices. Its declared minimum `proxmoxer` version, 2.3.0, does not include PDM in its service map. A supported library version or an explicit connection implementation is therefore a prerequisite. The presence of PDM in newer upstream source does not establish a released dependency contract. See [Proxmoxer 2.3.0](https://github.com/proxmoxer/proxmoxer/blob/2.3.0/proxmoxer/core.py).

The inspected [PDM API schema](https://pdm.proxmox.com/docs/api-viewer/index.html) establishes these operations:

| Capability | Verified API operation | Planning implication |
|---|---|---|
| Remote registration | `GET`/`POST /remotes/remote`; resource `GET`/`PUT`/`DELETE` routes under `/remotes/remote/{id}`. | Base remote lifecycle is feasible; validate credential and certificate handling against the selected version. |
| Cross-remote inventory | `GET /resources/list`. | Use the actual returned resource types and filtering contract. |
| Cross-cluster VM migration | `POST /pve/remotes/{remote}/qemu/{vmid}/remote-migrate`. | Requires source/target remotes, bridge/storage mappings, and remote-task handling. |
| Cross-remote SDN | `GET`/`POST /sdn/zones` and `/sdn/vnets`. | The inspected routes establish list/create behavior; the promised full CRUD lifecycle remains unproven. |
| Remote APT updates | `GET`/`POST /pve/remotes/{remote}/nodes/{node}/apt/update`. | The POST refreshes the APT database. It does not establish package installation/patch application. |

PDM task aggregation, cached inventory, and remote UPIDs need explicit contracts; do not assume every PVE/PBS helper can be reused unchanged. PDM certificate rotation can also invalidate pinned remote fingerprints. See [PDM remotes](https://pdm.proxmox.com/docs/remotes.html).

Prepared installation answers use a dedicated installer-token mechanism separate from ordinary API tokens. This belongs in the PDM automated-installation scope and test design. See [PDM automated installations](https://pdm.proxmox.com/docs/automated-installations.html).

### Remaining module families

The epic inventory establishes desired scope, not a completed endpoint-by-endpoint API audit. Before implementing each resource, record its exact read/list, create, update, delete, action, permissions, and task routes for the selected product version. Mark unsupported or inconclusive operations explicitly.

Pair action modules with an appropriate information module or a documented shared discovery path. Adding an `_info` companion beyond Jira scope requires a scope decision; do not silently treat a complete action/info pair as already planned everywhere.

PBS S3 and other deferred features should remain governed by the explicit Jira scope until their support status and product versions are revalidated.

## 7. Validation and delivery gates

### Resource modules

For each delivered resource, verify applicable behavior:

- Create, inspect, update, delete, and repeated deletion.
- A second unchanged run returns `changed: false`.
- Check mode predicts changes without mutating the server.
- Omitted values, explicit defaults, empty values, and deletion semantics are handled consistently.
- API string/number/boolean encodings do not produce false differences.
- Out-of-band edits converge according to the documented ownership model.
- Missing resources, permission failures, timeouts, and partial failures produce useful results.
- Cleanup executes after both successful and failed tests.

### Action modules

Define repeat-run behavior per operation. Reboot, forced renewal, manual GC, rollback, and similar actions do not acquire meaningful idempotency simply by accepting `state: present`. Distinguish declarative state reconciliation from an explicit request to perform an action.

### Customer-level gates

| Gate | Evidence required |
|---|---|
| Foundation | Reproducible PR #1 tests; documented versions, credentials, EE, fixtures, and cleanup. |
| Workload provisioning | Booted guest, reachable address, guest configuration, repeated convergence, and cleanup. |
| Protection | Backup completion; successful restore under another identity; guest data and connectivity verification. |
| Maintenance/HA | Appropriate node/storage/network fixtures; migration or recovery verified after controlled failures. |
| Fleet | Two independent PVE remotes; PDM permissions/trust; verified cross-remote results and failure behavior. |
| Release | Supported-version matrix, required sanity/lint/unit/live integration checks, complete documentation, changelog, and completion of the actual certification process. |

CI checks labeled for certification do not themselves establish that the collection has completed certification or been published as supported content.

## 8. Immediate backlog and decisions

| Priority | Work item | Expected result |
|---|---|---|
| P0 | Reconcile Jira hierarchy, module names, PBS expansion, and PDM scope. | An authoritative delivery inventory and progress baseline. |
| P0 | Confirm target customer/deployment and representative playbooks. | Evidence-based workflows and acceptance criteria. |
| P0 | Select supported PVE/PBS versions and initial EE/toolchain matrix. | Reproducible compatibility contract. |
| P0 | Reproduce PR #1 in an isolated lab. | Verified initial fixtures and integration procedure. |
| P0 | Decide privilege expectations and bootstrap/steady-state credential separation. | Documented access model and permission tests. |
| P1 | Deliver VM power operations and selected cloud-init/guest-agent functionality. | A booted, reachable workload journey. |
| P1 | Move foundational tasks out of broad later epics. | Task polling/inspection, permission inspection, discovery, and apply semantics available when needed. |
| P1 | Add real backup/restore validation. | Demonstrated recovery of a working guest. |
| P1 | Resolve modern HA scope and PDM library/API gaps. | Feasible requirements before those workstreams expand. |

Assign owners and calendar estimates after scope reconciliation, product-version selection, lab capacity, and staffing are confirmed. No duration or customer topology is assumed by this plan.

## 9. Boundaries of this analysis

- This document records the analysis snapshot; Jira, PR, and product states can change.
- The complete epic hierarchy was read through `jira-rh`; the parent description's embedded list was not used as the hierarchy source.
- CI results were inspected; no new live test run was launched during analysis.
- No customer environment was accessed or provisioned.
- Public reports inform reference scenarios; they do not replace discovery with the intended customer.
- No Jira issues, PRs, or repository code were modified as part of this plan.
