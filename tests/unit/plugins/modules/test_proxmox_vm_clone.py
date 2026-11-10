# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask
from ansible_collections.ansible.proxmox.plugins.modules import proxmox_vm_clone
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_vm_clone import ProxmoxVmCloneModule


def make_clone_module(params=None):
    """Create a clone handler with isolated module and API dependencies.

    Args:
        params: Optional module parameters to override the defaults.

    Returns:
        The handler with fake module, client, and clone endpoint.
    """
    module_params = {
        "node": "pve01",
        "vmid": 100,
        "newid": 101,
        "task_timeout": None,
        "description": None,
        "format": None,
        "full": None,
        "name": None,
        "pool": None,
        "snapname": None,
        "storage": None,
        "target": None,
    }
    module_params.update(params or {})
    module = SimpleNamespace(
        params=module_params,
        check_mode=False,
        fail_json=Mock(side_effect=RuntimeError("module failed")),
        exit_json=Mock(side_effect=SystemExit),
    )
    client = SimpleNamespace(
        api=Mock(),
        validate_pve_permissions=Mock(),
        mark_changed=Mock(),
    )
    resource = SimpleNamespace(
        clone=SimpleNamespace(post=Mock()),
        feature=SimpleNamespace(get=Mock()),
    )
    handler = ProxmoxVmCloneModule(module, client=client)
    handler.call_api = Mock(return_value=[])
    handler.vm_resource = Mock(return_value=resource)
    return handler


def test_clone_action_is_always_needed():
    """Treat each invocation as a new, non-idempotent clone request."""
    handler = make_clone_module()

    assert handler.is_action_needed() is True
    assert handler.is_action_needed() is True

    handler.client.validate_pve_permissions.assert_called_with(handler.api, "/vms")
    assert handler.client.validate_pve_permissions.call_count == 2


@pytest.mark.parametrize("check_mode", [False, True])
def test_clone_check_mode_delegates_validation_in_order(check_mode):
    """Preserve validation ordering and keep API preflight out of normal mode.

    Args:
        check_mode: Whether read-only clone preconditions should be checked.
    """
    handler = make_clone_module()
    handler.module.check_mode = check_mode
    source = {"vmid": 100, "template": 1}
    validators = Mock()
    validators.source.return_value = source
    handler._validate_clone_options = validators.options
    handler._validate_destination_vmid = validators.destination
    handler._validate_source_vm = validators.source
    handler._validate_target_storage = validators.storage
    handler._validate_linked_clone_support = validators.linked_clone

    handler._validate_check_mode()

    expected_calls = [call.options()]
    expected_calls.append(call.destination())
    if check_mode:
        expected_calls.extend(
            [call.source(), call.storage(), call.linked_clone(source)]
        )
    assert validators.mock_calls == expected_calls
    handler.call_api.assert_not_called()


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("vmid", 99),
        ("vmid", 1000000000),
        ("newid", 99),
        ("newid", 1000000000),
    ],
)
def test_clone_rejects_vmids_outside_supported_range(parameter, value):
    """Reject source or destination VMIDs outside the Proxmox range.

    Args:
        parameter: VMID argument to override.
        value: Invalid VMID value.
    """
    handler = make_clone_module({parameter: value})

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    assert parameter in handler.module.fail_json.call_args.kwargs["msg"]
    handler.client.validate_pve_permissions.assert_not_called()


def test_clone_rejects_same_source_and_destination_vmid():
    """Reject requests that would clone a VM onto its own ID."""
    handler = make_clone_module({"newid": 100})

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    assert "newid must be different from vmid" in handler.module.fail_json.call_args.kwargs["msg"]


@pytest.mark.parametrize("check_mode", [False, True])
def test_clone_rejects_format_with_full_false(check_mode):
    """Reject a disk format with explicit full=false in either mode.

    Args:
        check_mode: Whether to predict the clone instead of submitting it.
    """
    handler = make_clone_module({"full": False, "format": "qcow2"})
    handler.module.check_mode = check_mode

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(msg="format cannot be used with full=false.")
    handler.call_api.assert_not_called()
    handler.vm_resource.assert_not_called()


