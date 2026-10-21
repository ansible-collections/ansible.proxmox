# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base lifecycle helpers shared by Proxmox modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from .proxmox import ProxmoxClient


class ProxmoxBase:
    """Common client, API error handling, and result shaping."""

    result_key = "result"

    def __init__(self, module, client=None):
        self.module = module
        self.client = client or ProxmoxClient(module)

    @property
    def api(self):
        return self.client.api

    def validate_vmid(self):
        vmid = self.module.params.get("vmid")
        if vmid is not None and not 100 <= vmid <= 999999999:
            self.module.fail_json(msg="VMID must be between 100 and 999999999.")

    def validate_resource(self, resource_type, resource_name, getter, resource_key=None, fail_on_missing=True):
        """Ensure a Proxmox resource exists before using its endpoint."""
        resource = self.call_api(
            "Retrieving {0} {1}".format(resource_type, resource_name),
            getter,
            return_none_on_404=True,
        )
        if resource_key:
            exists = any(
                str(item.get(resource_key)) == str(resource_name)
                for item in resource or []
                if isinstance(item, dict)
            )
        else:
            exists = resource is not None

        if not exists and fail_on_missing:
            self.module.fail_json(msg="{0} {1} does not exist".format(resource_type.capitalize(), resource_name))
        return exists

    def call_api(self, operation, function, *args, **kwargs):
        return_none_on_404 = kwargs.pop("return_none_on_404", False)
        try:
            return function(*args, **kwargs)
        except Exception as exception:
            if return_none_on_404 and self.client.exception_status(exception) == 404:
                return None
            self._fail_invalid_parameter(exception, kwargs)
            self.client.fail_request(operation, exception)

    def _fail_invalid_parameter(self, exception, parameters):
        if self.client.exception_status(exception) != 400:
            return

        errors = getattr(exception, "errors", None)
        if not isinstance(errors, dict):
            return

        for parameter, value in parameters.items():
            if parameter in errors:
                self.module.fail_json(
                    msg="{0} value for {1} is not available".format(value, parameter)
                )

    def prepare_result(self, changed, resource=None, **values):
        result = {"changed": changed, self.result_key: resource}
        result.update(values)
        return result

    def exit(self, changed, resource=None, **values):
        self.module.exit_json(**self.prepare_result(changed, resource, **values))
