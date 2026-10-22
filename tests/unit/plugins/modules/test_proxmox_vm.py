# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_resource import ProxmoxResourceModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask
from ansible_collections.ansible.proxmox.plugins.modules import proxmox_vm
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_vm import ProxmoxVmModule, VGA_CHOICES


class FakeApi:
    def __init__(self):
        self.create_parameters = None
        self.update_parameters = None
        self.storage_queries = 0
        self.task_upids = []
        self.task_status_pending = False
        self.storage_entries = [{"storage": "local-lvm", "active": 1, "enabled": 1, "content": "images"}]
        self.storage_get_calls = []
        self.machine_get_calls = []
        self.machine_entries = [
            {"id": "pc-q35-10.0", "type": "q35", "version": "10.0"},
            {"id": "pc-q35-10.0+pve1", "type": "q35", "version": "10.0+pve1"},
            {"id": "pc-i440fx-10.0+pve1", "type": "i440fx", "version": "10.0+pve1"},
        ]

    def nodes(self, node):
        return self

    @property
    def qemu(self):
        return self

    @property
    def config(self):
        return self

    @property
    def storage(self):
        return self

    def get(self, uri=None, **parameters):
        if self.task_status_pending:
            self.task_status_pending = False
            return {"status": "stopped", "exitstatus": "OK"}
        if uri is not None:
            self.machine_get_calls.append(uri)
            return self.machine_entries
        self.storage_queries += 1
        self.storage_get_calls.append(parameters)
        return self.storage_entries

    def __call__(self, vmid):
        return self

    def create(self, **parameters):
        self.create_parameters = parameters
        return "UPID:pve01:task"

    def post(self, **parameters):
        self.update_parameters = parameters
        return "UPID:pve01:task"

    def delete(self):
        return "UPID:pve01:delete"

    def tasks(self, upid):
        self.task_upids.append(upid)
        self.task_status_pending = True
        return self

    @property
    def status(self):
        return self


class FakeClient:
    def __init__(self, api):
        self.api = api


def module_params(**updates):
    params = {
        "node": "pve01",
        "vmid": 100,
        "name": None,
        "memory": None,
        "cores": None,
        "sockets": None,
        "cpu": None,
        "bios": None,
        "efidisk": None,
        "machine": None,
        "ostype": None,
        "vga": None,
        "scsihw": None,
        "ide2": None,
        "network": None,
        "disk": None,
    }
    params.update(updates)
    return params


def make_vm(params=None, api=None):
    vm = ProxmoxVmModule(
        SimpleNamespace(params=params or module_params()),
        client=FakeClient(api or FakeApi()),
    )
    vm._vm_status = "stopped"
    return vm


def test_disk_argument_and_examples_use_structured_disk_entries(monkeypatch):
    constructor = Mock(return_value=SimpleNamespace(params=module_params()))
    monkeypatch.setattr(proxmox_vm, "AnsibleModule", constructor)
    monkeypatch.setattr(ProxmoxVmModule, "execute_resource_module", Mock())

    proxmox_vm.main()

    spec = constructor.call_args.kwargs["argument_spec"]
    assert "required_if" not in constructor.call_args.kwargs
    documentation = yaml.safe_load(proxmox_vm.DOCUMENTATION)
    assert "scsi0" not in spec
    assert "scsi0" not in module_params()
    assert set(documentation["options"]).issubset(spec)
    assert documentation["options"]["machine"]["type"] == "dict"
    assert spec["machine"]["type"] == "dict"
    assert documentation["options"]["efidisk"]["type"] == "dict"
    assert spec["efidisk"]["type"] == "dict"
    assert set(documentation["options"]["machine"]["suboptions"]) == set(spec["machine"]["options"])
    assert spec["disk"]["type"] == "list"
    assert spec["disk"]["elements"] == "dict"
    assert set(spec["disk"]["options"]) == {"name", "storage", "size"}
    for task in yaml.safe_load(proxmox_vm.EXAMPLES):
        arguments = task["ansible.proxmox.proxmox_vm"]
        assert set(arguments).issubset(spec)
        for name, value in arguments.items():
            if "choices" in spec[name]:
                assert value in spec[name]["choices"]
        for disk in arguments.get("disk", []):
            assert set(disk) == {"name", "storage", "size"}