@pytest.mark.parametrize(
    ("full", "disk_format", "storage"),
    [
        (True, "qcow2", None),
        (None, "qcow2", None),
        (False, None, None),
        (False, None, "local-lvm"),
        (None, None, "local-lvm"),
    ],
)
def test_clone_check_mode_validates_vmids_and_linked_clone_options(full, disk_format, storage):
    """Check VMIDs and linked-clone support for valid option combinations.

    Args:
        full: Explicit or omitted full-clone setting.
        disk_format: Optional target disk format.
        storage: Optional target storage.
    """
    handler = make_clone_module({"full": full, "format": disk_format, "storage": storage})
    handler.module.check_mode = True
    responses = [[], [{"vmid": "100"}]]
    if full is False:
        responses.append({"hasFeature": 1})
    handler.call_api.side_effect = responses

    assert handler.is_action_needed() is True

    assert handler.call_api.call_count == len(responses)
    assert handler.call_api.call_args_list[1].args == (
        "Retrieving VMs from node pve01",
        handler.api.get,
        "nodes/pve01/qemu",
    )
    handler.module.fail_json.assert_not_called()
    handler.vm_resource.return_value.clone.post.assert_not_called()


@pytest.mark.parametrize(
    ("full", "template", "has_feature"),
    [(False, 0, 1), (False, 1, "1"), (None, 1, True), (None, "1", 1), (None, True, 1)],
)
@pytest.mark.parametrize("snapname", [None, "before-upgrade"])
def test_clone_check_mode_checks_linked_disk_support(full, template, has_feature, snapname):
    """Query Proxmox disk capabilities for explicit or default linked clones.

    Args:
        full: Explicit or omitted full-clone setting.
        template: Source template flag returned by Proxmox.
        has_feature: Supported boolean representation returned by Proxmox.
        snapname: Optional snapshot used as the clone source.
    """
    handler = make_clone_module({"full": full, "snapname": snapname})
    handler.module.check_mode = True
    handler.call_api.side_effect = [
        [],
        [{"vmid": 100, "template": template}],
        {"hasFeature": has_feature},
    ]

    assert handler.is_action_needed() is True

    options = {"feature": "clone"}
    if snapname is not None:
        options["snapname"] = snapname
    handler.call_api.assert_called_with(
        "Checking linked clone support for VM 100 on node pve01",
        handler.vm_resource.return_value.feature.get,
        **options
    )
    handler.vm_resource.return_value.clone.post.assert_not_called()
    handler.client.mark_changed.assert_not_called()


@pytest.mark.parametrize("full", [False, None])
@pytest.mark.parametrize("has_feature", [0, "0", False])
def test_clone_check_mode_rejects_unsupported_linked_disks(full, has_feature):
    """Notify users when the source disks cannot be linked-cloned.

    Args:
        full: Explicit or default linked-clone request for a template.
        has_feature: Unsupported boolean representation returned by Proxmox.
    """
    handler = make_clone_module({"full": full})
    handler.module.check_mode = True
    handler.call_api.side_effect = [
        [],
        [{"vmid": 100, "template": 1}],
        {"hasFeature": has_feature},
    ]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(
        msg=(
            "Linked clone feature is not supported for one or more disks of VM 100 on node pve01. "
            "Use full=true to create a full clone."
        )
    )
    handler.vm_resource.return_value.clone.post.assert_not_called()
    handler.client.mark_changed.assert_not_called()


@pytest.mark.parametrize("features", [None, [], {}, {"hasFeature": None}, {"hasFeature": "unknown"}])
def test_clone_check_mode_rejects_unknown_linked_disk_support(features):
    """Avoid predicting a successful linked clone when disk support is unknown.

    Args:
        features: Malformed or incomplete feature endpoint response.
    """
    handler = make_clone_module({"full": False})
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], [{"vmid": 100}], features]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(
        msg="Unable to determine linked clone support for VM 100 on node pve01."
    )
    handler.vm_resource.return_value.clone.post.assert_not_called()


@pytest.mark.parametrize(("full", "template"), [(True, 0), (True, 1), (None, 0)])
def test_clone_check_mode_skips_linked_disk_checks_for_full_clones(full, template):
    """Do not require linked-clone support for explicit or default full clones.

    Args:
        full: Explicit or omitted full-clone setting.
        template: Source template flag returned by Proxmox.
    """
    handler = make_clone_module({"full": full})
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], [{"vmid": 100, "template": template}]]

    assert handler.is_action_needed() is True

    assert handler.call_api.call_count == 2
    handler.vm_resource.assert_not_called()


