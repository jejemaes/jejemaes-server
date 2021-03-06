#!/usr/bin/env python
"""#
# to run the script
#
#   fab -H root@1.1.1.1.1 setup
#
#   fab -H root@1.1.1.1.1 my_task:param1
#
# for test
#   env SAAS_USER=accounts fab -H root@accounts.test.openerp.com update:saas-1
#
"""
import ConfigParser
import io
import json
import os
import re

from fabric.api import task, env, run, cd, sudo, put, hide, hosts, local, get, execute
from fabric.colors import red, yellow, green, blue, white
from fabric.utils import abort, puts, fastprint, warn
from fabric.context_managers import warn_only, settings, shell_env
from fabric.contrib.files import exists, upload_template

import fabtools
import fabtools.require

from functools import wraps


HERE = os.path.dirname(os.path.realpath(__file__))
LOCAL_DIR_RESOURCES = HERE + '/resources/'

DIR_SCRIPT = '/root/cloud/'
SERV_DIR_CLOUD_FILES = '/root/cloud/setup/cloud_files'
SERV_DIR_CLOUD_SETUP = '/root/cloud/setup'
SERV_DIR_RESOURCES = '/root/cloud/setup/resources'
SERV_DIR_FILES = '/root/cloud/setup/cloud_files'
CONFIG = {}

ODOO_USER = os.environ.get('ODOO_USER', 'odoo')
if not re.match(r'^[a-z_]+$', ODOO_USER):
    abort('%r is not alphabetical' % (ODOO_USER,))

ODOO_DIR_HOME = '/home/%s' % ODOO_USER
ODOO_DIR_SRC = ODOO_DIR_HOME + '/src'
ODOO_DEFAULT_VERSION = '11.0'
# those github repo should be versionned as the odoo community repo (same branch nickname)
ODOO_REPO_DIR_MAP = {
    'odoo': 'https://github.com/odoo/odoo.git',
    'jejemaes': 'https://github.com/jejemaes/odoo-custom-addons.git',
}

# ----------------------------------------------------------
# Script Tools
# ----------------------------------------------------------


def as_(user):
    def deco(fun):
        @wraps(fun)
        def wrapper(*args, **kwargs):
            current_user = env.user
            if current_user != user:
                warn('force using user ' + user)
            env.user = user
            try:
                return fun(*args, **kwargs)
            finally:
                env.user = current_user
        return wrapper
    return deco


def _auto_load_config_file():
    config_values = {}
    file_path = "config.ini"
    if os.path.exists(file_path):
        # Load the configuration file
        with open(file_path) as f:
            sample_config = f.read()
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.readfp(io.BytesIO(sample_config))

        for section in config.sections():
            for option in config.options(section):
                config_values['%s_%s' % (section, option)] = config.get(section, option)
    return config_values

CONFIG = _auto_load_config_file()


def _get_config(section_prefix):
    result = {}
    for option in CONFIG:
        if option.startswith(section_prefix):
            result[option] = CONFIG.get(option)
    return result


def has_systemd():
    with hide('output', 'running', 'warnings'):
        with settings(warn_only=True):
            res = run('command -v systemctl')
            return res.return_code == 0


def _validate_domain(domain):
    regex = re.compile(
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, domain) is not None


def slugify(value):
    name = re.sub('[^\w\s-]', '', value).strip().lower()
    return name


def domain2database(domain):
    temp_domain = domain[4:] if domain.startswith('www.') else domain
    slug_name = slugify(temp_domain)
    return slug_name


# fabtools issue: https://github.com/fabtools/fabtools/issues/4
# checking the existance of a user will always return True as a warning
# "/bin/bash: /root/.bash_profile: Permission denied\r\ncould not
# change directory to "/root" is returned, and is evaluated to True.
# This method patch it.
def pg_user_exists(name):
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = fabtools.postgres._run_as_pg('''psql -t -A -c "SELECT count(*) FROM pg_user WHERE usename='%(name)s';"''' % locals())
    return '1' in res

# ----------------------------------------------------------
# Git Utils
# ----------------------------------------------------------


