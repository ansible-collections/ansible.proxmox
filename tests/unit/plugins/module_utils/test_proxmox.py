# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.ansible.proxmox.plugins.module_utils import proxmox
from ansible_collections.ansible.proxmox.plugins.module_utils import proxmox_task
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_action import ProxmoxActionModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_info import ProxmoxInfoModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_resource import ProxmoxResourceModule
from ansible_collections.ansible.proxmox.plugins.module_utils.proxmox_task import ProxmoxTask


class ExitJson(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class FailJson(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class FakeModule:
    def __init__(self, params=None, check_mode=False):
        self.params = params or {}
        self.check_mode = check_mode

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise FailJson(kwargs)


class FakeAccessEndpoint:
    def __init__(self, api):
        self.api = api
        self.permissions = FakePermissionsEndpoint(api)
        self.roles = FakeRolesEndpoint(api)


class FakePermissionsEndpoint:
    def __init__(self, api):
        self.api = api

    def get(self, path=None):
        if self.api.permission_error:
            raise self.api.permission_error
        return {path: self.api.permissions} if path else self.api.permissions


class FakeRolesEndpoint:
    def __init__(self, api):
        self.api = api

    def get(self):
        if self.api.role_error:
            raise self.api.role_error
        return self.api.roles


class FakePveApi:
    def __init__(self, permissions=None, roles=None, permission_error=None, role_error=None):
        self.permissions = permissions or {}
        self.roles = roles or []
        self.permission_error = permission_error
        self.role_error = role_error
        self.access = FakeAccessEndpoint(self)


def connection_params(**updates):
    params = {
        "api_host": "proxmox.example.test",
        "api_user": "root@pam",
        "ssh_user": None,
        "api_password": "password-value",
        "api_token_id": None,
        "api_token_secret": None,
        "api_service": "PVE",
        "api_backend": "https",
        "api_port": None,
        "ssh_port": None,
        "validate_certs": True,
        "ca_path": None,
        "api_timeout": 5,
        "api_otp": None,
        "ssh_config_file": None,
        "ssh_identity_file": None,
        "ssh_forward_agent": False,
    }
    params.update(updates)
    return params


def test_api_validation_error_identifies_unavailable_parameter_value():
    class ApiValidationError(Exception):
        status_code = 400
        errors = {"cpu": "invalid value"}

    def reject_parameter(**params):
        raise ApiValidationError()

    info = ProxmoxInfoModule(FakeModule())

    with pytest.raises(FailJson) as failure:
        info.call_api("Updating a VM", reject_parameter, cpu="unsupported-cpu")

    assert failure.value.result == {"msg": "unsupported-cpu value for cpu is not available"}


def test_argument_spec_merges_resource_arguments():
    spec = proxmox.proxmox_resource_argument_spec({"name": {"type": "str"}})

    assert spec["api_service"]["choices"] == ["PVE", "PBS"]
    assert spec["api_backend"]["choices"] == ["https", "openssh"]
    assert spec["ssh_user"]["fallback"][1] == ["PROXMOX_SSH_USER"]
    assert spec["ssh_port"]["fallback"][1] == ["PROXMOX_SSH_PORT"]
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["name"] == {"type": "str"}


def test_client_is_lazy_and_cached(monkeypatch):
    calls = []

    def fake_api(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    client = proxmox.ProxmoxClient(FakeModule(connection_params()))

    assert calls == []
    first = client.get_api()
    second = client.get_api()

    assert first is second
    assert len(calls) == 1
    assert calls[0][0] == ("proxmox.example.test",)
    assert calls[0][1] == {
        "backend": "https",
        "service": "PVE",
        "timeout": 5,
        "user": "root@pam",
        "password": "password-value",
        "verify_ssl": True,
    }


def test_https_uses_api_user_when_both_user_options_are_configured(monkeypatch):
    calls = []

    def fake_api(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    params = connection_params(ssh_user="root")

    proxmox.ProxmoxClient(FakeModule(params)).get_api()

    assert calls[0][1]["user"] == "root@pam"


def test_https_token_supports_pbs_ca_and_full_token_identifier(monkeypatch):
    calls = []

    def fake_api(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    module = FakeModule(
        connection_params(
            api_user=None,
            api_password=None,
            api_token_id="backup@pbs!automation",
            api_token_secret="token-value",
            api_service="PBS",
            api_port=8007,
            ca_path="/etc/pki/proxmox-ca.pem",
        )
    )

    proxmox.ProxmoxClient(module).get_api()

    assert calls[0][1] == {
        "backend": "https",
        "service": "PBS",
        "timeout": 5,
        "port": 8007,
        "user": "backup@pbs",
        "token_name": "automation",
        "token_value": "token-value",
        "verify_ssl": "/etc/pki/proxmox-ca.pem",
    }


@pytest.mark.parametrize(
    ("permissions", "should_fail"),
    [
        ({"Sys.Audit": True, "VM.Audit": True, "VM.Allocate": True}, False),
        ({"Sys.Audit": True, "VM.Audit": True}, True),
        ({"Sys.Audit": True, "VM.Audit": False, "VM.Allocate": True}, True),
    ],
)
def test_pve_role_validation_checks_all_propagated_role_privileges(permissions, should_fail):
    role_privileges = "Sys.Audit,VM.Audit,VM.Allocate"
    module = FakeModule(connection_params())
    api = FakePveApi(
        permissions=permissions,
        roles=[{"roleid": "Administrator", "privs": role_privileges}],
    )
    client = proxmox.ProxmoxClient(module)

    if should_fail:
        with pytest.raises(FailJson) as failure:
            client.validate_pve_permissions(api, "/vms")
        assert "full Administrator permissions propagated on /vms" in failure.value.result["msg"]
    else:
        client.validate_pve_permissions(api, "/vms")


def test_pve_role_validation_fails_closed_when_permissions_unavailable():
    module = FakeModule(connection_params())
    api = FakePveApi(permission_error=RuntimeError("permission endpoint unavailable"))

    with pytest.raises(FailJson) as failure:
        proxmox.ProxmoxClient(module).validate_pve_permissions(api, "/vms")

    assert "Unable to verify effective PVE permissions" in failure.value.result["msg"]


@pytest.mark.parametrize("service", ["PVE", "PBS"])
def test_openssh_options_support_both_services(monkeypatch, service):
    calls = []

    def fake_api(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    monkeypatch.setattr(proxmox, "OPENSSH_WRAPPER_IMPORT_ERROR", None)
    module = FakeModule(
        connection_params(
            ssh_user="root",
            api_password=None,
            api_service=service,
            api_backend="openssh",
            api_port=8006,
            ssh_port=2222,
            ssh_config_file="/tmp/ssh-config",
            ssh_identity_file="/tmp/id_ed25519",
            ssh_forward_agent=True,
        )
    )

    proxmox.ProxmoxClient(module).get_api()

    assert calls[0][1] == {
        "backend": "openssh",
        "service": service,
        "timeout": 5,
        "port": 2222,
        "user": "root",
        "config_file": "/tmp/ssh-config",
        "identity_file": "/tmp/id_ed25519",
        "forward_ssh_agent": True,
    }


def test_openssh_uses_ssh_user_instead_of_https_user(monkeypatch):
    calls = []

    def fake_api(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    monkeypatch.setattr(proxmox, "OPENSSH_WRAPPER_IMPORT_ERROR", None)
    params = connection_params(
        api_user="root@pam",
        ssh_user="root",
        api_password=None,
        api_backend="openssh",
    )

    proxmox.ProxmoxClient(FakeModule(params)).get_api()

    assert calls[0][1]["user"] == "root"


def test_openssh_requires_dedicated_ssh_user():
    client = proxmox.ProxmoxClient(
        FakeModule(connection_params(api_password=None, api_backend="openssh"))
    )

    with pytest.raises(FailJson) as failure:
        client.connection_options()

    assert "ssh_user is required" in failure.value.result["msg"]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"api_token_id": "token", "api_token_secret": "secret"}, "Provide exactly one"),
        ({"api_password": None}, "Provide exactly one"),
        (
            {"api_password": None, "api_token_id": "token", "api_token_secret": None},
            "api_token_secret is required",
        ),
        (
            {
                "api_password": None,
                "api_backend": "openssh",
                "ssh_user": "root",
                "api_token_id": "token",
                "api_token_secret": "secret",
            },
            "cannot be used with the OpenSSH backend",
        ),
        (
            {"ca_path": "/etc/pki/proxmox-ca.pem", "validate_certs": False},
            "ca_path requires validate_certs=true",
        ),
        (
            {"api_backend": "openssh", "ssh_user": "root", "validate_certs": False},
            "cannot be used with the OpenSSH backend",
        ),
    ],
)
def test_invalid_authentication_combinations_fail(updates, message):
    client = proxmox.ProxmoxClient(FakeModule(connection_params(**updates)))

    with pytest.raises(FailJson) as failure:
        client.connection_options()

    assert message in failure.value.result["msg"]


def test_client_failure_does_not_render_third_party_exception(monkeypatch):
    def fake_api(*args, **kwargs):
        raise RuntimeError("request contained token-value")

    monkeypatch.setattr(proxmox, "ProxmoxAPI", fake_api)
    client = proxmox.ProxmoxClient(FakeModule(connection_params()))

    with pytest.raises(FailJson) as failure:
        client.get_api()

    assert failure.value.result["error_type"] == "RuntimeError"
    assert "token-value" not in str(failure.value.result)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"api_host": ""}, "api_host must not be empty"),
        ({"api_timeout": 0}, "api_timeout must be greater than zero"),
        ({"api_port": 0}, "api_port must be between 1 and 65535"),
        ({"api_port": 65536}, "api_port must be between 1 and 65535"),
        (
            {
                "api_backend": "openssh",
                "ssh_user": "root",
                "api_password": None,
                "ssh_port": 0,
            },
            "ssh_port must be between 1 and 65535",
        ),
    ],
)
def test_invalid_connection_values_fail(updates, message):
    client = proxmox.ProxmoxClient(FakeModule(connection_params(**updates)))

    with pytest.raises(FailJson) as failure:
        client.connection_options()

    assert failure.value.result["msg"] == message