@pytest.mark.parametrize("full", [True, None])
@pytest.mark.parametrize("storage_config", [{}, {"shared": 0}, {"shared": "0"}, {"shared": False}])
def test_clone_check_mode_rejects_non_shared_target_storage(full, storage_config):
    """Reject cross-node clones to storage that is not configured as shared.

    Args:
        full: Explicit or default full-clone setting for a regular VM.
        storage_config: Destination storage configuration without shared support.
    """
    handler = make_clone_module({"full": full, "storage": "local-lvm", "target": "pve02"})
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], [{"vmid": 100}], storage_config]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(msg="can't clone to non-shared storage 'local-lvm'")
    handler.call_api.assert_called_with(
        "Retrieving configuration for storage local-lvm",
        handler.api.storage.return_value.get,
    )
    handler.api.storage.assert_called_once_with("local-lvm")
    handler.vm_resource.assert_not_called()
    handler.client.mark_changed.assert_not_called()


@pytest.mark.parametrize("shared", [1, "1", True])
def test_clone_check_mode_accepts_shared_target_storage(shared):
    """Allow a cross-node full clone when the destination storage is shared.

    Args:
        shared: Shared storage flag returned by Proxmox.
    """
    handler = make_clone_module({"full": True, "storage": "shared-vms", "target": "pve02"})
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], [{"vmid": 100}], {"shared": shared}]

    assert handler.is_action_needed() is True

    handler.api.storage.assert_called_once_with("shared-vms")
    assert handler.call_api.call_count == 3
    handler.module.fail_json.assert_not_called()
    handler.vm_resource.assert_not_called()
    handler.client.mark_changed.assert_not_called()


@pytest.mark.parametrize(
    ("check_mode", "target", "storage"),
    [
        (True, None, "local-lvm"),
        (True, "pve01", "local-lvm"),
        (True, "localhost", "local-lvm"),
        (True, "pve02", None),
        (False, "pve02", "local-lvm"),
    ],
)
def test_clone_skips_shared_storage_checks_when_not_required(check_mode, target, storage):
    """Check only destination VMID in normal mode and skip irrelevant storage reads.

    Args:
        check_mode: Whether the clone is only being predicted.
        target: Optional destination node.
        storage: Optional destination storage.
    """
    handler = make_clone_module({"full": True, "target": target, "storage": storage})
    handler.module.check_mode = check_mode
    handler.call_api.side_effect = [[], [{"vmid": 100}]]

    assert handler.is_action_needed() is True

    assert handler.call_api.call_count == (2 if check_mode else 1)
    handler.api.storage.assert_not_called()
    handler.module.fail_json.assert_not_called()


@pytest.mark.parametrize("storage_config", [None, []])
def test_clone_check_mode_rejects_unknown_shared_storage_support(storage_config):
    """Fail safely if destination storage configuration cannot be verified.

    Args:
        storage_config: Invalid destination storage configuration response.
    """
    handler = make_clone_module({"full": True, "storage": "local-lvm", "target": "pve02"})
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], [{"vmid": 100}], storage_config]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(
        msg="Unable to determine whether storage 'local-lvm' is shared."
    )
    handler.vm_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_clone_rejects_destination_vmid_in_use(check_mode):
    """Reject an occupied destination VMID in both normal and check mode.

    Args:
        check_mode (bool): Whether the clone is only being predicted.
    """
    handler = make_clone_module()
    handler.module.check_mode = check_mode
    handler.call_api.return_value = [{"vmid": "101"}]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(msg="VMID 101 is already in use.")
    assert handler.call_api.call_count == 1
    handler.vm_resource.return_value.clone.post.assert_not_called()
    handler.client.mark_changed.assert_not_called()


@pytest.mark.parametrize("source_vms", [None, [], [{"vmid": 102}]])
def test_clone_check_mode_rejects_missing_source_vmid(source_vms):
    """Reject a predicted clone when the source VMID is absent from the node.

    Args:
        source_vms: Node QEMU resources without the requested source VMID.
    """
    handler = make_clone_module()
    handler.module.check_mode = True
    handler.call_api.side_effect = [[], source_vms]

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    handler.module.fail_json.assert_called_once_with(msg="QEMU VM 100 is not available on node pve01.")


