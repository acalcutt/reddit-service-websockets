import signal

import gevent
import manhole

# Prefer the new `baseplate` API when available (with Baseplate class).
# Fall back to the older top-level `baseplate` layout for compatibility
# with older installs that still provide `error_reporter_from_config`.
try:
    from baseplate import Baseplate
    from baseplate.lib import config as config
    from baseplate.lib.secrets import secrets_store_from_config
    from baseplate.lib.metrics import metrics_client_from_config
    _HAS_BASEPLATE_CLASS = True
except Exception:
    from baseplate import (
        config,
        metrics_client_from_config,
        error_reporter_from_config,
    )
    from baseplate.lib.secrets import secrets_store_from_config
    Baseplate = None
    _HAS_BASEPLATE_CLASS = False

from .dispatcher import MessageDispatcher
from .socketserver import SocketServer
from .source import MessageSource


manhole.install(oneshot_on='USR1')


CONFIG_SPEC = {
    "amqp": {
        "endpoint": config.Endpoint,
        "vhost": config.String,
        "username": config.String,
        "password": config.String,

        "exchange": {
            "broadcast": config.String,
            "status": config.String,
        },

        "send_status_messages": config.Boolean,
    },

    "web": {
        "ping_interval": config.Integer,
        "admin_auth": config.String,
        "conn_shed_rate": config.Integer,
    },
}


def make_app(raw_config):
    cfg = config.parse_config(raw_config, CONFIG_SPEC)

    metrics_client = metrics_client_from_config(raw_config)

    # Configure error reporting / observability using the modern Baseplate
    # `configure_observers()` when available. For older Baseplate versions
    # that still expose `error_reporter_from_config`, fall back to that API.
    error_reporter = None
    if _HAS_BASEPLATE_CLASS and Baseplate is not None:
        bp = Baseplate(raw_config)
        bp.configure_observers()
        # Try common locations for the configured error reporter.
        error_reporter = getattr(bp, "error_reporter", None)
        if error_reporter is None:
            observers = getattr(bp, "observers", None)
            if isinstance(observers, dict):
                error_reporter = observers.get("error_reporter")
            elif isinstance(observers, list):
                for o in observers:
                    if getattr(o, "report_exception", None) is not None:
                        error_reporter = o
                        break
        # fallback to None if still not found
    else:
        # older API
        error_reporter = error_reporter_from_config(raw_config, __name__)

    secrets = secrets_store_from_config(raw_config)

    dispatcher = MessageDispatcher(metrics=metrics_client)

    source = MessageSource(
        config=cfg.amqp,
    )

    app = SocketServer(
        metrics=metrics_client,
        dispatcher=dispatcher,
        secrets=secrets,
        error_reporter=error_reporter,
        ping_interval=cfg.web.ping_interval,
        admin_auth=cfg.web.admin_auth,
        conn_shed_rate=cfg.web.conn_shed_rate,
    )

    # register SIGUSR2 to trigger app quiescing,
    #  useful if app processes are behind
    #  a process manager like einhorn.
    def _handle_quiesce_signal(_, frame):
        app._quiesce({}, bypass_auth=True)

    signal.signal(signal.SIGUSR2, _handle_quiesce_signal)
    signal.siginterrupt(signal.SIGUSR2, False)

    source.message_handler = dispatcher.on_message_received
    app.status_publisher = source.send_message

    gevent.spawn(source.pump_messages)

    return app