class DummyResource(ProxmoxResourceModule):
    result_key = "dummy"

    def __init__(self, module, current):
        super().__init__(module)
        self.current = current
        self.operations = []

    def get_resource(self):
        return self.current

    def create_resource(self):
        self.operations.append("create")
        return {"name": self.module.params["name"], "value": self.module.params["value"]}

    def get_update_parameters(self, resource):
        if resource["value"] != self.module.params["value"]:
            return {"value": self.module.params["value"]}
        return {}

    def update_resource(self, resource, updates):
        self.operations.append("update")
        updated = dict(resource)
        updated.update(updates)
        return updated

    def delete_resource(self, resource):
        self.operations.append("delete")

    def get_check_mode_resource(self, operation, resource=None, updates=None):
        if operation == "create":
            return {"name": self.module.params["name"], "value": self.module.params["value"]}
        return super().get_check_mode_resource(operation, resource, updates)


@pytest.mark.parametrize(
    ("state", "current", "check_mode", "changed", "operation", "value"),
    [
        ("present", None, False, True, "create", "desired"),
        ("present", {"name": "demo", "value": "old"}, False, True, "update", "desired"),
        ("present", {"name": "demo", "value": "desired"}, False, False, None, "desired"),
        ("absent", {"name": "demo", "value": "old"}, False, True, "delete", None),
        ("absent", None, False, False, None, None),
        ("present", None, True, True, None, "desired"),
        ("present", {"name": "demo", "value": "old"}, True, True, None, "desired"),
    ],
)
def test_resource_lifecycle(state, current, check_mode, changed, operation, value):
    module = FakeModule({"state": state, "name": "demo", "value": "desired"}, check_mode=check_mode)
    resource = DummyResource(module, current)

    with pytest.raises(ExitJson) as result:
        resource.execute_resource_module()

    assert result.value.result["changed"] is changed
    assert resource.operations == ([] if operation is None else [operation])
    if value is None:
        assert result.value.result["dummy"] is None
    else:
        assert result.value.result["dummy"]["value"] == value