def test_clone_posts_only_required_options_and_waits(monkeypatch):
    """Submit a default clone request, mark the mutation, and wait for its task.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
    """
    handler = make_clone_module()
    handler.call_api.return_value = "UPID:pve01:clone"
    wait_for_task = Mock()
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", wait_for_task)

    assert handler.perform_action() == {"vmid": 101}

    handler.call_api.assert_called_once_with(
        "Cloning VM 100 on node pve01 as VM 101",
        handler.vm_resource.return_value.clone.post,
        newid=101,
    )
    handler.client.mark_changed.assert_called_once_with()
    wait_for_task.assert_called_once_with("UPID:pve01:clone")


def test_clone_forwards_all_supplied_options(monkeypatch):
    """Forward every supported optional parameter to the clone endpoint.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
    """
    options = {
        "description": "Clone for staging",
        "format": "qcow2",
        "full": 1,
        "name": "staging-copy",
        "pool": "staging",
        "snapname": "before-upgrade",
        "storage": "local-lvm",
        "target": "pve02",
    }
    handler = make_clone_module(options)
    handler.call_api.return_value = "UPID:pve01:clone"
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", Mock())

    assert handler.perform_action() == {"vmid": 101}

    handler.call_api.assert_called_once_with(
        "Cloning VM 100 on node pve01 as VM 101",
        handler.vm_resource.return_value.clone.post,
        newid=101,
        **options
    )


@pytest.mark.parametrize(("full", "expected"), [(True, 1), (False, 0)])
def test_clone_encodes_full_as_pve_boolean(monkeypatch, full, expected):
    """Encode the full-clone boolean as Proxmox's numeric boolean value.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
        full: Requested full-clone setting.
        expected: Integer value sent to the Proxmox API.
    """
    handler = make_clone_module({"full": full})
    handler.call_api.return_value = "UPID:pve01:clone"
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", Mock())

    handler.perform_action()

    assert handler.call_api.call_args.kwargs["full"] == expected


@pytest.mark.parametrize("task_upid", [None, "not-a-task"])
def test_clone_rejects_response_without_task_upid(monkeypatch, task_upid):
    """Fail if Proxmox does not return the asynchronous clone task ID.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
        task_upid: Invalid clone endpoint response.
    """
    handler = make_clone_module()
    handler.call_api.return_value = task_upid
    wait_for_task = Mock()
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", wait_for_task)

    with pytest.raises(RuntimeError, match="module failed"):
        handler.perform_action()

    assert "did not return a task UPID" in handler.module.fail_json.call_args.kwargs["msg"]
    wait_for_task.assert_not_called()


def test_clone_result_includes_task_upid_only_after_clone():
    """Return the destination VMID in check mode and a task UPID after cloning."""
    handler = make_clone_module()

    assert handler.get_action_result() == {"vmid": 101}
    assert handler.prepare_result(changed=True, resource=handler.get_action_result()) == {
        "changed": True,
        "clone": {"vmid": 101},
    }

    handler._task_upid = "UPID:pve01:clone"
    assert handler.prepare_result(changed=True, resource=handler.get_action_result()) == {
        "changed": True,
        "clone": {"vmid": 101},
        "task_upid": "UPID:pve01:clone",
    }


def test_clone_main_registers_arguments_and_executes_handler(monkeypatch):
    """Register the clone argument spec and delegate to the action lifecycle.

    Args:
        monkeypatch: Pytest fixture for replacing Ansible module construction.
    """
    module = SimpleNamespace()
    constructor = Mock(return_value=module)
    handler = Mock()
    handler_constructor = Mock(return_value=handler)
    monkeypatch.setattr(proxmox_vm_clone, "AnsibleModule", constructor)
    monkeypatch.setattr(proxmox_vm_clone, "ProxmoxVmCloneModule", handler_constructor)

    proxmox_vm_clone.main()

    arguments = constructor.call_args.kwargs
    spec = arguments["argument_spec"]
    assert arguments["supports_check_mode"] is True
    assert spec["node"] == {"type": "str", "required": True}
    assert spec["vmid"] == {"type": "int", "required": True}
    assert spec["newid"] == {"type": "int", "required": True}
    assert spec["format"]["choices"] == ["raw", "qcow2", "vmdk"]
    assert spec["full"] == {"type": "bool"}
    assert spec["task_timeout"] == {"type": "int"}
    handler_constructor.assert_called_once_with(module)
    handler.execute_action_module.assert_called_once_with()