def git_clone(path, gh_url, directory, branch_name=False):
    """ Clone a github repo into a given directory
        :param path: absotute path of the directory in which create the new repo
        :param gh_url: HTTPS github url of the repo to clone (e.i.: https://github.com/jejemaes/jejemaes-server.git)
        :param directory: name of directory that will contain the code
        :param branch_name: branche name (in github repo). If given, this will fecth only this branch. Otherwise, only the
            primary of the github repo will be fetched.
    """
    with cd(path):
        if not fabtools.files.is_dir(directory):
            if branch_name:
                run('git clone -q --branch {0} --single-branch {1} {2}'.format(branch_name, gh_url, directory))
            else:
                run('git clone -q --single-branch {0} {1}'.format(gh_url, directory))
        return True
    return False


def git_update_directory(path):
    """ Update code from git for the given git directory
        :param path: absolute path of the git directory to update
    """
    if not fabtools.files.is_dir(path):
        puts(red('Setup directory {0} not found'.format(path)))
        return

    puts(blue('Update setup directory {0}'.format(path)))
    with cd(path):
        sudo('git fetch --quiet --prune')
        sudo('git rebase --quiet --autostash')
        with hide('status', 'commands'):
            no_conflicts = sudo('git diff --diff-filter=U --no-patch --exit-code').succeeded
    puts(blue('Update of cloud scripts done !'))
    return no_conflicts


# ----------------------------------------------------------
# Deployment / Setup for Odoo and LEMP server
# ----------------------------------------------------------

@task
@as_('root')
def deploy(server=False):
    if not server:
        _setup_common_packages()

    _setup_server_scripts()

    # Odoo Server Deploy
    if not server or server == 'odoo':
        _setup_odoo_packages()
        _setup_odoo_user()
        run('geoipupdate')
    # LEMP Server Deploy
    if not server or server == 'lemp':
        _setup_lemp_server()

    _setup_rsync_files(server)

    if not server:
        fabtools.require.service.stopped('postgresql')
        _setup_postgres()
        fabtools.require.service.restarted('postgresql')

    setup_metabase()


def _setup_common_packages():
    """ Method to install common packages """
    debs = """
debconf-utils
git
htop
jq
nginx
python-pip
postgresql
postgresql-contrib
rsync
vim
""".split()
    fabtools.deb.update_index()
    run("apt-get upgrade -y --force-yes")
    fabtools.deb.install(debs, options=['--force-yes', '--ignore-missing'])

    python_pip = """
docopt
fabric
fabtools
mako
sh
suds
""".split()
    fabtools.python.install(python_pip, upgrade=True)


def _setup_server_scripts():
    """ Checkout the scripts and setup the /root/src directory """
    # checkout or pull
    sudo('mkdir -p ' + DIR_SCRIPT)
    with cd(DIR_SCRIPT):
        if not fabtools.files.is_dir('setup'):
            sudo('git clone https://github.com/jejemaes/jejemaes-server.git setup')
        else:
            git_update_directory(DIR_SCRIPT + 'setup')


def _setup_rsync_files(server=False):
    """ Synchronize files from the setup repo to the real server configuration, in order to set services, ... as it should be. """
    # nginx config
    sudo('rsync -rtlE %s/etc/nginx/nginx.conf /etc/nginx/nginx.conf' % (SERV_DIR_CLOUD_FILES,))
    # postgres config
    sudo("find /etc/postgresql -name 'postgresql.local.conf' -type l -delete")
    sudo("find /etc/postgresql -name 'main' -type d -exec touch '{}/postgresql.local.conf' ';' -exec chown postgres:postgres '{}/postgresql.local.conf' ';'")
    sudo('rsync -rtlE %s/etc/postgresql /etc/postgresql' % (SERV_DIR_CLOUD_FILES,))
    # make cloud meta tool executable
    sudo("mkdir -p %s/log" % (SERV_DIR_CLOUD_SETUP,))
    sudo("chmod 775 %s/cloud-meta" % (SERV_DIR_CLOUD_SETUP,))

    if not server or server == 'odoo':
        run('rsync -rtlE %s/odoo/ %s' % (SERV_DIR_CLOUD_FILES, ODOO_DIR_HOME))
        sudo("chown -R {0}:{0} {1}/bin".format(ODOO_USER, ODOO_DIR_HOME))

        run('rsync -rtlE %s/etc/sudoers.d/ /etc/sudoers.d/' % (SERV_DIR_CLOUD_FILES,))
        run('chmod 440 /etc/sudoers.d/*')