@pytest.mark.parametrize(
    ("state", "efidisk", "should_fail"),
    [("present", None, True), ("absent", None, False), ("absent", {}, False)],
)
def test_ovmf_requires_efidisk_only_when_present(monkeypatch, state, efidisk, should_fail):
    module = SimpleNamespace(
        params={"state": state, "bios": "ovmf", "efidisk": efidisk},
        fail_json=Mock(side_effect=RuntimeError("module failed")),
    )
    vm = ProxmoxVmModule(module, client=FakeClient(FakeApi()))
    execute = Mock()
    monkeypatch.setattr(ProxmoxResourceModule, "execute_resource_module", execute)

    if should_fail:
        with pytest.raises(RuntimeError, match="module failed"):
            vm.execute_resource_module()
        assert "efidisk" in module.fail_json.call_args.kwargs["msg"]
        execute.assert_not_called()
    else:
        vm.execute_resource_module()
        execute.assert_called_once_with()


@pytest.mark.parametrize("vmid", [99, 1000000000])
def test_vm_rejects_vmid_outside_supported_range(vmid):
    vm = make_vm(module_params(vmid=vmid))
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.execute_resource_module()

    assert "VMID must be between 100 and 999999999" in vm.module.fail_json.call_args.kwargs["msg"]


def test_create_omits_parameters_equal_to_api_defaults():
    api = FakeApi()
    result = make_vm(api=api).create_resource()

    assert result == "UPID:pve01:task"
    assert api.create_parameters == {"vmid": 100}
    assert api.task_upids == ["UPID:pve01:task"]


def test_vm_task_wait_uses_short_timeout(monkeypatch):
    wait_for_task = Mock()
    monkeypatch.setattr(ProxmoxTask, "wait_for_task", wait_for_task)
    vm = make_vm()

    vm._wait_for_task("UPID:pve01:task")

    wait_for_task.assert_called_once_with("UPID:pve01:task", timeout=120)


@pytest.mark.parametrize("efitype", ["2m", "4m"])
def test_create_with_ovmf_allocates_basic_efi_disk(efitype):
    api = FakeApi()
    efidisk = {"storage": "company-lvm", "efitype": efitype, "pre_enrolled_keys": True}
    api.storage_entries = [
        {"storage": "company-lvm", "active": 1, "enabled": 1, "content": "images"}
    ]
    vm = make_vm(module_params(bios="ovmf", efidisk=efidisk), api)

    vm.create_resource()

    assert api.create_parameters["bios"] == "ovmf"
    assert api.create_parameters["efidisk0"] == "company-lvm:1,efitype={0},pre-enrolled-keys=1".format(efitype)
    assert api.storage_queries == 1
    assert api.storage_get_calls == [{"content": "images", "enabled": 1}]


@pytest.mark.parametrize(
    ("storage_entries", "message"),
    [([], "not enabled for images"), ([{"storage": "company-lvm", "active": 0}], "not active")],
)
def test_create_with_ovmf_rejects_unavailable_or_inactive_efi_storage(storage_entries, message):
    api = FakeApi()
    api.storage_entries = storage_entries
    vm = make_vm(
        module_params(
            bios="ovmf",
            efidisk={"storage": "company-lvm", "efitype": "4m", "pre_enrolled_keys": True},
        ),
        api,
    )
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.create_resource()

    assert message in vm.module.fail_json.call_args.kwargs["msg"]
    assert api.create_parameters is None


@pytest.mark.parametrize("size", ["32G", "32g", "32"])
def test_disk_allocation_is_formatted_only_for_creation(size):
    api = FakeApi()
    vm = make_vm(
        module_params(disk=[{"name": "scsi0", "storage": "local-lvm", "size": size}]),
        api,
    )

    vm.create_resource()

    assert api.create_parameters == {"vmid": 100, "scsi0": "local-lvm:32"}
    assert api.storage_queries == 1


def test_disk_definitions_are_ignored_by_update_comparison():
    vm = make_vm(module_params(disk=[{"name": "scsi0", "storage": "missing", "size": "999G"}]))
    resource = {
        "scsi0": "local-lvm:vm-100-disk-0,size=32G",
        "scsi1": "local-lvm:vm-100-disk-1,size=64G",
    }

    assert "disk" not in vm._desired_parameters()
    assert vm.get_update_parameters(resource) == {}


