#!/usr/bin/env python
import ConfigParser
import io
import os

from fabric.api import task, env, run, cd, sudo, hide
from fabric.colors import red, yellow, green, blue, white
from fabric.utils import warn, puts

import fabtools
import fabtools.require

from functools import wraps


DIR_SCRIPT = '/root/cloud/'
CONFIG = {}

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

#----------------------------------------------------------
# Setup:
# These methods should install only what is required to make
# the cloud_tools works. Simply install base packages and
# checkout the tools code to execute it.
#----------------------------------------------------------


@as_('root')
def _setup_packages():
    """ Method to install common packages """
    debs = """
debconf-utils
git
htop
jq
python-pip
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


@as_('root')
def _setup_scripts():
    """ Checkout the scripts and setup the /root/src directory """
    # checkout or pull
    sudo('mkdir -p ' + DIR_SCRIPT)
    with cd(DIR_SCRIPT):
        if not fabtools.files.is_dir('setup'):
            sudo('git clone https://github.com/jejemaes/jejemaes-server.git setup')
        else:
            setup_update()


@task
@as_('root')
def setup():
    _setup_packages()
    _setup_scripts()


@task
@as_('root')
def setup_update():
    """ Update the cloud tools code """
    path = DIR_SCRIPT + 'setup'
    if not fabtools.files.is_dir(path):
        puts(red('Setup directory {0} not found'.format(path)))
        return

    puts(blue('Update setup directory {0}'.format(path)))
    with cd(path):
        sudo('git fetch --quiet --prune')
        sudo('git rebase --quiet --autostash')
        with hide('status', 'commands'):
            no_conflicts = sudo('git diff --diff-filter=U --no-patch --exit-code').succeeded
    puts(blue('Update done !'))
    return no_conflicts

#----------------------------------------------------------
# LEMP server
#----------------------------------------------------------

@task
@as_('root')
def setup_lemp_server():
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

    # create unix group
    if not fabtools.group.exists(group):
        fabtools.group.create(group)

    # create unix user
    if not fabtools.user.exists(user):
        home_dir = '/home/%s' % (user,)
        fabtools.user.create(user, group=group, home=home_dir, shell='/bin/bash')

    # create php fpm and nginx files, and restart services
    with cd('/root/cloud/setup'):
        sudo('./cloud-setup lemp newsite -d {dns} -u {user} -g {group} -v'.format(dns=domain, user=user, group=user))
    fabtools.service.restart('php7.0-fpm')
    fabtools.service.restart('nginx')

    # create mysql user and database
    mysql_config = _get_config('mysql')
    if fabtools.mysql.user_exists(user, **mysql_config):
        fabtools.mysql.user_create(user, password, **mysql_config)

    if fabtools.mysql.database_exists(user, **mysql_config):
        fabtools.mysql.create_database(user, owner=user, **mysql_config)
