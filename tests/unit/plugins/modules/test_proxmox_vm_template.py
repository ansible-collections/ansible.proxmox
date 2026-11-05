# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask
from ansible_collections.ansible.proxmox.plugins.modules import proxmox_vm_template
from ansible_collections.ansible.proxmox.plugins.modules import proxmox_vm_template_info
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_vm_template import ProxmoxVmTemplateModule
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_vm_template_info import ProxmoxVmTemplateInfoModule


def make_template_module(params=None):
    """Create a template handler with isolated module and API dependencies.

    Args:
        params: Optional module parameters to override the defaults.

    Returns:
        The template handler with its fake module, client, and API resource.
    """
    module_params = {"vmid": 100, "disk": None, "power_cycle": "fail"}
    module_params.update(params or {})
    module = SimpleNamespace(
        params=module_params,
        check_mode=False,
        fail_json=Mock(side_effect=RuntimeError("module failed")),
    )
    client = SimpleNamespace(api=Mock(), validate_pve_permissions=Mock())
    resource = SimpleNamespace(
        config=SimpleNamespace(get=Mock()),
        template=SimpleNamespace(post=Mock()),
    )
    handler = ProxmoxVmTemplateModule(module, client=client)
    handler.call_api = Mock()
    handler.get_status = Mock()
    handler.node = Mock(return_value="pve01")
    handler.set_state = Mock(return_value=("UPID:pve01:stop", "stopped"))
    handler.vm_resource = Mock(return_value=resource)
    handler._needs_stop = False
    return handler


def make_template_info_module(params=None):
    """Create a template-info handler with mocked API boundaries.

    Args:
        params: Optional module parameters to override the defaults.

    Returns:
        The info handler with fake module and client dependencies.
    """
    module_params = {"node": "pve01", "vmid": None}
    module_params.update(params or {})
    module = SimpleNamespace(
        params=module_params,
        check_mode=False,
        fail_json=Mock(side_effect=RuntimeError("module failed")),
    )
    client = SimpleNamespace(api=Mock(), validate_pve_permissions=Mock())
    handler = ProxmoxVmTemplateInfoModule(module, client=client)
    handler.call_api = Mock()
    handler.validate_proxmox_resource_exist = Mock()
    return handler


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"template": 1}, True),
        ({"template": "1"}, True),
        ({"template": True}, True),
        ({"template": 0}, False),
        ({"status": "stopped"}, False),
        (None, False),
    ],
)
def test_template_status_recognizes_supported_values(status, expected):
    """Recognize Proxmox template flags and reject other status values.

    Args:
        status: Status response to inspect.
        expected: Whether the response should be recognized as a template.
    """
    assert ProxmoxVmTemplateModule._is_template_status(status) is expected


def test_existing_template_needs_no_action():
    """Leave an already converted VM unchanged after checking permissions."""
    handler = make_template_module()
    handler.get_status.return_value = {"template": 1, "status": "stopped"}

    assert handler.is_action_needed() is False

    handler.client.validate_pve_permissions.assert_called_once_with(handler.api, "/vms")


@pytest.mark.parametrize(
    "status",
    [None, {"status": "paused"}],
)
def test_action_rejects_unknown_vm_status(status):
    """Fail closed when the API cannot establish the VM power state.

    Args:
        status: Invalid or missing status response.
    """
    handler = make_template_module()
    handler.get_status.return_value = status

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    assert handler.module.fail_json.call_count == 1


def test_action_requires_power_cycle_policy_for_running_vm():
    """Reject conversion of a running VM under the default fail policy."""
    handler = make_template_module()
    handler.get_status.return_value = {"status": "running"}

    with pytest.raises(RuntimeError, match="module failed"):
        handler.is_action_needed()

    assert "power_cycle=off" in handler.module.fail_json.call_args.kwargs["msg"]


@pytest.mark.parametrize(
    ("status", "expected_stop"),
    [
        ({"status": "stopped"}, False),
        ({"status": "running"}, True),
        ({"status": "stopped", "lock": "suspended"}, True),
    ],
)
def test_action_records_whether_vm_must_be_stopped(status, expected_stop):
    """Accept convertible VM states and record required power transitions.

    Args:
        status: Initial VM status returned by the API.
        expected_stop: Whether conversion requires stopping the VM first.
    """
    handler = make_template_module({"power_cycle": "off"})
    handler.get_status.return_value = status

    assert handler.is_action_needed() is True

    assert handler._needs_stop is expected_stop


def test_disk_validation_accepts_configured_disk():
    """Allow a valid disk selector that names a configured VM disk."""
    handler = make_template_module({"disk": "scsi0"})
    handler.call_api.return_value = {"scsi0": "local-lvm:vm-100-disk-0,size=32G"}

    handler._validate_template_disk()

    handler.call_api.assert_called_once_with(
        "Retrieving VM 100 configuration for template conversion",
        handler.vm_resource.return_value.config.get,
    )


