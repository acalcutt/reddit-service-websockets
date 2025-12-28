import json
import logging
import socket

import gevent
import pika
import pika.exceptions


LOG = logging.getLogger(__name__)


class MessageSource(object):
    """An AMQP based message source.

    This will monitor a fanout exchange on AMQP and signal on receipt of any
    messages, as well as allow messages to be sent to a topic exchange on
    status changes within the system.

    """

    def __init__(self, config):
        assert config.endpoint.family == socket.AF_INET

        self.host = config.endpoint.address.host
        self.port = config.endpoint.address.port
        self.vhost = config.vhost
        self.username = config.username
        self.password = config.password
        self.broadcast_exchange = config.exchange.broadcast
        self.status_exchange = config.exchange.status
        self.send_status_messages = config.send_status_messages
        self.message_handler = None

        self.channel = None
        self.publish_channel = None

    def _connect(self):
        credentials = pika.PlainCredentials(self.username, self.password)
        params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=credentials,
        )

        # Use a blocking connection and drive it from gevent in pump_messages
        self.connection = pika.BlockingConnection(params)

        # Publisher channel (use a dedicated channel for publishing)
        self.publish_channel = self.connection.channel()

        # Consumer channel
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=self.broadcast_exchange, exchange_type="fanout")
        q = self.channel.queue_declare(queue="", exclusive=True, auto_delete=True)
        queue_name = q.method.queue
        self.channel.queue_bind(queue=queue_name, exchange=self.broadcast_exchange)

        # Register a consumer that calls into the existing message handler
        # NOTE: We rely on pump_messages to call process_data_events periodically.
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=self._on_pika_message, auto_ack=False)

    @property
    def connected(self):
        return bool(self.connection)

    def _on_queue_created(self, queue_name, *ignored):
        # This method is a haigha-style callback and is no longer used with pika.
        pass

    def _on_pika_message(self, ch, method, properties, body):
        try:
            if self.message_handler:
                decoded = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body
                namespace = method.routing_key
                self.message_handler(namespace=namespace, message=decoded)
        finally:
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                LOG.exception("failed to ack message")

    def _on_message(self, message):
        if self.message_handler:
            decoded = message.body.decode("utf-8")
            namespace = message.delivery_info["routing_key"]
            self.message_handler(namespace=namespace, message=decoded)

    def _on_close(self):
        LOG.warning("lost connection")
        self.connection = None
        self.channel = None
        self.publisher = None

    def send_message(self, key, payload):
        """Publish a status update to the status exchange."""
        if self.send_status_messages and self.publisher:
            serialized_payload = json.dumps(payload).encode("utf-8")
            try:
                self.publish_channel.basic_publish(
                    exchange=self.status_exchange,
                    routing_key=key,
                    body=serialized_payload,
                )
            except Exception:
                LOG.exception("failed to publish message")

    def pump_messages(self):
        """Maintain a connection to the broker and handle incoming frames.

        This will never return, so it should be run from a separate greenlet.

        """
        while True:
            try:
                self._connect()
                LOG.info("connected")

                while self.connected:
                    LOG.debug("pumping")
                    try:
                        # Process network events for the blocking connection
                        self.connection.process_data_events(time_limit=1)
                    except pika.exceptions.AMQPError as exc:
                        LOG.warning("connection processing failed: %s", exc)
                        break
                    gevent.sleep()
            except (socket.error, pika.exceptions.AMQPConnectionError) as exception:
                LOG.warning("connection failed: %s", exception)
                gevent.sleep(1)
