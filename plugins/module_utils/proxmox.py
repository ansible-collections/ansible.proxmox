# Copyright: (c) 2026, Ansible Proxmox Collection contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Proxmox connection options and lazy PVE/PBS API client construction."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import traceback

from ansible.module_utils.basic import env_fallback, missing_required_lib

PROXMOXER_IMPORT_ERROR = None
try:
    from proxmoxer import ProxmoxAPI
except ImportError:
    ProxmoxAPI = None
    PROXMOXER_IMPORT_ERROR = traceback.format_exc()

REQUESTS_IMPORT_ERROR = None
try:
    __import__("requests")
except ImportError:
    REQUESTS_IMPORT_ERROR = traceback.format_exc()

OPENSSH_WRAPPER_IMPORT_ERROR = None
try:
    __import__("openssh_wrapper")
except ImportError:
    OPENSSH_WRAPPER_IMPORT_ERROR = traceback.format_exc()


def proxmox_argument_spec(argument_spec=None):
    """Return connection options merged with a module-specific argument spec."""
    spec = {
        "api_host": {
            "type": "str",
            "required": True,
            "fallback": (env_fallback, ["PROXMOX_HOST"]),
        },
        "api_user": {
            "type": "str",
            "fallback": (env_fallback, ["PROXMOX_USER"]),
        },
        "ssh_user": {
            "type": "str",
            "fallback": (env_fallback, ["PROXMOX_SSH_USER"]),
        },
        "api_password": {
            "type": "str",
            "no_log": True,
            "fallback": (env_fallback, ["PROXMOX_PASSWORD"]),
        },
        "api_token_id": {
            "type": "str",
            "fallback": (env_fallback, ["PROXMOX_TOKEN_ID"]),
        },
        "api_token_secret": {
            "type": "str",
            "no_log": True,
            "fallback": (env_fallback, ["PROXMOX_TOKEN_SECRET"]),
        },
        "api_service": {
            "type": "str",
            "default": "PVE",
            "choices": ["PVE", "PBS"],
            "fallback": (env_fallback, ["PROXMOX_SERVICE"]),
        },
        "api_backend": {
            "type": "str",
            "default": "https",
            "choices": ["https", "openssh"],
            "fallback": (env_fallback, ["PROXMOX_BACKEND"]),
        },
        "api_port": {
            "type": "int",
            "fallback": (env_fallback, ["PROXMOX_PORT"]),
        },
        "ssh_port": {
            "type": "int",
            "fallback": (env_fallback, ["PROXMOX_SSH_PORT"]),
        },
        "validate_certs": {
            "type": "bool",
            "default": True,
            "fallback": (env_fallback, ["PROXMOX_VALIDATE_CERTS"]),
        },
        "ca_path": {
            "type": "path",
            "fallback": (env_fallback, ["PROXMOX_CA_PATH"]),
        },
        "api_timeout": {
            "type": "int",
            "default": 5,
            "fallback": (env_fallback, ["PROXMOX_API_TIMEOUT"]),
        },
        "api_otp": {
            "type": "str",
            "no_log": True,
            "fallback": (env_fallback, ["PROXMOX_OTP"]),
        },
        "ssh_config_file": {
            "type": "path",
            "fallback": (env_fallback, ["PROXMOX_SSH_CONFIG_FILE"]),
        },
        "ssh_identity_file": {
            "type": "path",
            "fallback": (env_fallback, ["PROXMOX_SSH_IDENTITY_FILE"]),
        },
        "ssh_forward_agent": {
            "type": "bool",
            "default": False,
            "fallback": (env_fallback, ["PROXMOX_SSH_FORWARD_AGENT"]),
        },
    }
    spec.update(argument_spec or {})
    return spec


def proxmox_resource_argument_spec(argument_spec=None):
    """Return connection and standard resource state arguments."""
    resource_spec = {
        "state": {
            "type": "str",
            "choices": ["present", "absent"],
            "default": "present",
        },
    }
    resource_spec.update(argument_spec or {})
    return proxmox_argument_spec(resource_spec)