@pytest.mark.parametrize(
    ("disk", "config"),
    [
        ("invalid", {"invalid": "local-lvm:disk,size=1G"}),
        ("scsi0", {}),
        ("scsi0", {"scsi0": ""}),
        ("scsi0", {"scsi0": 1}),
        ("ide2", {"ide2": "local:iso/image.iso,media=cdrom"}),
    ],
)
def test_disk_validation_rejects_unconfigured_or_non_disk_devices(disk, config):
    """Reject malformed selectors, missing disks, and CD-ROM devices.

    Args:
        disk: Requested disk selector.
        config: VM configuration returned by the API.
    """
    handler = make_template_module({"disk": disk})
    handler.call_api.return_value = config

    with pytest.raises(RuntimeError, match="module failed"):
        handler._validate_template_disk()

    assert disk in handler.module.fail_json.call_args.kwargs["msg"]


@pytest.mark.parametrize("disk", [None, "scsi0"])
def test_perform_action_waits_and_verifies_template_conversion(monkeypatch, disk):
    """Submit conversion, wait for its task, and verify the resulting state.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
        disk: Optional disk selector passed to the conversion endpoint.
    """
    handler = make_template_module({"disk": disk})
    handler.call_api.return_value = "UPID:pve01:template"
    handler.get_status.return_value = {"template": 1}
    wait_for_task = Mock()
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", wait_for_task)

    assert handler.perform_action() is True

    expected_options = {"disk": disk} if disk is not None else {}
    handler.call_api.assert_called_once_with(
        "Converting VM 100 on node pve01 to a template",
        handler.vm_resource.return_value.template.post,
        **expected_options
    )
    wait_for_task.assert_called_once_with("UPID:pve01:template")
    handler.get_status.assert_called_once_with()


@pytest.mark.parametrize(
    ("status", "expected_actions"),
    [
        ({"status": "running"}, ["stop"]),
        ({"status": "stopped", "lock": "suspended"}, ["resume", "stop"]),
    ],
)
def test_perform_action_stops_or_resumes_vm_before_conversion(monkeypatch, status, expected_actions):
    """Stop a running VM and resume a suspended VM before stopping it.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
        status: Initial VM status requiring a power transition.
        expected_actions: Ordered power actions to issue before conversion.
    """
    handler = make_template_module({"power_cycle": "off"})
    handler._current_status = status
    handler._needs_stop = True
    handler.call_api.return_value = "UPID:pve01:template"
    handler.get_status.return_value = {"template": 1}
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", Mock())

    assert handler.perform_action() is True

    assert [call.args[0] for call in handler.set_state.call_args_list] == expected_actions


@pytest.mark.parametrize("upid", [None, "not-a-task"])
def test_perform_action_rejects_invalid_task_identifier(monkeypatch, upid):
    """Fail when the conversion endpoint does not return a UPID.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
        upid: Invalid endpoint response to validate.
    """
    handler = make_template_module()
    handler.call_api.return_value = upid
    wait_for_task = Mock()
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", wait_for_task)

    with pytest.raises(RuntimeError, match="module failed"):
        handler.perform_action()

    assert "did not return a task UPID" in handler.module.fail_json.call_args.kwargs["msg"]
    wait_for_task.assert_not_called()


def test_perform_action_fails_if_conversion_does_not_reach_template(monkeypatch):
    """Fail after task completion if the VM is not reported as a template.

    Args:
        monkeypatch: Pytest fixture for replacing task waiting.
    """
    handler = make_template_module()
    handler.call_api.return_value = "UPID:pve01:template"
    handler.get_status.return_value = {"template": 0}
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", Mock())

    with pytest.raises(RuntimeError, match="module failed"):
        handler.perform_action()

    assert "did not reach the template state" in handler.module.fail_json.call_args.kwargs["msg"]


def test_action_result_and_task_result_shaping():
    """Return the template state and include a task UPID only when available."""
    handler = make_template_module()

    assert handler.get_action_result() is True
    assert handler.prepare_result(changed=False, resource=True) == {
        "changed": False,
        "template": True,
    }

    handler._task_upid = "UPID:pve01:template"
    assert handler.prepare_result(changed=True, resource=True) == {
        "changed": True,
        "template": True,
        "task_upid": "UPID:pve01:template",
    }