def test_existing_vm_does_not_validate_creation_disk_storage():
    api = Mock()
    api.nodes.get.return_value = [{"node": "pve01"}]
    api.nodes.return_value.qemu.get.return_value = [{"vmid": 100}]
    api.nodes.return_value.qemu.return_value.status.current.get.return_value = {
        "status": "running",
        "qmpstatus": "running",
    }
    api.nodes.return_value.qemu.return_value.config.get.return_value = {"name": "existing"}
    vm = make_vm(
        module_params(disk=[{"name": "scsi0", "storage": "missing", "size": "32G"}]),
        api,
    )
    vm.client.validate_pve_permissions = Mock()

    assert vm.get_resource() == {"name": "existing"}
    assert vm._vm_status == "running"
    api.nodes.get.assert_called_once_with()
    api.nodes.return_value.qemu.get.assert_called_once_with()
    api.nodes.return_value.qemu.return_value.status.current.get.assert_called_once_with()
    api.nodes.return_value.storage.get.assert_not_called()


def test_missing_vm_is_detected_before_status_lookup():
    api = Mock()
    api.nodes.get.return_value = [{"node": "pve01"}]
    api.nodes.return_value.qemu.get.return_value = [{"vmid": 100}, {"vmid": 101}]
    vm = make_vm(module_params(vmid=107), api)
    vm.client.validate_pve_permissions = Mock()

    assert vm.get_resource() is None

    api.nodes.get.assert_called_once_with()
    api.nodes.return_value.qemu.get.assert_called_once_with()
    api.nodes.return_value.qemu.return_value.status.current.get.assert_not_called()
    api.nodes.return_value.qemu.return_value.config.get.assert_not_called()


def test_creation_check_mode_includes_disk_allocation_without_storage_queries():
    api = FakeApi()
    vm = make_vm(
        module_params(disk=[{"name": "scsi0", "storage": "local-lvm", "size": "32G"}]),
        api,
    )

    assert vm.get_check_mode_resource("create") == {"vmid": 100, "scsi0": "local-lvm:32"}
    assert api.storage_queries == 0


@pytest.mark.parametrize("ide2", ["none", "cdrom"])
def test_ide2_fixed_media_option_is_configured_by_vm_module(ide2):
    vm = make_vm(module_params(ide2=ide2))
    expected = "{0},media=cdrom".format(ide2)

    assert vm._creation_parameters()["ide2"] == expected
    assert vm.get_update_parameters({"ide2": expected}) == {}


def test_create_keeps_non_default_parameters():
    api = FakeApi()
    params = module_params(
        machine={"name": "pc", "type": "q35", "version": "latest"},
        memory=4096,
        name="test-vm",
        vga="qxl",
        scsihw="virtio-scsi-pci",
        network=[
            {"name": "net0", "model": "virtio", "bridge": "vmbr0", "firewall": True, "tag": 42},
            {"name": "net1", "model": "e1000", "bridge": "vmbr1", "firewall": False},
        ],
    )

    make_vm(params, api).create_resource()

    assert api.create_parameters == {
        "vmid": 100,
        "name": "test-vm",
        "memory": 4096,
        "machine": "q35",
        "vga": "qxl",
        "scsihw": "virtio-scsi-pci",
        "net0": "virtio,bridge=vmbr0,firewall=1,tag=42",
        "net1": "e1000,bridge=vmbr1,firewall=0",
    }


@pytest.mark.parametrize("version", ["10.0", "10.0+pve1"])
def test_create_serializes_pinned_machine_version(version):
    api = FakeApi()
    params = module_params(machine={"name": "pc", "type": "q35", "version": version})

    make_vm(params, api).create_resource()

    assert api.create_parameters["machine"] == "pc-q35-{0}".format(version)
    assert api.machine_get_calls == ["nodes/pve01/capabilities/qemu/machines"]


def test_create_rejects_unsupported_machine_version_before_creating_vm():
    api = FakeApi()
    vm = make_vm(
        module_params(machine={"name": "pc", "type": "q35", "version": "10.4"}),
        api,
    )
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.create_resource()

    assert "pc-q35-10.4 is not available" in vm.module.fail_json.call_args.kwargs["msg"]
    assert api.create_parameters is None
    assert api.machine_get_calls == ["nodes/pve01/capabilities/qemu/machines"]