def proxmox_required_together():
    """Return constraints shared by all Proxmox modules."""
    return [["api_token_id", "api_token_secret"]]


def proxmox_mutually_exclusive():
    """Return authentication options that cannot be combined."""
    return [["api_password", "api_token_id"]]


def _exception_status(exception):
    """Extract an HTTP status without rendering a potentially sensitive error."""
    for attribute in ("status", "status_code"):
        value = getattr(exception, attribute, None)
        if value is not None:
            return value

    response = getattr(exception, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    return None


class ProxmoxClient:
    """Validate connection parameters and lazily construct a proxmoxer client."""

    def __init__(self, module):
        self.module = module
        self._api = None

    def _fail(self, message, **details):
        self.module.fail_json(msg=message, **details)

    def fail_request(self, operation, exception):
        """Fail without exposing a third-party exception message or credentials."""
        details = {"error_type": type(exception).__name__}
        status = _exception_status(exception)
        if status is not None:
            details["status_code"] = status
        self._fail("{0} failed".format(operation), **details)

    @staticmethod
    def exception_status(exception):
        """Expose HTTP status inspection to lifecycle helpers."""
        return _exception_status(exception)

    def _token_identity(self, user, token_id):
        """Accept either a token name or the conventional user!token form."""
        if "!" not in token_id:
            return user, token_id

        token_user, token_name = token_id.split("!", 1)
        if not token_user or not token_name:
            self._fail("api_token_id must use the format user@realm!token or token")
        if user and user != token_user:
            self._fail("api_user must match the user embedded in api_token_id")
        return token_user, token_name

    def validate_pve_permissions(self, api, path, role="Administrator", require_propagation=True):
        """Ensure the authenticated identity has a role's effective permissions at a path."""
        params = self.module.params
        if params.get("api_service", "PVE").upper() != "PVE":
            return

        try:
            roles = api.access.roles.get()
            permissions = api.access.permissions.get(path=path)
        except Exception:
            self._fail(
                "Unable to verify effective PVE permissions for role {0} on {1}.".format(role, path)
            )

        role_info = next(
            (item for item in roles if isinstance(item, dict) and item.get("roleid") == role),
            None,
        ) if isinstance(roles, list) else None
        if role_info is None:
            self._fail(
                "Unable to verify PVE role {0}; refusing to continue.".format(role)
            )

        role_privileges = role_info.get("privs", "")
        if isinstance(role_privileges, str):
            role_privileges = {
                privilege.strip()
                for privilege in role_privileges.split(",")
                if privilege.strip()
            }
        else:
            role_privileges = set(role_privileges or [])

        effective = permissions.get(path) if isinstance(permissions, dict) else None
        if not isinstance(effective, dict):
            self._fail(
                "Unable to verify effective PVE permissions for role {0} on {1}.".format(role, path)
            )

        missing = sorted(
            privilege
            for privilege in role_privileges
            if privilege not in effective or (require_propagation and not bool(effective[privilege]))
        )
        if missing:
            self._fail(
                "Authenticated identity lacks full {0} permissions propagated on {1}; missing: {2}.".format(
                    role, path, ", ".join(missing)
                )
            )

    def _validate_https_options(self, params):
        password = params.get("api_password")
        token_id = params.get("api_token_id")
        token_secret = params.get("api_token_secret")
        otp = params.get("api_otp")

        if bool(password) == bool(token_id):
            self._fail("Provide exactly one of api_password or api_token_id/api_token_secret for HTTPS")
        if token_id and not token_secret:
            self._fail("api_token_secret is required when api_token_id is set")
        if token_secret and not token_id:
            self._fail("api_token_id is required when api_token_secret is set")
        if token_id and otp:
            self._fail("api_otp can only be used with HTTPS password authentication")
        if params.get("ca_path") and not params["validate_certs"]:
            self._fail("ca_path requires validate_certs=true")
        if (
            params.get("ssh_config_file")
            or params.get("ssh_identity_file")
            or params.get("ssh_forward_agent")
        ):
            self._fail("OpenSSH options cannot be used with the HTTPS backend")

    def _https_options(self, params, options):
        self._validate_https_options(params)
        user = params.get("api_user")
        password = params.get("api_password")
        token_id = params.get("api_token_id")
        token_secret = params.get("api_token_secret")
        otp = params.get("api_otp")

        if token_id:
            user, token_name = self._token_identity(user, token_id)
            options.update({"token_name": token_name, "token_value": token_secret})
        else:
            options["password"] = password
            if otp:
                options["otp"] = otp

        if not user:
            self._fail("api_user is required for HTTPS password authentication or a token name without a user")

        options["user"] = user
        if params.get("ca_path") and params["validate_certs"]:
            options["verify_ssl"] = params["ca_path"]
        else:
            options["verify_ssl"] = params["validate_certs"]

    def _openssh_options(self, params, options):
        user = params.get("ssh_user")
        if not user:
            self._fail("ssh_user is required for OpenSSH connections")

        forbidden = {
            "api_password": params.get("api_password"),
            "api_token_id": params.get("api_token_id"),
            "api_token_secret": params.get("api_token_secret"),
            "api_otp": params.get("api_otp"),
            "ca_path": params.get("ca_path"),
            "validate_certs": params.get("validate_certs") is False,
        }
        configured = sorted(name for name, value in forbidden.items() if value)
        if configured:
            self._fail(
                "HTTPS authentication and certificate options cannot be used with the OpenSSH backend",
                conflicting_options=configured,
            )

        options["user"] = user
        if params.get("ssh_config_file"):
            options["config_file"] = params["ssh_config_file"]
        if params.get("ssh_identity_file"):
            options["identity_file"] = params["ssh_identity_file"]
        if params.get("ssh_forward_agent"):
            options["forward_ssh_agent"] = True

    def connection_options(self):
        """Return validated proxmoxer keyword arguments for the selected backend."""
        params = self.module.params
        if not params.get("api_host"):
            self._fail("api_host must not be empty")
        if params["api_timeout"] <= 0:
            self._fail("api_timeout must be greater than zero")
        backend = params["api_backend"]
        port_option = "api_port" if backend == "https" else "ssh_port"
        port = params.get(port_option)
        if port is not None and not 1 <= port <= 65535:
            self._fail("{0} must be between 1 and 65535".format(port_option))

        options = {
            "backend": backend,
            "service": params["api_service"],
            "timeout": params["api_timeout"],
        }
        if port is not None:
            options["port"] = port

        if backend == "https":
            self._https_options(params, options)
        elif backend == "openssh":
            self._openssh_options(params, options)
        else:
            self._fail("Unsupported api_backend", api_backend=backend)
        return options

    def get_api(self):
        """Return a cached ProxmoxAPI instance, constructing it on first use."""
        if self._api is not None:
            return self._api
        if ProxmoxAPI is None:
            self._fail(
                missing_required_lib("proxmoxer", url="https://github.com/proxmoxer/proxmoxer"),
                exception=PROXMOXER_IMPORT_ERROR,
            )

        backend = self.module.params["api_backend"]
        if backend == "https" and REQUESTS_IMPORT_ERROR:
            self._fail(missing_required_lib("requests"), exception=REQUESTS_IMPORT_ERROR)
        if backend == "openssh" and OPENSSH_WRAPPER_IMPORT_ERROR:
            self._fail(missing_required_lib("openssh_wrapper"), exception=OPENSSH_WRAPPER_IMPORT_ERROR)

        try:
            self._api = ProxmoxAPI(self.module.params["api_host"], **self.connection_options())
        except Exception as exception:
            self.fail_request("Initializing the Proxmox API connection", exception)
        return self._api

    @property
    def api(self):
        """Expose the lazy proxmoxer client as a property."""
        return self.get_api()
