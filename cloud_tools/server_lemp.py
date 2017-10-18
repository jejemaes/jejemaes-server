# -*- coding: utf-8 -*-

import logging
import os
import sh


from . import DIR_FILES
from . import templates
from utils import run


log = logging.getLogger(__name__)


def setup_lemp_server(upgrade=False):
    """ Uninstall, install or update all required lib (python or debs) for the LEMP stack server """
    log.info("Uninstalling apt ...")
    debs_to_uninstall = """
        php5
    """.split()
    sh.dpkg('-P', debs_to_uninstall)

    log.info("Updating apt ...")
    sh.apt_get.update(_out=log.debug)
    if upgrade:
        log.info("Upgrading apt ...")
        sh.apt_get.upgrade('-y', '--force-yes', _out=log.debug)

    # check if mysql server already installed. If not, warn to set root password
    if not os.path.isdir('/etc/mysql'):
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        mysql_root_pass = '!r00tpAss2017'
        log.warn('Mysql server will be installed in non interactive mode. DO NOT FORGET TO SET THE ROOT PASSWORD, since the default one will be %s.', mysql_root_pass)
        run("""echo "mysql-server-5.7 mysql-server/root_password password %s" | sudo debconf-set-selections""" % (mysql_root_pass,))
        run("""echo "mysql-server-5.7 mysql-server/root_password_again password %s" | sudo debconf-set-selections""" % (mysql_root_pass,))

    log.info("Installing deb dependencies ...")
    debs_to_install = """
        mysql-server-5.7
        nginx
        php7.0
        php7.0-fpm
        php7.0-gd
        php7.0-mysql
        php7.0-common
        php7.0-curl
        php7.0-opcache
    """.split()
    sh.apt_get.install('-y', '--ignore-missing', debs_to_install, _out=log.debug)


def config_lemp_server():
    """ Copy config file for LEMP packages (nginx, mysql, php, ...) """
    run("rsync -rtlE %setc/nginx/ /etc/nginx/" % (DIR_FILES,))
    run("rsync -rtlE %setc/php/ /etc/php/" % (DIR_FILES,))


def restart_lemp_services():
    run("systemctl reload nginx")
    run("systemctl restart php7.0-fpm")


def create_new_site(user, group, domain):
    """ Create the fpm pool file, append domain to /etc/host and add a site file for nginx
        :param user: unix username to run the pool
        :param group: unix group to run the pool
        :param domain: DNS of the website to run
    """
    # create php fpm pool
    file_path = '/etc/php/7.0/fpm/pool.d/{user}.conf'.format(user=user)
    if not os.path.isfile(file_path):
        context = {
            'unix_user': user,
            'unix_group': group,
            'domain': domain,
        }
        file_content = templates.render_template('php-fpm-pool', context)
        with open(file_path, 'w') as file_conf:
            file_conf.write(file_content)

        # append to /etc/hosts
        with sh.contrib.sudo:
            with open("/etc/hosts", "a") as hosts_file:
                hosts_file.write("127.0.0.1 %s\n" % (domain,))

    # create new nginx site config
    file_path = '/etc/nginx/sites-available/{user}'.format(user=user)
    if not os.path.isfile(file_path):
        context = {
            'unix_user': user,
            'unix_group': group,
            'domain': domain,
        }
        file_content = templates.render_template('nginx-site-available', context)
        with open(file_path, 'w') as file_conf:
            file_conf.write(file_content)

        run("""ln -s /etc/nginx/sites-available/{user} /etc/nginx/sites-enabled/{user}""".format(user=user))
