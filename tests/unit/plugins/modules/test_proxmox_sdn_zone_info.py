# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import Mock

import pytest
from proxmoxer.core import ResourceException

from ansible_collections.ansible.proxmox.plugins.modules import proxmox_sdn_zone_info
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_sdn_zone_info import ProxmoxSdnZoneInfoModule


@pytest.mark.parametrize("check_mode", [False, True])
def test_info_lists_zones_and_forwards_filters(sdn_zone_environment, check_mode):
    records = {
        "vxlan1": {"zone": "vxlan1", "type": "vxlan"},
        "vlan1": {"zone": "vlan1", "type": "vlan"},
    }
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records=records, zone=None, type="vxlan", running=True, pending=False,
    )
    handler = ProxmoxSdnZoneInfoModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert result.value.args[0] == {"changed": False, "zones": [records["vxlan1"]]}
    assert api.reads == [("LIST", None, {"running": 1, "pending": 0, "type": "vxlan"})]
    assert api.writes == []
    client.validate_pve_permissions.assert_called_once_with(api, "/sdn/zones")


@pytest.mark.parametrize("options,query", [
    ({"running": False}, {"running": 0}),
    ({"running": False, "pending": False}, {"running": 0, "pending": 0}),
    ({"pending": True}, {"pending": 1}),
    ({"running": False, "pending": True}, {"running": 0, "pending": 1}),
    ({"running": True, "pending": True}, {"running": 1, "pending": 1}),
])
def test_info_retrieves_one_zone_configuration(sdn_zone_environment, options, query):
    record = {"zone": "office", "type": "simple", "dedicated-vrf": 1}
    module, client, api = sdn_zone_environment(
        records={"office": record}, zone="office", **options,
    )
    handler = ProxmoxSdnZoneInfoModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert result.value.args[0] == {"changed": False, "zones": [record]}
    assert api.reads == [("LIST", None, query)]
    assert api.writes == []


def test_info_returns_empty_list_for_missing_zone(sdn_zone_environment):
    module, client, api = sdn_zone_environment(zone="missing")
    handler = ProxmoxSdnZoneInfoModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert result.value.args[0] == {"changed": False, "zones": []}
    assert api.reads == [("LIST", None, {})]
    assert api.writes == []


def test_info_does_not_hide_non_404_failures(sdn_zone_environment):
    module, client, api = sdn_zone_environment(zone="office")
    api.cluster.sdn.zones.get_error = ResourceException(403, "Forbidden", "permission denied")
    handler = ProxmoxSdnZoneInfoModule(module, client)
    with pytest.raises(module.Fail) as failure:
        handler.get_info()

    assert failure.value.args[0]["status_code"] == 403
    assert "permission denied" in failure.value.args[0]["api_error"]
    assert api.writes == []


def test_main_uses_read_only_arguments_and_excludes_zone_type(monkeypatch, sdn_zone_environment):
    module, _client, _api = sdn_zone_environment(zone=None)
    factory = Mock(return_value=module)
    monkeypatch.setattr(proxmox_sdn_zone_info, "AnsibleModule", factory)
    execute = Mock()
    monkeypatch.setattr(ProxmoxSdnZoneInfoModule, "execute_info_module", execute)
    proxmox_sdn_zone_info.main()

    spec = factory.call_args.kwargs
    assert spec["supports_check_mode"] is True
    assert "state" not in spec["argument_spec"]
    assert ["zone", "type"] in spec["mutually_exclusive"]
    assert ["running", "pending"] not in spec["mutually_exclusive"]
    assert ["api_password", "api_token_id"] in spec["mutually_exclusive"]
    execute.assert_called_once()
