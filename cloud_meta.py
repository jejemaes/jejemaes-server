#!/usr/bin/env python

import contextlib
import datetime
import json
import logging
from functools import wraps
import os
import sys

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import NamedTupleCursor

HERE = os.path.dirname(os.path.realpath(__file__))

_logger = logging.getLogger(__name__)
_log_fmt = logging.Formatter('[%(asctime)s] %(levelname)s pid=%(process)d db=meta %(message)s')
_log_hndl = logging.FileHandler(os.path.expanduser('%s/log/meta.log' % (HERE,)))
_log_hndl.setFormatter(_log_fmt)
_logger.addHandler(_log_hndl)
_logger.setLevel(logging.INFO)


# ----------------------------------------------------------------------------
# signal handling
# ----------------------------------------------------------------------------

_STOPPED = False
_STOPPABLE = False


def stopped():
    return _STOPPED


def graceful_stop(f):
    @wraps(f)
    def w(*a, **kw):
        global _STOPPABLE
        _STOPPABLE = True
        return f(*a, **kw)
    return w


def check_stop(it):
    for i in it:
        if _STOPPED:
            break
        yield i


def _sigint_handler(s, f):
    global _STOPPED
    if _STOPPABLE and not _STOPPED:
        _logger.info('CTRL-C catched. Will Stop after next operation')
        sys.stdout.flush()
        _STOPPED = True
    else:
        if _STOPPABLE:
            _logger.info('CTRL-C catched. Stop immediatly')
            sys.stdout.flush()
        raise KeyboardInterrupt()

# ----------------------------------------------------------------------------
# Database access
# ----------------------------------------------------------------------------

_METAPOOL = {}
MAX_CONN = 32
META = 'meta'

@contextlib.contextmanager
def cursor(commit=True):
    global _METAPOOL
    dbname = META
    try:
        pool = _METAPOOL[dbname]
        cnx = pool.getconn()
    except KeyError, AttributeError:
        dsn = 'dbname=%s' % dbname
        pool = ThreadedConnectionPool(0, MAX_CONN, dsn)
        cnx = pool.getconn()

        # save the connection pool
        _METAPOOL[dbname] = pool

    cr = cnx.cursor(cursor_factory=NamedTupleCursor)

    try:
        to_commit = False
        yield cr
        to_commit = commit
    finally:
        if to_commit:
            cnx.commit()
        else:
            cnx.rollback()
        try:
            cr.close()
        finally:
            pool.putconn(cnx)

# ----------------------------------------------------------------------------
# Odoo Business Methods
# ----------------------------------------------------------------------------


def odoo_get_port(branch):
    return _odoo_get_port(branch, 'port')


def odoo_get_longpolling_port(branch):
    return _odoo_get_port(branch, 'longpolling_port')


def _odoo_get_port(branch, column_port):
    port = None
    with cursor() as cr:
        cr.execute("""
            SELECT %s AS port
            FROM odoo_version
            WHERE version = %%s
        """ % (column_port,), (branch,))
        data = cr.fetchall()
        port = data[0].port if data else None
    if not port:
        raise RuntimeError('No %s for branch %s found' % (column_port, branch,))
    return port


def odoo_list_branches():
    version_list = []
    with cursor() as cr:
        cr.execute("""
            SELECT version
            FROM odoo_version
            ORDER BY id DESC
        """)
        version_list = [v.version for v in cr.fetchall()]
    return version_list


def odoo_last_branch():
    version_list = odoo_list_branches()
    if version_list:
        return version_list[0]
    raise RuntimeError('No last odoo branch found !')


def odoo_add_version(version, port, longpolling_port):
    port = int(port)
    if longpolling_port:
        longpolling_port = int(longpolling_port)
    else:
        longpolling_port = port + 3
    with cursor() as cr:
        cr.execute("INSERT INTO odoo_version(version, port, longpolling_port) VALUES (%s, %s, %s) RETURNING id", (version, port, longpolling_port))
        return cr.fetchone()[0]
    return False


def main():
    """
        Usage:
            cloud-meta odoo-get-port <branch>
            cloud-meta odoo-get-longpolling-port <branch>
            cloud-meta odoo-list-branches [-a] [-p]
            cloud-meta odoo-last-branch [-a]
            cloud-meta odoo-add-version <version> <port> [<longpolling_port>]
    """
    from docopt import docopt
    import signal

    if os.getuid() != 0:  # TODO: this might not be a good practice
        sys.exit("cloud-meta must be run as root")

    signal.signal(signal.SIGINT, _sigint_handler)

    opt = docopt(main.__doc__)

    if opt['odoo-list-branches']:
        for branch in odoo_list_branches():
            if opt['-p']:
                print('%s (%d)' % (branch, get_port(branch)))
            else:
                print(branch)
    elif opt['odoo-last-branch']:
        print(odoo__last_branch())
    elif opt['odoo-get-port']:
        print(odoo_get_port(opt['<branch>']))
    elif opt['odoo-get-longpolling-port']:
        print(odoo_get_longpolling_port(opt['<branch>']))
    elif opt['odoo-add-version']:
        print(odoo_add_version(opt['<version>'], opt['<port>'], opt['<longpolling_port>']))

if __name__ == '__main__':
    main()
