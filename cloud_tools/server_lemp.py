# -*- coding: utf-8 -*-

import logging
import os
import sh

from subprocess import call

from . import DIR_FILES

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
		os.system("""echo "mysql-server-5.7 mysql-server/root_password password %s" | sudo debconf-set-selections""" % (mysql_root_pass,))
		os.system("""echo "mysql-server-5.7 mysql-server/root_password_again password %s" | sudo debconf-set-selections""" % (mysql_root_pass,))

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
	os.system("rsync -rtlE %setc/nginx/ /etc/nginx/" % (DIR_FILES,))
	os.system("rsync -rtlE %setc/php/ /etc/php/" % (DIR_FILES,))


def restart_lemp_services():
	os.system("systemctl reload nginx")
	os.system("systemctl restart php7.0-fpm")

	