def test_cpu_argument_matches_api_parameter_name():
    vm = make_vm(module_params(cpu="host"))

    assert vm._desired_parameters() == {"cpu": "host"}


def test_vga_choices_include_proxmox_device_types():
    assert VGA_CHOICES == [
        "cirrus",
        "qxl",
        "qxl2",
        "qxl3",
        "qxl4",
        "none",
        "serial0",
        "serial1",
        "serial2",
        "serial3",
        "std",
        "virtio",
        "virtio-gl",
        "vmware",
    ]


def test_empty_config_values_match_parameter_defaults():
    vm = make_vm(
        module_params(
            memory=512,
            cores=1,
            sockets=1,
            cpu="kvm64",
            bios="seabios",
            ostype="other",
            scsihw="lsi",
        )
    )
    resource = {
        "memory": "",
        "cores": None,
        "cpu": "",
        "ostype": "",
        "scsihw": "",
    }

    assert vm.get_update_parameters(resource) == {}


def test_scsi_controller_default_is_omitted_on_create():
    api = FakeApi()
    vm = make_vm(module_params(scsihw="lsi"), api)

    vm.create_resource()

    assert api.create_parameters == {"vmid": 100}


def test_numeric_config_strings_match_integer_parameters():
    vm = make_vm(module_params(memory=512))

    assert vm.get_update_parameters({"memory": "512"}) == {}


@pytest.mark.parametrize(
    ("requested", "current", "expected"),
    [
        ({"name": "pc", "type": "q35", "version": "latest"}, "pc-q35-latest", {}),
        ({"name": "pc", "type": "q35", "version": "latest"}, "q35", {}),
        ({"name": "pc", "type": "i440fx", "version": "latest"}, "i440fx", {}),
        ({"name": "pc", "type": "q35", "version": "latest"}, "pc-q35-5.1", {}),
        ({"name": "pc", "type": "i440fx", "version": "latest"}, "pc-i440fx-5.1", {}),
        ({"name": "pc", "type": "q35", "version": "10.0"}, "pc-q35-10.0", {}),
        ({"name": "pc", "type": "q35", "version": "10.0+pve1"}, "pc-q35-10.0+pve1", {}),
        ({"name": "pc", "type": "q35", "version": "10.0"}, "pc-q35-10.0+pve1", {"machine": "pc-q35-10.0"}),
        ({"name": "pc", "type": "q35", "version": "10.0+pve1"}, "pc-q35-10.0", {"machine": "pc-q35-10.0+pve1"}),
        ({"name": "pc", "type": "i440fx", "version": "10.0+pve1"}, "pc-i440fx-10.0+pve1", {}),
        ({"name": "pc", "type": "q35", "version": "latest"}, "pc-q35-10.0+pve1", {}),
    ],
)
def test_machine_comparison_handles_latest_and_pinned_versions(requested, current, expected):
    vm = make_vm(module_params(machine=requested))

    assert vm.get_update_parameters({"machine": current}) == expected


def test_machine_comparison_still_detects_chipset_change():
    vm = make_vm(module_params(machine={"name": "pc", "type": "q35", "version": "latest"}))

    assert vm.get_update_parameters({"machine": "pc-i440fx-11.0"}) == {"machine": "q35"}


@pytest.mark.parametrize(
    ("requested_bios", "current_bios"),
    [("seabios", "ovmf"), ("ovmf", "seabios")],
)
def test_bios_change_preserves_existing_efi_disk(requested_bios, current_bios):
    api = FakeApi()
    vm = make_vm(
        module_params(
            bios=requested_bios,
            efidisk={"storage": "company-lvm", "efitype": "4m", "pre_enrolled_keys": True},
        ),
        api,
    )
    resource = {
        "bios": current_bios,
        "efidisk0": "local-lvm:vm-100-disk-1,efitype=4m,ms-cert=2023k,pre-enrolled-keys=1,size=4M",
    }

    expected = {"delete": "bios"} if requested_bios == "seabios" else {"bios": "ovmf"}
    updates = vm.get_update_parameters(resource)
    assert updates == expected

    vm.update_resource(resource, updates)

    assert api.update_parameters == expected
    assert "efidisk0" not in api.update_parameters


