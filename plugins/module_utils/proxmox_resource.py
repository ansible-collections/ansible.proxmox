# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from .proxmox_base import ProxmoxBase


class ProxmoxResourceModule(ProxmoxBase):
    """OCI-style create/update/delete lifecycle for Proxmox resources."""

    def get_resource(self):
        raise NotImplementedError("get_resource must be implemented")

    def create_resource(self):
        raise NotImplementedError("create_resource must be implemented")

    def get_update_parameters(self, resource):
        return {}

    def update_resource(self, resource, updates):
        raise NotImplementedError("update_resource must be implemented")

    def delete_resource(self, resource):
        raise NotImplementedError("delete_resource must be implemented")

    @staticmethod
    def omit_default_parameters(parameters, parameter_defaults):
        """Omit configured API defaults while preserving values without a default."""
        return {
            key: value
            for key, value in parameters.items()
            if parameter_defaults.get(key, "") == "" or value != parameter_defaults[key]
        }

    @staticmethod
    def _serialize_formatted_options(options, primary_field=None):
        fields = []
        primary_value = options.get(primary_field) if primary_field else None
        if primary_value is not None:
            fields.append(str(primary_value))

        for option, value in options.items():
            if option == primary_field or value is None:
                continue
            if isinstance(value, bool):
                value = "1" if value else "0"
            fields.append("{0}={1}".format(option, value))
        return ",".join(fields)

    def _formatted_entries(self, parent, entries, prefix):
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or "name" not in entry:
                self.module.fail_json(
                    msg="Each {0} entry must be a mapping with a name such as {1}0.".format(parent, prefix)
                )

            api_parameter = entry["name"]
            if prefix is None:
                if api_parameter != parent:
                    self.module.fail_json(msg="{0} entry name must be {0}.".format(parent))
            else:
                suffix = api_parameter[len(prefix) :] if isinstance(api_parameter, str) else ""
                if not isinstance(api_parameter, str) or not api_parameter.startswith(prefix) or not suffix.isdigit():
                    self.module.fail_json(
                        msg="{0} entry name must use the {1}<index> format.".format(parent, prefix)
                    )
            if api_parameter in seen:
                self.module.fail_json(msg="Duplicate formatted API parameter {0}.".format(api_parameter))
            seen.add(api_parameter)
            options = {key: value for key, value in entry.items() if key != "name"}
            yield api_parameter, options

    def serialize_formatted_parameters(
        self,
        parameters,
        formatted_parameters,
        prefixes,
        primary_fields=None,
        fixed_options=None,
    ):
        """Expand structured formatted parameters into Proxmox API strings."""
        primary_fields = primary_fields or {}
        fixed_options = fixed_options or {}
        serialized = {key: value for key, value in parameters.items() if key not in formatted_parameters}

        for parent in formatted_parameters:
            entries = parameters.get(parent)
            if entries is None:
                continue
            if isinstance(entries, str):
                primary_field = primary_fields.get(parent)
                options = {primary_field: entries} if primary_field else {"value": entries}
                options.update(fixed_options.get(parent, {}))
                serialized[parent] = self._serialize_formatted_options(options, primary_field)
                continue
            if not isinstance(entries, list):
                self.module.fail_json(msg="{0} must be a list.".format(parent))
            for api_parameter, options in self._formatted_entries(
                parent,
                entries,
                prefixes.get(parent, parent),
            ):
                options.update(fixed_options.get(parent, {}))
                serialized[api_parameter] = self._serialize_formatted_options(
                    options,
                    primary_fields.get(parent),
                )
        return serialized

    @staticmethod
    def _parse_formatted_options(value):
        if not isinstance(value, str) or not value:
            return {}

        options = {}
        for item in value.split(","):
            key, separator, field_value = item.partition("=")
            if key.strip():
                options[key.strip()] = field_value.strip() if separator else ""
        return options

    @staticmethod
    def _formatted_values_equal(current, desired):
        if isinstance(desired, bool):
            desired = "1" if desired else "0"
        return current is not None and str(current) == str(desired)

    def get_formatted_parameter_updates(
        self,
        resource,
        parameters,
        formatted_parameters,
        prefixes,
        primary_fields=None,
        fixed_options=None,
    ):
        """Compare structured formatted options with API strings and remove stale indexed entries."""
        primary_fields = primary_fields or {}
        fixed_options = fixed_options or {}
        updates = {}
        deletions = []

        for parent in formatted_parameters:
            entries = parameters.get(parent)
            if entries is None:
                continue
            if isinstance(entries, str):
                primary_field = primary_fields.get(parent)
                desired_options = {primary_field: entries} if primary_field else {"value": entries}
                desired_options.update(fixed_options.get(parent, {}))
                current_options = self._parse_formatted_options(resource.get(parent))
                if primary_field and primary_field not in current_options and current_options:
                    primary_key = next(
                        (key for key, value in current_options.items() if value == ""),
                        None,
                    )
                    if primary_key is None:
                        primary_key = next(iter(current_options))
                    current_options.pop(primary_key)
                    current_options[primary_field] = primary_key
                for key, value in fixed_options.get(parent, {}).items():
                    current_options.setdefault(key, value)
                if all(
                    self._formatted_values_equal(current_options.get(key), value)
                    for key, value in desired_options.items()
                ):
                    continue
                updates[parent] = self._serialize_formatted_options(desired_options, primary_field)
                continue
            if not isinstance(entries, list):
                self.module.fail_json(msg="{0} must be a list.".format(parent))

            prefix = prefixes.get(parent, parent)
            primary_field = primary_fields.get(parent)
            desired_names = set()
            for api_parameter, desired_options in self._formatted_entries(parent, entries, prefix):
                desired_names.add(api_parameter)
                current_options = self._parse_formatted_options(resource.get(api_parameter))
                if primary_field and primary_field not in current_options and current_options:
                    primary_key = next(
                        (key for key, value in current_options.items() if value == ""),
                        None,
                    )
                    if primary_key is None:
                        primary_key = next(iter(current_options))
                    current_options.pop(primary_key)
                    current_options[primary_field] = primary_key
                for key, value in fixed_options.get(parent, {}).items():
                    current_options.setdefault(key, value)
                requested_options = {
                    key: value
                    for key, value in fixed_options.get(parent, {}).items()
                    if value is not None
                }
                requested_options.update(
                    {key: value for key, value in desired_options.items() if value is not None}
                )
                if all(
                    self._formatted_values_equal(current_options.get(key), value)
                    for key, value in requested_options.items()
                ):
                    continue

                updated_options = dict(current_options)
                updated_options.update(requested_options)
                updates[api_parameter] = self._serialize_formatted_options(
                    updated_options,
                    primary_field,
                )

            if prefix is not None:
                current_names = {
                    key
                    for key in resource
                    if key.startswith(prefix) and key[len(prefix) :].isdigit()
                }
                deletions.extend(sorted(current_names - desired_names))

        if deletions:
            existing_deletions = [key for key in updates.get("delete", "").split(",") if key]
            existing_deletions.extend(key for key in deletions if key not in existing_deletions)
            updates["delete"] = ",".join(existing_deletions)
        return updates

    @staticmethod
    def parameter_values_equal(current, desired):
        """Compare API values while tolerating numeric values serialized as strings."""
        if current == desired:
            return True
        if isinstance(current, str):
            if isinstance(desired, int) and not isinstance(desired, bool):
                try:
                    return int(current) == desired
                except ValueError:
                    return False
            if isinstance(desired, float):
                try:
                    return float(current) == desired
                except ValueError:
                    return False
        return False

    @staticmethod
    def get_parameter_updates(resource, desired_parameters, parameter_defaults):
        """Compare desired values with resource values, treating empty defaults as API defaults."""
        updates = {}
        deleted_parameters = []

        for key, value in desired_parameters.items():
            current = resource.get(key)
            default_value = parameter_defaults.get(key, "")
            if default_value != "" and ProxmoxResourceModule.parameter_values_equal(value, default_value):
                if current is None or current == "" or ProxmoxResourceModule.parameter_values_equal(current, default_value):
                    continue
                deleted_parameters.append(key)
            elif not ProxmoxResourceModule.parameter_values_equal(current, value):
                updates[key] = value

        if deleted_parameters:
            updates["delete"] = ",".join(deleted_parameters)
        return updates

    @staticmethod
    def apply_parameter_updates(resource, updates):
        """Predict or return a resource after API config updates, including deleted keys."""
        updated = dict(resource)
        for key in updates.get("delete", "").split(","):
            if key:
                updated.pop(key, None)
        updated.update({key: value for key, value in updates.items() if key != "delete"})
        return updated

    def get_check_mode_resource(self, operation, resource=None, updates=None):
        if operation == "delete":
            return None
        if operation == "update" and isinstance(resource, dict) and isinstance(updates, dict):
            return self.apply_parameter_updates(resource, updates)
        return resource

    def execute_resource_module(self):
        state = self.module.params.get("state", "present")
        resource = self.get_resource()

        if state == "absent":
            if resource is None:
                self.exit(changed=False, resource=None)
            if self.module.check_mode:
                self.exit(changed=True, resource=self.get_check_mode_resource("delete", resource=resource))
            result = self.delete_resource(resource)
            self.exit(changed=True, resource=result)

        if resource is None:
            if self.module.check_mode:
                self.exit(changed=True, resource=self.get_check_mode_resource("create"))
            self.exit(changed=True, resource=self.create_resource())

        updates = self.get_update_parameters(resource)
        if not updates:
            self.exit(changed=False, resource=resource)
        if self.module.check_mode:
            self.exit(changed=True, resource=self.get_check_mode_resource("update", resource=resource, updates=updates))
        self.exit(changed=True, resource=self.update_resource(resource, updates))

    def execute(self):
        self.execute_resource_module()
