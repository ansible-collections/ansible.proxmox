# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import Mock

import pytest

from ansible_collections.ansible.proxmox.plugins.modules import proxmox_sdn_zone
from ansible_collections.ansible.proxmox.plugins.modules.proxmox_sdn_zone import ProxmoxSdnZoneModule


@pytest.mark.parametrize("check_mode", [False, True])
def test_create_zone_omits_defaults_and_predicts_without_writing(sdn_zone_environment, check_mode):
    module, client, api = sdn_zone_environment(check_mode=check_mode, type="simple", dedicated_vrf=False)
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    expected = {"zone": "office", "type": "simple"}
    if not check_mode:
        expected["digest"] = "digest-1"
    assert result.value.args[0] == {"changed": True, "zone": expected}
    assert api.writes == ([] if check_mode else [("POST", {"zone": "office", "type": "simple"})])
    client.validate_pve_permissions.assert_called_once_with(api, "/sdn/zones")


def test_missing_zone_is_discovered_from_the_collection_list(sdn_zone_environment):
    module, client, api = sdn_zone_environment(type="simple")
    handler = ProxmoxSdnZoneModule(module, client)

    assert handler.get_resource() is None
    assert api.reads == [("LIST", None, {})]
    assert api.writes == []


def test_update_maps_options_uses_digest_and_verifies_readback(sdn_zone_environment):
    record = {"zone": "office", "type": "vlan", "bridge": "vmbr0", "digest": "digest-1"}
    module, client, api = sdn_zone_environment(
        records={"office": record}, type="vlan", bridge="vmbr1", bridge_disable_mac_learning=True,
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert result.value.args[0]["changed"] is True
    assert result.value.args[0]["zone"]["bridge"] == "vmbr1"
    assert result.value.args[0]["zone"]["bridge-disable-mac-learning"] == 1
    assert api.writes == [("PUT", "office", {
        "bridge": "vmbr1", "bridge-disable-mac-learning": 1, "digest": "digest-1",
    })]


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_string_clears_named_field_and_resets_defaults(sdn_zone_environment, check_mode):
    record = {
        "zone": "office", "type": "simple", "dedicated-vrf": 1, "dns": "dns1",
        "dnszone": "example.com", "digest": "digest-1",
    }
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records={"office": record}, type="simple", dedicated_vrf=False, dnszone="",
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    zone = result.value.args[0]["zone"]
    assert "dedicated-vrf" not in zone
    assert "dnszone" not in zone
    assert zone["dns"] == "dns1"
    assert ("digest" not in zone) is check_mode
    assert api.writes == ([] if check_mode else [("PUT", "office", {
        "delete": "dedicated-vrf,dnszone", "digest": "digest-1",
    })])


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_mtu_clears_optional_integer(sdn_zone_environment, check_mode):
    record = {"zone": "office", "type": "simple", "mtu": 1450, "digest": "digest-1"}
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records={"office": record}, type="simple", mtu="",
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert "mtu" not in result.value.args[0]["zone"]
    assert ("digest" not in result.value.args[0]["zone"]) is check_mode
    assert api.writes == ([] if check_mode else [("PUT", "office", {
        "delete": "mtu", "digest": "digest-1",
    })])


@pytest.mark.parametrize("check_mode", [False, True])
def test_matching_zone_is_idempotent(sdn_zone_environment, check_mode):
    record = {"zone": "office", "type": "simple", "dedicated-vrf": 1, "digest": "digest-1"}
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records={"office": record}, type="simple", dedicated_vrf=True,
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()

    assert result.value.args[0] == {"changed": False, "zone": record}
    assert api.writes == []


@pytest.mark.parametrize("current_nodes", ["pve02,pve01", {"pve02": 1, "pve01": 1}])
def test_node_lists_compare_without_order_differences(sdn_zone_environment, current_nodes):
    record = {"zone": "office", "type": "simple", "nodes": current_nodes}
    module, client, api = sdn_zone_environment(
        records={"office": record}, type="simple", nodes=["pve01", "pve02"],
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()
    assert result.value.args[0] == {"changed": False, "zone": record}
    assert api.writes == []


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_node_list_removes_the_node_restriction(sdn_zone_environment, check_mode):
    record = {"zone": "office", "type": "simple", "nodes": "pve01", "digest": "digest-1"}
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records={"office": record}, type="simple", nodes=[],
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()
    assert "nodes" not in result.value.args[0]["zone"]
    if check_mode:
        assert "digest" not in result.value.args[0]["zone"]
        assert api.writes == []
    else:
        assert api.writes == [("PUT", "office", {"delete": "nodes", "digest": "digest-1"})]


@pytest.mark.parametrize("zone_type,options,message", [
    ("vlan", {}, "requires bridge"),
    ("qinq", {"bridge": "vmbr0"}, "requires tag"),
    ("evpn", {"controller": "ctrl1"}, "requires vrf_vxlan"),
    ("faucet", {"dp_id": 1}, "requires controller"),
    ("vxlan", {}, "exactly one of peers or fabric"),
    ("vxlan", {"peers": "192.0.2.1", "fabric": "fabric1"}, "exactly one of peers or fabric"),
])
def test_creation_validates_required_type_options(sdn_zone_environment, zone_type, options, message):
    module, client, api = sdn_zone_environment(type=zone_type, **options)
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match=message):
        handler.execute()
    assert api.writes == []


def test_rejects_options_not_supported_by_zone_type(sdn_zone_environment):
    module, client, api = sdn_zone_environment(type="simple", bridge="vmbr0")
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match="not supported for SDN zone type simple"):
        handler.execute()
    assert api.writes == []


