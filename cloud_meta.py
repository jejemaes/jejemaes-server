#!/usr/bin/env python

import contextlib
import datetime
import json
import logging
from functools import wraps
import os
import re
import sys

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import NamedTupleCursor

HERE = os.path.dirname(os.path.realpath(__file__))

ODOO_LONGPOLLINGPORT_OFFSET = 3

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
# Tools
# ----------------------------------------------------------------------------

def slugify(value):
    name = re.sub('[^\w\s-]', '', value).strip().lower()
    return name


def domain2database(domain):
    temp_domain = domain[4:] if domain.startswith('www.') else domain
    slug_name = slugify(temp_domain)
    return slug_name

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
# Common
# ----------------------------------------------------------------------------

def account_info(name):
    service_type = account_get_service_type(name)
    data = {}
    if service_type in ['lemp', 'wordpress']:
        data = lemp_info(name)
    elif service_type == 'odoo':
        raise Exception("Not implemented yet")
    dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime) else None
    return json.dumps(data, default=dthandler)


def _account_add(domain, unix_user, unix_group, status='production', service_type='lemp', odoo_version_id=False):
    slug_name = domain2database(domain)

    with cursor() as cr:
        cr.excute("""
            INSERT INTO service_account (name, server_name, unix_user, unix_group, status, service_type)
            VALUES (%s, %s, %s, %s, %s)
        """, (domain, slug_name, unix_user, unix_group, status, service_type))
    return slug_name


def account_get_service_type(name):
    with cursor() as cr:
        cr.execute("""
            SELECT service_type
            FROM service_account
            WHERE name = %s
        """, (name,))
        data = cr.fetchall()
        if data:
            return data[0].service_type
    return None


# ----------------------------------------------------------------------------
# LEMP Methods
# ----------------------------------------------------------------------------

def lemp_add(domain, unix_user, unix_group, status='production', wordpress=False):
    service_type = 'wordpress' if wordpress else 'lemp'
    return _account_add(domain, unix_user, unix_group, status=status, service_type=service_type)


def lemp_info(name):
    with cursor() as cr:
        cr.execute("""
            SELECT name, server_name, unix_user, unix_group, service_type, status, create_date, update_date
            FROM service_account
            WHERE name = %s
        """, (name,))
        data = cr.fetchall()
        if data:
            return data[0]._asdict()
    return {}


# ----------------------------------------------------------------------------
# Odoo Business Methods
# ----------------------------------------------------------------------------

def _odoo_compute_port(branch):
    """ For branch >= 11.0, with nickname based on 'saas-XX.x' or 'XX.0', generate the port number
        on wich the version should run.
        :param branch: branch nickname (string)
        :rtype tuple of integer
    """
    version_list = re.findall(r"\d*\.\d+|\d+", branch)
    if not version_list:
        raise RuntimeError('No version can be extract from branch nickname %s to determine its port' % (branch,))
    version = float(version_list[0])
    port = int(8069 + 100 * version)
    return port, port + ODOO_LONGPOLLINGPORT_OFFSET


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


def odoo_add_version(version):
    # check if version already existing
    if version in odoo_list_branches():
        return False
    # add version and compute its ports
    port, longpolling_port = _odoo_compute_port(version)
    with cursor() as cr:
        cr.execute("INSERT INTO odoo_version(version, port, longpolling_port) VALUES (%s, %s, %s) RETURNING id", (version, port, longpolling_port))
        return cr.fetchone()[0]
    return False


def odoo_add_database(domain, version, dbname=False):
    if not dbname:
        dbname = domain2database(domain)

    with cursor() as cr:
        # extract version id
        cr.execute("""
            SELECT id AS id
            FROM odoo_version
            WHERE version = %s
        """, (version,))
        data = cr.fetchall()
        version_id = data[0].id if data else None

        # create the service entry
        cr.excute("""
            INSERT INTO service_account (name, service_name, status, service_type, odoo_version_id) VALUES (%s, %s, 'production', 'odoo', %s) RETURNING id
        """, (domain, dbname, version_id))
        service_id = int(cr.fetchone()[0])

        # create the database entry
        cr.excute("""
            INSERT INTO database (name, db_type, service_id) VALUES (%s, 'postgres', %s) RETURNING id
        """, (dbname, service_id))
    return cr.fetchone()[0]


def odoo_get_info(dbname):
    db_values = {}
    with cursor() as cr:
        cr.execute("""
            SELECT
                A.name AS service_name,
                A.status AS status,
                V.version AS version,
                D.name AS dbname,
                S.create_date AS create_date,
                S.update_date AS update_date,
                D.port AS port,
                D.longpolling_port AS longpolling_port
            FROM database D
                LEFT JOIN service_account A ON D.service_id = D.id
                LEFT JOIN odoo_version V ON A.odoo_version_id = V.id
            WHERE D.name = %s
            LIMIT 1
        """, (dbname,))
        dbinfo = cr.fetchall()[0]
        db_values = dbinfo._asdict()

    dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime) else None
    return json.dumps(db_values, default=dthandler)


def main():
    """
        Usage:
            cloud-meta info <name>
            cloud-meta odoo-get-info <dbname>
            cloud-meta odoo-get-port <branch>
            cloud-meta odoo-get-longpolling-port <branch>
            cloud-meta odoo-list-branches [-a] [-p]
            cloud-meta odoo-last-branch [-a]
            cloud-meta odoo-add-version <version>
            cloud-meta odoo-add-database <url> <version> [-d <database>]
    """
    from docopt import docopt
    import signal

    if os.getuid() != 0:  # TODO: this might not be a good practice
        sys.exit("cloud-meta must be run as root")

    signal.signal(signal.SIGINT, _sigint_handler)

    opt = docopt(main.__doc__)

    # common
    if opt['info']:
        print(account_info(opt['name']))
    elif opt['lemp-add']:
        print(lemp_add(opt['domain'], opt['unix_user'], opt['unix_group']))
    # odoo
    elif opt['odoo-get-info']:
        print(odoo_get_info(opt['<dbname>']))
    elif opt['odoo-list-branches']:
        for branch in odoo_list_branches():
            if opt['-p']:
                print('%s (%d)' % (branch, odoo_get_port(branch)))
            else:
                print(branch)
    elif opt['odoo-last-branch']:
        print(odoo_last_branch())
    elif opt['odoo-get-port']:
        print(odoo_get_port(opt['<branch>']))
    elif opt['odoo-get-longpolling-port']:
        print(odoo_get_longpolling_port(opt['<branch>']))
    elif opt['odoo-add-version']:
        print(odoo_add_version(opt['<version>']))
    elif opt['odoo-add-database']:
        print(odoo_add_database(opt['<url>'], opt['<version>'], opt['<database>']))

if __name__ == '__main__':
    main()