def test_ovmf_update_adds_efi_disk_only_when_missing():
    api = FakeApi()
    vm = make_vm(
        module_params(
            bios="ovmf",
            efidisk={"storage": "company-lvm", "efitype": "4m", "pre_enrolled_keys": True},
        ),
        api,
    )
    api.storage_entries = [
        {"storage": "company-lvm", "active": 1, "enabled": 1, "content": "images"}
    ]

    updates = vm.get_update_parameters({"bios": "seabios"})
    resource = {"bios": "seabios"}
    vm.update_resource(resource, updates)

    assert updates == {
        "bios": "ovmf",
        "efidisk0": "company-lvm:1,efitype=4m,pre-enrolled-keys=1",
    }
    assert api.update_parameters == updates
    assert api.storage_get_calls == [{"content": "images", "enabled": 1}]


@pytest.mark.parametrize("status", ["running", "paused"])
def test_config_update_requires_vm_to_be_stopped(status):
    vm = make_vm(module_params(memory=4096))
    vm._vm_status = status
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.get_update_parameters({"memory": 2048})

    assert "power it off" in vm.module.fail_json.call_args.kwargs["msg"]


def test_config_update_fails_closed_when_vm_status_is_unknown():
    vm = make_vm(module_params(memory=4096))
    vm._vm_status = None
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.get_update_parameters({"memory": 2048})

    assert "Unable to verify VM power state" in vm.module.fail_json.call_args.kwargs["msg"]


def test_running_vm_with_no_config_changes_is_allowed():
    vm = make_vm(module_params(memory=4096))
    vm._vm_status = "running"

    assert vm.get_update_parameters({"memory": 4096}) == {}


def test_create_does_not_require_existing_vm_power_state():
    vm = make_vm()
    vm.module.check_mode = False
    vm.module.exit_json = Mock(side_effect=SystemExit)
    vm.get_resource = Mock(return_value=None)
    vm.create_resource = Mock(return_value="UPID:pve01:create")

    with pytest.raises(SystemExit):
        vm.execute_resource_module()

    vm.create_resource.assert_called_once_with()


def test_absent_state_rejects_running_vm_before_delete():
    api = Mock()
    vm = make_vm(module_params(state="absent"), api)
    vm.module.check_mode = False
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))
    vm.get_resource = Mock(return_value={"vmid": 100})
    vm._vm_status = "running"

    with pytest.raises(RuntimeError, match="module failed"):
        vm.execute_resource_module()

    assert "VM is running; power it off before deleting it." in vm.module.fail_json.call_args.kwargs["msg"]
    api.nodes.return_value.qemu.return_value.delete.assert_not_called()


def test_absent_state_check_mode_rejects_running_vm():
    vm = make_vm(module_params(state="absent"))
    vm._vm_status = "running"
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm.get_check_mode_resource("delete", resource={"vmid": 100})

    assert "power it off before deleting it" in vm.module.fail_json.call_args.kwargs["msg"]


def test_absent_state_deletes_stopped_vm():
    api = Mock()
    api.nodes.return_value.qemu.return_value.delete.return_value = "UPID:pve01:delete"
    api.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "OK",
    }
    vm = make_vm(module_params(state="absent"), api)
    vm._vm_status = "stopped"

    assert vm.delete_resource({"vmid": 100}) == "UPID:pve01:delete"
    api.nodes.return_value.tasks.assert_called_once_with("UPID:pve01:delete")


def test_omitted_parameters_do_not_change_existing_values():
    vm = make_vm()
    resource = {
        "memory": 4096,
        "cores": 4,
        "cpu": "host",
        "machine": "q35",
        "ostype": "win10",
        "vga": "qxl",
        "net0": "virtio,bridge=vmbr0",
    }

    assert vm.get_update_parameters(resource) == {}


def test_network_list_serializes_fields_and_deletes_stale_devices():
    vm = make_vm(
        module_params(
            network=[
                {"name": "net0", "model": "virtio", "bridge": "vmbr0", "firewall": True, "tag": 42}
            ]
        )
    )
    resource = {
        "net0": "e1000,bridge=vmbr0",
        "net1": "e1000,bridge=stale-bridge",
    }

    assert vm.get_update_parameters(resource) == {
        "net0": "virtio,bridge=vmbr0,firewall=1,tag=42",
        "delete": "net1",
    }


def test_formatted_value_parser_returns_literal_fields():
    assert ProxmoxResourceModule._parse_formatted_options(
        "virtio=BC:24:11:E4:07:3D,bridge=vmbr0,firewall=1"
    ) == {
        "virtio": "BC:24:11:E4:07:3D",
        "bridge": "vmbr0",
        "firewall": "1",
    }