def test_cannot_clear_required_type_option(sdn_zone_environment):
    record = {"zone": "office", "type": "vlan", "bridge": "vmbr0"}
    module, client, api = sdn_zone_environment(records={"office": record}, type="vlan", bridge="")
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match="requires bridge"):
        handler.execute()
    assert api.writes == []


@pytest.mark.parametrize("exists", [False, True])
def test_empty_mac_is_rejected_before_evpn_mutation(sdn_zone_environment, exists):
    records = {}
    if exists:
        records["office"] = {
            "zone": "office", "type": "evpn", "controller": "ansible",
            "vrf-vxlan": 1000, "mac": "02:00:00:00:00:01",
        }
    module, client, api = sdn_zone_environment(
        records=records, type="evpn", controller="ansible", vrf_vxlan=1000, mac="",
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match="mac cannot be cleared for EVPN zones"):
        handler.execute()
    assert api.writes == []


def test_rejects_type_changes_and_stale_digests_before_writing(sdn_zone_environment):
    record = {"zone": "office", "type": "simple", "digest": "digest-1"}
    module, client, api = sdn_zone_environment(records={"office": record}, type="vlan", digest="old")
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match="different type"):
        handler.get_resource()
    assert api.writes == []

    module.params["type"] = "simple"
    with pytest.raises(module.Fail, match="digest does not match"):
        handler.get_resource()
    assert api.writes == []


def test_rejects_invalid_zone_ids_before_api_access(sdn_zone_environment):
    module, client, api = sdn_zone_environment(zone="bad-zone", type="simple")
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Fail, match="2 to 8 alphanumeric"):
        handler.get_resource()
    client.validate_pve_permissions.assert_not_called()
    assert api.reads == []


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("exists", [False, True])
def test_delete_and_repeated_delete(sdn_zone_environment, check_mode, exists):
    records = {"office": {"zone": "office", "type": "evpn", "controller": "ansible", "digest": "digest-1"}} if exists else {}
    module, client, api = sdn_zone_environment(
        check_mode=check_mode, records=records, state="absent", type="evpn",
        controller="ansible", vrf_vxlan=1000, secondary_controllers=[],
    )
    handler = ProxmoxSdnZoneModule(module, client)
    with pytest.raises(module.Exit) as result:
        handler.execute()
    assert result.value.args[0] == {"changed": exists, "zone": None}
    assert api.writes == ([] if check_mode or not exists else [("DELETE", "office", {})])


def test_main_uses_shared_resource_arguments_and_type_requirement(monkeypatch, sdn_zone_environment):
    module, _client, _api = sdn_zone_environment(type="simple")
    factory = Mock(return_value=module)
    monkeypatch.setattr(proxmox_sdn_zone, "AnsibleModule", factory)
    execute = Mock()
    monkeypatch.setattr(ProxmoxSdnZoneModule, "execute", execute)
    proxmox_sdn_zone.main()

    spec = factory.call_args.kwargs
    assert spec["supports_check_mode"] is True
    assert spec["required_if"] == [("state", "present", ["type"])]
    assert spec["argument_spec"]["zone"]["required"] is True
    assert spec["argument_spec"]["type"]["choices"] == ["evpn", "faucet", "qinq", "simple", "vlan", "vxlan"]
    assert spec["argument_spec"]["mtu"]["type"] == "raw"
    assert spec["argument_spec"]["vxlan_port"]["type"] == "raw"
    assert "delete" not in spec["argument_spec"]
    assert ["api_password", "api_token_id"] in spec["mutually_exclusive"]
    execute.assert_called_once()