def test_resource_lifecycle_returns_delete_result():
    module = FakeModule({"state": "absent", "name": "demo"})
    resource = DummyResource(module, {"name": "demo", "value": "old"})
    resource.delete_resource = lambda current: "UPID:pve01:task"

    with pytest.raises(ExitJson) as result:
        resource.execute_resource_module()

    assert result.value.result["dummy"] == "UPID:pve01:task"


class DummyInfo(ProxmoxInfoModule):
    result_key = "information"

    def get_info(self):
        return {"version": "1.0"}


class DummyAction(ProxmoxActionModule):
    result_key = "action"

    def __init__(self, module, needed):
        super().__init__(module)
        self.needed = needed
        self.performed = False

    def is_action_needed(self):
        return self.needed

    def perform_action(self):
        self.performed = True
        return {"status": "done"}

    def get_action_result(self):
        return {"status": "current"}


def test_info_lifecycle_is_read_only():
    with pytest.raises(ExitJson) as result:
        DummyInfo(FakeModule()).execute()

    assert result.value.result == {"changed": False, "information": {"version": "1.0"}}


@pytest.mark.parametrize(
    ("needed", "check_mode", "changed", "performed"),
    [(False, False, False, False), (True, True, True, False), (True, False, True, True)],
)
def test_action_lifecycle(needed, check_mode, changed, performed):
    action = DummyAction(FakeModule(check_mode=check_mode), needed)

    with pytest.raises(ExitJson) as result:
        action.execute()

    assert result.value.result["changed"] is changed
    assert action.performed is performed