def _setup_postgres(version='9.5'):
    """ Setup postgres databse user and root and odoo roles """
    datadir = '/home/postgres/%s/main' % version
    if not fabtools.files.is_dir(datadir):
        fabtools.require.directory('/home/postgres/%s/main' % version)
        run('chown -R postgres:postgres /home/postgres')
        sudo('/usr/lib/postgresql/%s/bin/initdb --locale=en_US.UTF-8 --lc-collate=C %s' % (version, datadir), user='postgres')
    fabtools.service.start('postgresql')

    if not pg_user_exists('root'):
        fabtools.postgres.create_user('root', 'root', superuser=True)
    if not pg_user_exists('odoo'):
        fabtools.postgres.create_user('odoo', 'odoo', superuser=True)
        sudo('''psql -tAq -d postgres -c ALTER USER odoo CREATEDB;"''', user='postgres')


@task
@as_('root')
def setup_metabase():
    """ Create or update schema of `meta` database. Only root should access it since this is the cloud user. """
    META = 'meta'
    with settings(sudo_user=env.user):
        if not fabtools.postgres.database_exists(META):
            fabtools.postgres.create_database(META, owner='root')

    with shell_env(PGOPTIONS='--client-min-messages=warning'):
        sudo('psql -Xq -d {0} -f {1}/metabase.sql'.format(META, SERV_DIR_RESOURCES))


@as_('root')
def _setup_odoo_packages():
    """ Install/Update debian and python packages needed for Odoo Server """
    codename = sudo('lsb_release -cs').strip()
    uninstall = """mlocate xinetd locate wkhtmltopdf whoopsie""".split()
    # local packages repo
    sio = io.BytesIO(b"deb http://nightly.openerp.com/deb/%s ./" % codename)
    put(sio, '/etc/apt/sources.list.d/odoo.list')

    sio = io.BytesIO(b"Package: nginx\nPin: origin nightly.openerp.com\nPin-Priority: 1001")
    put(sio, '/etc/apt/preferences.d/odoo')

    run('add-apt-repository -y ppa:maxmind/ppa')    # for geoipupdate

    base_debs = """
curl
fabric
file
geoipupdate
git
graphviz
htop
jq
less
libdbd-pg-perl
libev-dev
libevent-dev
libfreetype6-dev
libjpeg8-dev
libpq-dev
libsasl2-dev
libtiff-dev
libwww-perl
libxml2-dev
libxslt1-dev
lsb-release
lsof
make
mosh
ncdu
npm
p7zip-full
pg-activity
rsync
sudo
tree
unzip
uptimed
vim
wkhtmltox
zip
""".split()
    fabtools.deb.uninstall(uninstall, purge=True, options=['--quiet'])
    fabtools.deb.update_index()
    run("apt-get upgrade -y --force-yes")

    p3_debs = """
        python3-dev
        python3-babel
        python3-dateutil
        python3-decorator
        python3-docopt
        python3-docutils
        python3-feedparser
        python3-geoip
        python3-gevent
        python3-html2text
        python3-jinja2
        python3-lxml
        python3-mako
        python3-markdown
        python3-matplotlib
        python3-mock
        python3-ofxparse
        python3-openid
        python3-passlib
        python3-pil
        python3-pip
        python3-psutil
        python3-psycopg2
        python3-pydot
        python3-pyparsing
        python3-pypdf2
        python3-reportlab
        python3-requests
        python3-setproctitle
        python3-simplejson
        python3-tz
        python3-unittest2
        python3-vatnumber
        python3-werkzeug
        python3-xlrd
        python3-xlsxwriter
        python3-yaml
    """.split()

    p3_pips = """
        fabtools
        geoip2
        num2words==0.5.4
        phonenumbers
        psycogreen
        python-slugify
        suds-jurko
        vobject
        xlwt
    """.split()

    debs = base_debs + p3_debs
    fabtools.deb.install(debs, options=['--force-yes', '--ignore-missing'])

    # NOTE libevent-dev is required by gevent. /!\ version 1.0 of gevent will require libev-dev (and cython)
    # run('pip install cython -e git://github.com/surfly/gevent.git@1.0rc2#egg=gevent')

    # fabtools.python.install(python_pip, upgrade=False)
    run("pip3 install -q {}".format(' '.join(p3_pips)))

    # Nodejs
    run("ln -sf /usr/bin/nodejs /usr/bin/node")
    run("npm install -g less less-plugin-clean-css")


