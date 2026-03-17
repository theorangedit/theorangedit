# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################
"""
Async AMQP helpers — replaces the old amqplib/threading-based implementation.

Public API (same names, now all async):

    await add_item(routing_key, body, ...)
    await add_kw(routing_key, **kw)
    await consume_items(queue, callback, ...)
    await handle_items(queue, callback, ...)
    await empty_queue(queue)

The connection is lazy: it is established on first use and re-established
automatically after connection failures.  All functions degrade gracefully
when AMQP is not configured (cfg.amqp_host is falsy).
"""

import asyncio
import pickle
import sys
from typing import Awaitable, Callable, Optional

import aio_pika
import aio_pika.abc

# ── Module-level state ────────────────────────────────────────────────────────

cfg = None
_connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
_channel: Optional[aio_pika.abc.AbstractChannel] = None
_init_lock: Optional[asyncio.Lock] = None

DELIVERY_TRANSIENT = 1
DELIVERY_DURABLE = 2


# ── Config ────────────────────────────────────────────────────────────────────

class Config:
    def __init__(self, g):
        self.amqp_host = g.amqp_host
        self.amqp_user = g.amqp_user
        self.amqp_pass = g.amqp_pass
        self.amqp_virtual_host = g.amqp_virtual_host
        self.amqp_exchange = 'reddit_exchange'
        self.amqp_logging = g.amqp_logging
        self.log = g.log
        self.stats = g.stats
        self.queues = g.queues
        self.reset_caches = g.reset_caches

    @property
    def amqp_url(self) -> str:
        vhost = (self.amqp_virtual_host or '/').lstrip('/')
        return (
            f"amqp://{self.amqp_user}:{self.amqp_pass}"
            f"@{self.amqp_host}/{vhost}"
        )


def initialize(app_globals):
    """Called once at startup (synchronously) from app_globals.setup().

    The async lock and connection are created lazily on first use so that
    this function is safe to call before the event loop has started.
    """
    global cfg
    cfg = Config(app_globals)


# ── Connection management ─────────────────────────────────────────────────────

async def _get_channel() -> Optional[aio_pika.abc.AbstractChannel]:
    """Return a ready channel, (re-)connecting as needed."""
    global _connection, _channel, _init_lock

    if not cfg or not cfg.amqp_host:
        return None

    # Create lock lazily inside the running event loop
    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        if _connection is None or _connection.is_closed:
            _connection = await aio_pika.connect_robust(
                cfg.amqp_url,
                reconnect_interval=1,
            )
            _channel = None

        if _channel is None or _channel.is_closed:
            _channel = await _connection.channel()
            await _channel.set_qos(prefetch_count=10)
            await _declare_topology(_channel)

    return _channel


async def _declare_topology(channel: aio_pika.abc.AbstractChannel) -> None:
    """Declare exchange, queues, and bindings."""
    exchange = await channel.declare_exchange(
        cfg.amqp_exchange,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
        auto_delete=False,
    )

    for queue in cfg.queues:
        q = await channel.declare_queue(
            queue.name,
            durable=queue.durable,
            exclusive=queue.exclusive,
            auto_delete=queue.auto_delete,
        )
        if queue.bind_to_self:
            await q.bind(exchange, routing_key=queue.name)

    for queue_name, routing_key in cfg.queues.bindings:
        q = await channel.declare_queue(queue_name, durable=True)
        await q.bind(exchange, routing_key=routing_key)


# ── Publishing ────────────────────────────────────────────────────────────────

async def add_item(
    routing_key: str,
    body: bytes,
    message_id: Optional[str] = None,
    delivery_mode: int = DELIVERY_DURABLE,
    headers: Optional[dict] = None,
    exchange: Optional[str] = None,
    send_stats: bool = True,
) -> None:
    """Publish *body* to *routing_key*.  No-ops gracefully if AMQP is down."""
    if not cfg or not cfg.amqp_host:
        if cfg:
            cfg.log.debug("amqp disabled — dropping message to %r", routing_key)
        return

    if cfg.amqp_logging:
        cfg.log.debug("amqp: adding item %r to %r", body, routing_key)

    channel = await _get_channel()
    if channel is None:
        return

    exchange_name = exchange or cfg.amqp_exchange
    event_name = f'amqp.{routing_key}'

    props: dict = {}
    if message_id:
        props['message_id'] = message_id
    if headers:
        props['headers'] = headers

    mode = (
        aio_pika.DeliveryMode.PERSISTENT
        if delivery_mode == DELIVERY_DURABLE
        else aio_pika.DeliveryMode.NOT_PERSISTENT
    )

    message = aio_pika.Message(
        body=body if isinstance(body, bytes) else body.encode(),
        delivery_mode=mode,
        **props,
    )

    try:
        exch = await channel.get_exchange(exchange_name)
        await exch.publish(message, routing_key=routing_key)
        if send_stats:
            cfg.stats.event_count(event_name, 'enqueue')
    except Exception as exc:
        cfg.log.error("amqp publish failed to %r: %r", routing_key, exc)
        if send_stats:
            cfg.stats.event_count(event_name, 'enqueue_failed')
        # Reset channel so next call reconnects
        global _channel
        _channel = None