def test_task_node_parsing():
    assert ProxmoxTask.task_node("UPID:pve01:00000001:00000002:task") == "pve01"

    with pytest.raises(ValueError, match="Invalid Proxmox task UPID"):
        ProxmoxTask.task_node("not-a-upid")


class FakeTaskStatus:
    def __init__(self, statuses):
        self.statuses = list(statuses)

    def get(self):
        return self.statuses.pop(0)


class FakeTaskPath:
    def __init__(self, statuses):
        self.status = FakeTaskStatus(statuses)


class FakeTasksPath:
    def __init__(self, statuses):
        self.statuses = statuses

    def __call__(self, upid):
        return FakeTaskPath(self.statuses)


class FakeNodePath:
    def __init__(self, statuses):
        self.tasks = FakeTasksPath(statuses)


class FakeNodesPath:
    def __init__(self, statuses):
        self.statuses = statuses

    def __call__(self, node):
        return FakeNodePath(self.statuses)


class FakeTaskApi:
    def __init__(self, statuses):
        self.nodes = FakeNodesPath(statuses)


class FakeClient:
    def __init__(self, api):
        self.api = api

    def fail_request(self, operation, exception):
        raise AssertionError("Unexpected API failure")


class DummyTaskModule(ProxmoxTask):
    pass


def test_wait_for_task_returns_successful_status(monkeypatch):
    statuses = [
        {"status": "running"},
        {"status": "stopped", "exitstatus": "OK"},
    ]
    task = DummyTaskModule(FakeModule(), client=FakeClient(FakeTaskApi(statuses)))
    monkeypatch.setattr(proxmox_task.time, "sleep", lambda interval: None)

    result = task.wait_for_task("UPID:pve01:00000001:00000002:task", timeout=10)

    assert result["exitstatus"] == "OK"


def test_wait_for_task_reports_failed_exit_status():
    statuses = [{"status": "stopped", "exitstatus": "permission denied"}]
    task = DummyTaskModule(FakeModule(), client=FakeClient(FakeTaskApi(statuses)))

    with pytest.raises(FailJson) as failure:
        task.wait_for_task("UPID:pbs01:00000001:00000002:task", timeout=10)

    assert failure.value.result["msg"] == "Proxmox task failed"
    assert failure.value.result["task_exit_status"] == "permission denied"