def test_network_comparison_checks_only_requested_suboptions():
    vm = make_vm(
        module_params(
            network=[
                {"name": "net0", "model": "virtio", "bridge": "vmbr0", "firewall": True, "tag": 42}
            ]
        )
    )
    resource = {"net0": "virtio=BC:24:11:E4:07:3D,bridge=vmbr0,firewall=1,tag=42"}

    assert vm.get_update_parameters(resource) == {}


def test_network_model_change_is_detected_with_server_generated_mac():
    vm = make_vm(
        module_params(network=[{"name": "net0", "model": "virtio", "bridge": "vmbr0"}])
    )
    resource = {"net0": "e1000=BC:24:11:E4:07:3D,bridge=vmbr0"}

    assert vm.get_update_parameters(resource) == {"net0": "virtio,bridge=vmbr0"}


def test_network_create_leaves_mac_generation_to_proxmox():
    api = FakeApi()
    vm = make_vm(
        module_params(network=[{"name": "net0", "model": "virtio", "bridge": "vmbr0"}]),
        api,
    )

    vm.create_resource()

    assert api.create_parameters == {"vmid": 100, "net0": "virtio,bridge=vmbr0"}


def test_network_entry_requires_the_declared_prefix():
    vm = make_vm(module_params(network=[{"name": "foo0", "model": "virtio"}]))
    vm.module.fail_json = Mock(side_effect=RuntimeError("module failed"))

    with pytest.raises(RuntimeError, match="module failed"):
        vm._creation_parameters()

    assert "net<index>" in vm.module.fail_json.call_args.kwargs["msg"]


def test_unspecified_network_suboptions_do_not_trigger_updates():
    vm = make_vm(
        module_params(network=[{
            "name": "net0", "model": "virtio", "bridge": None,
            "firewall": None, "tag": None,
        }])
    )

    assert vm.get_update_parameters({
        "net0": "virtio=BC:24:11:E4:07:3D,bridge=vmbr0,firewall=1"
    }) == {}


def test_formatted_parameter_helpers_support_other_indexed_families():
    vm = make_vm()
    formatted = {
        "disks": [
            {"name": "scsi0", "file": "local-lvm:vm-100-disk-0", "size": "32G"},
        ]
    }
    formatted_parameters = ["disks"]
    prefixes = {"disks": "scsi"}
    primary_fields = {"disks": "file"}

    assert vm.serialize_formatted_parameters(
        formatted,
        formatted_parameters,
        prefixes,
        primary_fields,
    ) == {"scsi0": "local-lvm:vm-100-disk-0,size=32G"}
    assert vm.get_formatted_parameter_updates(
        {"scsi0": "local-lvm:vm-100-disk-0,size=32G"},
        formatted,
        formatted_parameters,
        prefixes,
        primary_fields,
    ) == {}


def test_empty_network_list_deletes_all_existing_devices():
    vm = make_vm(module_params(network=[]))

    assert vm.get_update_parameters({"net0": "virtio,bridge=vmbr0", "net1": "e1000"}) == {
        "delete": "net0,net1"
    }


def test_update_uses_delete_for_defaults_and_updates_other_values():
    vm = make_vm(module_params(ostype="other"))
    resource = {"machine": "q35", "ostype": "win10"}

    assert vm.get_update_parameters(resource) == {"delete": "ostype"}


def test_update_and_check_mode_remove_deleted_default_key():
    api = FakeApi()
    vm = make_vm(api=api)
    resource = {"vmid": 100, "machine": "q35"}
    updates = {"delete": "machine"}

    assert vm.update_resource(resource, updates) == {"vmid": 100}
    assert api.update_parameters == updates
    assert api.task_upids == ["UPID:pve01:task"]
    assert vm.get_check_mode_resource("update", resource, updates) == {"vmid": 100}


def test_default_filter_leaves_parameters_without_default_unchanged():
    parameters = {"name": "", "machine": "i440fx", "vga": "qxl", "custom": ""}
    defaults = {"name": "", "machine": "i440fx", "vga": ""}

    assert ProxmoxResourceModule.omit_default_parameters(parameters, defaults) == {
        "name": "",
        "vga": "qxl",
        "custom": "",
    }
