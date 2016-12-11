#!/usr/bin/env python

from fabric.api import task, env, run, cd, sudo, hide
from fabric.colors import red, yellow, green, blue, white
from fabric.utils import warn, puts

import fabtools
import fabtools.require

from functools import wraps


DIR_SCRIPT = '/root/cloud/'

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
    with cd('/root/cloud/'):
        sudo('./cloud-setup lemp setup -v')


@task
@as_('root')
def update_lemp_server():
    with cd('/root/cloud/'):
        sudo('./cloud-setup lemp update -v')


@task
def test():
    run("ls -la")
    