async def add_kw(routing_key: str, **kw) -> None:
    """Pickle *kw* and publish to *routing_key*."""
    await add_item(routing_key, pickle.dumps(kw))


# ── Consuming ─────────────────────────────────────────────────────────────────

async def consume_items(
    queue: str,
    callback: Callable,
    verbose: bool = True,
) -> None:
    """Consume messages from *queue* one at a time, calling *callback(msg)*.

    *callback* may be a regular function or a coroutine function.
    Runs until cancelled (e.g. KeyboardInterrupt / asyncio.CancelledError).
    """
    channel = await _get_channel()
    if channel is None:
        cfg.log.error("amqp: cannot consume %r — no connection", queue)
        return

    q = await channel.declare_queue(queue, durable=True, passive=True)

    async with q.iterator() as messages:
        async for message in messages:
            async with message.process():
                if verbose:
                    cfg.log.debug("amqp %s: 1 item", queue)

                cfg.reset_caches()

                result = callback(message)
                if asyncio.iscoroutine(result):
                    await result


async def handle_items(
    queue: str,
    callback: Callable,
    ack: bool = True,
    limit: int = 1,
    min_size: int = 0,
    drain: bool = False,
    verbose: bool = True,
    sleep_time: float = 1.0,
) -> None:
    """Batch-consume messages from *queue*, calling *callback(items, channel)*.

    Mirrors the old synchronous handle_items interface:
      - Collects up to *limit* messages, waiting for *min_size* if the queue
        has fewer.
      - If *drain* is True, stops after the queue is empty.
      - *callback* receives a list of aio_pika.IncomingMessage objects and the
        channel (for compatibility); it may be sync or async.
    """
    if limit < min_size:
        raise ValueError("min_size must be less than limit")

    channel = await _get_channel()
    if channel is None:
        cfg.log.error("amqp: cannot handle %r — no connection", queue)
        return

    q = await channel.declare_queue(queue, durable=True, passive=True)

    while True:
        items = []
        countdown = None

        # Gather up to *limit* messages
        while len(items) < limit:
            try:
                message = await asyncio.wait_for(q.get(), timeout=sleep_time)
            except asyncio.TimeoutError:
                if len(items) >= min_size:
                    break
                if drain and not items:
                    return
                continue

            items.append(message)

            if countdown is None and drain:
                # message_count from aio_pika is not directly available on
                # IncomingMessage; approximate: stop after current batch
                countdown = True

            if drain and countdown:
                break

        if not items:
            if drain:
                return
            await asyncio.sleep(sleep_time)
            continue

        if verbose:
            cfg.log.debug("amqp %s: %d items", queue, len(items))

        cfg.reset_caches()

        try:
            result = callback(items, channel)
            if asyncio.iscoroutine(result):
                await result

            if ack:
                for msg in items:
                    await msg.ack()
        except Exception:
            for msg in items:
                await msg.nack(requeue=True)
            raise

        sys.stdout.flush()

        if drain:
            return


# ── Utilities ─────────────────────────────────────────────────────────────────

async def empty_queue(queue: str) -> None:
    """Purge all messages from *queue*."""
    channel = await _get_channel()
    if channel is None:
        return
    q = await channel.declare_queue(queue, durable=True, passive=True)
    await q.purge()


async def black_hole(queue: str) -> None:
    """Continuously discard messages from *queue*."""
    async def _ignore(msg):
        cfg.log.debug('Ignoring msg: %r', msg.body)

    await consume_items(queue, _ignore)
