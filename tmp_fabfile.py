#!/usr/bin/env python
from functools import wraps, partial

from fabric.api import task, env, run, cd, sudo, hide
from fabric.colors import red, yellow, green, blue, white
from fabric.utils import warn, puts
from fabric.context_managers import warn_only, settings, shell_env

import fabric
import fabtools
import fabtools.require


# Constants
GIT_CLOUD_URL = 'https://github.com/jejemaes/jejemaes-server.git'
MYSQL_METABASE_NAME = 'meta'
ROOT_DIR = '/home/root/'
SCRIPTS_DIR = ROOT_DIR + 'scripts/'
TEMPLATE_DIR = ROOT_DIR + 'templates/'

USER_UNIX_WEB = 'webuser'
USER_UNIX_WEB_UID = '10000'
USER_UNIX_WEB_HOME = '/home/%s' % (USER_UNIX_WEB,)

GROUP_UNIX_WEB = 'webuser'
GROUP_UNIX_WEB_GID = '10000'

# test for odoo
#----------------------------------------------------------
# Tools
#----------------------------------------------------------
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


@as_('root')
def uid(username):
    """ Return the unix uid of a given username """
    try:
        with settings(hide('warnings'), warn_only=True):
            result = run('id -u {0}'.format(username))
            return int(result)
    except ValueError:
        puts(red('{0} unix user does not exist. Returned uid is False'.format(username)))
    return False


def get_template(template_name):
    content = ''
    template_file = TEMPLATE_DIR + template_name + '.txt'
    print template_file
    with open(template_file, 'r') as content_file:
        content = content_file.read()
    return content


def render_template(template_name, values):
    template = get_template(template_name)
    from jinja2 import Template
    template_jinja = Template(template)
    return template_jinja.render(**values)


#----------------------------------------------------------
# Setup
#----------------------------------------------------------
@task
@as_('root')
def setup_packages():
    """ Install/Upgrade packages required to make the complete server work """
    # uninstall some packages
    uninstall = """wkhtmltopdf apache2""".split()
    fabtools.deb.uninstall(uninstall, purge=True, options=['--quiet'])
    # install and upgrade dependencies
    debs = """
python-dev
bsd-mailx
curl
fabric
file
geoip-database
ghostscript
git
graphviz
htop
less
libdbd-pg-perl
libev-dev
libevent-dev
libfreetype6-dev
libjpeg8-dev
liblchown-perl
libpq-dev
libtiff-dev
libwww-perl
libxml2-dev
libxslt1-dev
lsb-release
lsof
make
mc
moreutils
mosh
msmtp
msmtp-mta
ncdu
nginx
npm
openntpd
p7zip-full
postgresql
postgresql-contrib
python-babel
python-dateutil
python-decorator
python-docutils
python-feedparser
python-gdata
python-geoip
python-gevent
python-jinja2
python-ldap
python-libxslt1
python-lxml
python-mako
python-markdown
python-matplotlib
python-mock
python-openid
python-passlib
python-pip
python-psutil
python-psycopg2
python-pychart
python-pydot
python-pyparsing
python-pypdf
python-reportlab
python-requests
python-setproctitle
python-simplejson
python-tz
python-unittest2
python-vatnumber
python-vobject
python-webdav
python-werkzeug
python-xlrd
python-xlwt
python-yaml
python-zsi
rsnapshot
rsync
sudo
tree
unzip
uptimed
vim
zip
""".split()
    run("apt-get upgrade -y --force-yes")
    fabtools.deb.install(debs, options=['--force-yes', '--ignore-missing'])
    # install pyton lib
    if not fabtools.python.is_pip_installed():
        fabtools.python.install_pip()
    python_pip = """
lxml==3.5.0
fabtools
docopt
python-slugify
ofxparse
pillow
xlsxwriter
psycogreen
""".split()
    fabtools.python.install(python_pip, upgrade=True)
    return True


@as_('root')
def setup_users():
    """ Create the Unix user and related group """
    # create 'webuser' group
    if not fabtools.group.exists(GROUP_UNIX_WEB):
        fabtools.group.create(GROUP_UNIX_WEB, gid=GROUP_UNIX_WEB_GID)
    # create 'webuser' user and link it to the 'webuser' group
    if not fabtools.user.exists(USER_UNIX_WEB):
        fabtools.user.create(USER_UNIX_WEB, home=USER_UNIX_WEB_HOME, create_home=True, shell='/bin/bash', uid=USER_UNIX_WEB_UID, group=GROUP_UNIX_WEB)


@as_('root')
def setup_checkout_scripts():
    if fabric.contrib.files.exists(ROOT_DIR + 'scripts/'):
        return
    sudo('mkdir -p {0}'.format(ROOT_DIR))
    with cd(ROOT_DIR):
        sudo('git clone -q --branch {0} --single-branch {1} scripts'.format('master', GIT_CLOUD_URL))


@task
@as_('root')
def setup_metabases():
    """ Create (if needed) the metabase in MySQL, and import the script to create/update the tables """
    if not fabtools.mysql.database_exists(MYSQL_METABASE_NAME):
        fabtools.mysql.create_database(MYSQL_METABASE_NAME, owner=USER_UNIX_WEB, owner_host='localhost', charset='utf8', collate='utf8_general_ci')
    sudo('mysql -u {0}} -p {1} < {2}/webuser-metabase.sql'.format(USER_UNIX_WEB, MYSQL_METABASE_NAME, SCRIPTS_DIR))


@task
@as_('root')
def setup():
    #setup_packages()
    #setup_users()
    setup_checkout_scripts()
    #setup_metabases()


@task
def test():
    print render_template('php-fpm-pool', {
        'sitename': 'caca',
        'unix_user': 'myuser',
        'unix_group': 'mygroup',
    })
