# -*- coding: utf-8 -*-
# flake8: noqa
from collections import OrderedDict
import os

_commands = OrderedDict()

def command(func):
    _commands[func.__name__] = func
    return func

HERE = os.path.dirname(os.path.realpath(__file__))
DIR_FILES = HERE + '/../cloud_files/'
DIR_TEMPLATE = HERE + '/../tmpl/'
DIR_SCRIPTS = HERE + '/../scripts/'
DIR_RESOURCE = HERE + '/../resources/'

from . import server_lemp
from . import server_odoo