def test_main_registers_template_arguments_and_executes_handler(monkeypatch):
    """Register the argument specification and delegate to the action handler.

    Args:
        monkeypatch: Pytest fixture for replacing Ansible module construction.
    """
    module = SimpleNamespace()
    constructor = Mock(return_value=module)
    handler = Mock()
    handler_constructor = Mock(return_value=handler)
    monkeypatch.setattr(proxmox_vm_template, "AnsibleModule", constructor)
    monkeypatch.setattr(proxmox_vm_template, "ProxmoxVmTemplateModule", handler_constructor)

    proxmox_vm_template.main()

    arguments = constructor.call_args.kwargs
    assert arguments["supports_check_mode"] is True
    assert arguments["argument_spec"]["vmid"] == {"type": "int", "required": True}
    assert arguments["argument_spec"]["disk"] == {"type": "str"}
    assert arguments["argument_spec"]["power_cycle"] == {
        "type": "str",
        "choices": ["fail", "off"],
        "default": "fail",
    }
    assert arguments["argument_spec"]["task_timeout"] == {"type": "int"}
    handler_constructor.assert_called_once_with(module)
    handler.execute_action_module.assert_called_once_with()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"template": 1}, True),
        ({"template": "1"}, True),
        ({"template": True}, True),
        ({"template": 0}, False),
        ({"status": "stopped"}, False),
        (None, False),
    ],
)
def test_template_info_status_recognizes_supported_values(status, expected):
    """Recognize template flags in QEMU status responses.

    Args:
        status: Status response to inspect.
        expected: Whether the response should be recognized as a template.
    """
    assert ProxmoxVmTemplateInfoModule._is_template_status(status) is expected


def test_template_info_lists_templates_from_vm_records_without_extra_status_calls():
    """Filter templates from VM-list records without per-VM status requests."""
    handler = make_template_info_module()
    resources = [
        {"vmid": 100, "template": 1, "status": "stopped"},
        {"vmid": "101", "template": "1", "status": "stopped"},
        {"vmid": 102, "template": 0, "status": "stopped"},
        {"vmid": 103, "status": "stopped"},
        {"vmid": None, "template": 1},
        {"name": "missing-vmid", "template": 1},
        "invalid-resource",
        None,
    ]
    handler.call_api.return_value = resources

    result = handler.get_info()

    assert result == [
        {"template": 1, "status": "stopped", "vmid": 100},
        {"vmid": "101", "template": "1", "status": "stopped"},
    ]
    assert result[0] is not resources[0]
    assert resources[0] == {"vmid": 100, "template": 1, "status": "stopped"}

    handler.client.validate_pve_permissions.assert_called_once_with(handler.api, "/vms")
    handler.validate_proxmox_resource_exist.assert_called_once_with(
        "node",
        "pve01",
        handler.api.nodes.get,
        resource_key="node",
    )
    handler.call_api.assert_called_once_with(
        "Retrieving VMs from node pve01",
        handler.api.get,
        "nodes/pve01/qemu",
    )


def test_template_info_selects_requested_vmid_by_string_value():
    """Match an integer VMID against a string VMID in the node inventory."""
    handler = make_template_info_module({"vmid": 101})
    handler.call_api.return_value = [
        {"vmid": "101", "template": 1, "status": "stopped"},
        {"vmid": 100, "template": 0, "status": "stopped"},
    ]

    assert handler.get_info() == [{"vmid": "101", "template": 1, "status": "stopped"}]

    handler.call_api.assert_called_once_with(
        "Retrieving VMs from node pve01",
        handler.api.get,
        "nodes/pve01/qemu",
    )


def test_template_info_returns_empty_when_requested_vmid_is_not_on_node():
    """Skip status lookups when the requested VMID is absent from the node."""
    handler = make_template_info_module({"vmid": 107})
    handler.call_api.return_value = [{"vmid": 100}]

    assert handler.get_info() == []

    handler.call_api.assert_called_once()


def test_template_info_returns_empty_for_missing_vm_inventory():
    """Handle an empty or missing QEMU inventory without status lookups."""
    handler = make_template_info_module()
    handler.call_api.return_value = None

    assert handler.get_info() == []

    handler.call_api.assert_called_once()


@pytest.mark.parametrize("vmid", [99, 1000000000])
def test_template_info_rejects_vmid_outside_supported_range(vmid):
    """Reject an out-of-range VMID before API or permission checks.

    Args:
        vmid: Invalid VMID value to validate.
    """
    handler = make_template_info_module({"vmid": vmid})

    with pytest.raises(RuntimeError, match="module failed"):
        handler.get_info()

    assert "VMID must be between 100 and 999999999" in handler.module.fail_json.call_args.kwargs["msg"]
    handler.client.validate_pve_permissions.assert_not_called()
    handler.call_api.assert_not_called()


def test_template_info_main_registers_arguments_and_executes_handler(monkeypatch):
    """Register info arguments and delegate to the read-only lifecycle.

    Args:
        monkeypatch: Pytest fixture for replacing Ansible module construction.
    """
    module = SimpleNamespace()
    constructor = Mock(return_value=module)
    handler = Mock()
    handler_constructor = Mock(return_value=handler)
    monkeypatch.setattr(proxmox_vm_template_info, "AnsibleModule", constructor)
    monkeypatch.setattr(proxmox_vm_template_info, "ProxmoxVmTemplateInfoModule", handler_constructor)

    proxmox_vm_template_info.main()

    arguments = constructor.call_args.kwargs
    assert arguments["supports_check_mode"] is True
    assert arguments["argument_spec"]["node"] == {"type": "str", "required": True}
    assert arguments["argument_spec"]["vmid"] == {"type": "int"}
    handler_constructor.assert_called_once_with(module)
    handler.execute_info_module.assert_called_once_with()