def _setup_odoo_user():
    if not fabtools.user.exists(ODOO_USER):
        if ODOO_USER != 'odoo':
            abort('user %r does not exists' % ODOO_USER)
            return
        fabtools.user.create('odoo', create_home=True, shell='/bin/bash')
    sudo('mkdir -p {0}/log'.format(ODOO_DIR_HOME))
    sudo('mkdir -p {0}/src'.format(ODOO_DIR_HOME))
    sudo('mkdir -p {0}/bin'.format(ODOO_DIR_HOME))

    sudo("chown -R {0}:{0} {1}/log".format(ODOO_USER, ODOO_DIR_HOME))
    sudo("chown -R {0}:{0} {1}/src".format(ODOO_USER, ODOO_DIR_HOME))
    sudo("chown -R {0}:{0} {1}/bin".format(ODOO_USER, ODOO_DIR_HOME))


@task
def setup_odoo_services():  #TODO JEM: not sure this is usefull
    _setup_rsync_files('odoo')
    if not fabtools.systemd.is_running('nginx'):
        fabtools.systemd.start('nginx')
    fabtools.systemd.enable('nginx')

# ----------------------------------------------------------
# LEMP server
# ----------------------------------------------------------

@as_('root')
def _setup_lemp_server():
    with cd('/root/cloud/setup'):
        sudo('./cloud-setup lemp setup -v')


@task
@as_('root')
def update_lemp_server():
    with cd('/root/cloud/setup'):
        sudo('./cloud-setup lemp update -v')


#TODO: define default env with mysql root credentials

@task
@as_('root')
def lemp_create_account(domain, user, password):
    group = user
    home_dir = '/home/%s' % (user,)

    # create unix group
    if not fabtools.group.exists(group):
        fabtools.group.create(group)

    # create unix user
    if not fabtools.user.exists(user):
        fabtools.user.create(user, group=group, home=home_dir, shell='/bin/bash')

    # create php fpm and nginx files, and restart services
    with cd('/root/cloud/setup'):
        sudo('./cloud-setup lemp newsite -d {dns} -u {user} -g {group} -v'.format(dns=domain, user=user, group=user))
    fabtools.service.restart('php7.0-fpm')
    fabtools.service.restart('nginx')

    # create mysql user and database
    if not fabtools.mysql.user_exists(user):
        fabtools.mysql.create_user(user, password)

    if not fabtools.mysql.database_exists(user):
        fabtools.mysql.create_database(user, owner=user)

    # FTP SQL entries
    unix_group_id = fabtools.utils.run_as_root("id -g %s" % (user,))
    unix_user_id = fabtools.utils.run_as_root("id -u %s" % (user,))

    query = """INSERT IGNORE INTO meta.ftpgroup (groupname, gid, members) VALUES ("%s", %s, "%s");""" % (user, unix_group_id, user)
    puts(fabtools.mysql.query(query))
    query = """INSERT IGNORE INTO meta.ftpuser (userid, passwd, uid, gid, homedir, shell, count, accessed, modified) VALUES ("%s", "%s", %s, %s, "%s", "/sbin/nologin", 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);""" % (user, password, unix_user_id, unix_group_id, home_dir)
    puts(fabtools.mysql.query(query))

# ----------------------------------------------------------
# Odoo Server
# ----------------------------------------------------------

@task
def odoo_checkout(branch_nick):
    """ Odoo: deploy (fetch sources, create service, ....) or update code base of given branch (fetch sources, restart service, ....) """
    _odoo_fetch_sources(branch_nick)

    if not _odoo_is_service_running(branch_nick):  # then create it !
        _odoo_sync_filestore()
        sudo('{0}/cloud-meta odoo-add-version {1}'.format(SERV_DIR_CLOUD_SETUP, branch_nick))
        _odoo_create_initd(branch_nick)
    else:  # simply restart service after source code checkout
        _odoo_service_action(branch_nick, 'restart')


def _odoo_fetch_sources(branch_nick):
    """ Fetch source in src/<version> or update sources """
    for directory, repo_url in ODOO_REPO_DIR_MAP.items():
        current_path = ODOO_DIR_SRC + '/' + directory + '/'
        if fabtools.files.is_dir(current_path + branch_nick):
            git_update_directory(current_path + branch_nick)
        else:
            sudo('mkdir -p {0}'.format(current_path))
            result = git_clone(current_path, repo_url, branch_nick, branch_nick)
            if result:
                puts(blue('Odoo %s sources fetched !' % (branch_nick,)))
            else:
                puts(red('Error when fetching Odoo %s sources !' % (branch_nick,)))
        run("chown -R {0}:{0} {1}".format(ODOO_USER, current_path))


def _odoo_sync_filestore():
    # create a filestore directory and symlink from ~/.local to /home/odoo : one filestore per database
    sudo('mkdir -p {0}/filestore'.format(ODOO_DIR_HOME))
    # resymlink
    product = 'Odoo'  # hardcoded (was 'OpenERP' in 8.0)
    sudo('mkdir -p {0}/.local/share/{1}/sessions'.format(ODOO_DIR_HOME, product))
    sudo('ln -sfT {0}/filestore {0}/.local/share/{1}/filestore'.format(ODOO_DIR_HOME, product))


def _odoo_branch2service(branch):
    """returns a tuple (service_name, service_path)"""
    service_name = 'openerp-' + branch
    if has_systemd():
        service_path = '/etc/systemd/system/{0}.service'.format(service_name)
    else:
        service_path = '/etc/init.d/{0}'.format(service_name)
    return (service_name, service_path)


@as_('root')
def _odoo_create_initd(branch):
    """ create the initd file for the service """
    ctx = {
        'branch': branch
    }

    sudo('ln -sf {0}/bin/openerp {0}/bin/openerp-{1}'.format(ODOO_DIR_HOME, branch))

    def _upload_template(template, target, mode):
        upload_template(os.path.join(LOCAL_DIR_RESOURCES, template), target, ctx, backup=False, mode=mode)

    service_name, service_path = _odoo_branch2service(branch)
    if has_systemd():
        # systemd
        _upload_template('unit_openerp.tpl', service_path, '0644')
        run('systemctl daemon-reload')
        fabtools.systemd.enable(service_name)
    else:
        # SysV init
        _upload_template('initd_openerp.tpl', service_path, '0755')
        run('update-rc.d {0} defaults'.format(service_name))


def _odoo_is_service_running(branch_nick):
    """ check if the service of given branch exists and is running """
    service_name, service_path = _odoo_branch2service(branch_nick)
    if fabtools.files.is_file(service_path):
        return fabtools.systemd.is_running(service_name)
    return False


def _odoo_service_action(branch_nick, action):
    service_name, service_path = _odoo_branch2service(branch_nick)

    if not fabtools.files.is_file(service_path):
        puts(yellow('service {0} missing: skipping'.format(branch_nick)))
    else:
        if has_systemd():
            getattr(fabtools.systemd, action)(service_name)
        else:
            run('{0} {1}'.format(service_path, action))


@task
def odoo_db_add(domain, branch_nick, dbname=False):
    if not _validate_domain(domain):
        raise Exception("Given domain is not correct. Got '%s'." % (domain,))

    if not dbname:
        dbname = domain2database(domain)

    # insert meta entry
    sudo('{0}/cloud-meta odoo-add-database {1} {2} {3}'.format(SERV_DIR_CLOUD_SETUP, domain, branch_nick, dbname))

    # create nginx file
    odoo_create_nginx_config(dbname)


@task
def odoo_create_nginx_config(dbname):
    """ Create the nginx config file and restart nginx service
        :param dbname: name of the database to (re)generate the config file
    """
    dbinfo_str = sudo('{0}/cloud-meta odoo-get-info {1}'.format(SERV_DIR_CLOUD_SETUP, dbname))
    dbinfo = json.loads(dbinfo_str)

    # create nginx file
    upload_template(os.path.join(LOCAL_DIR_RESOURCES, 'nginx_openerp.tpl'), '/etc/nginx/sites-availables/%s' % (dbname,), dbinfo, backup=False, mode='0644')
    run("ln -sfT /etc/nginx/sites-availables/%s /etc/nginx/sites-enabled/%s" % (dbname, dbname))

    # restart nginx
    if fabtools.systemd.is_running('nginx'):
        fabtools.systemd.restart('nginx')
    else:
        fabtools.systemd.start('nginx')
