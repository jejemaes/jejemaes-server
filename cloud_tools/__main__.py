# -*- coding: utf-8 -*-
"""
cloud-setup

Usage:
    cloud-setup lemp setup [options]
    cloud-setup lemp update [options]
    cloud-setup lemp upgrade [options]
    cloud-setup lemp config [options]
    cloud-setup lemp newsite -d <dns> -u <user> -g <group> [options]
    cloud-setup odoo setup [options]

Options:
  -v         Verbose output
  -V         More verbose output

Available commands:
  {0}

"""

import sys
import logging
import docopt

from . import _commands
from . import server_lemp
from . import server_odoo


commands = _commands.keys()
cmdlist = ['  %s\n' % key for key in commands]
args = docopt.docopt(__doc__.format(cmdlist))

log = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    level='DEBUG' if (args['-v'] or args['-V']) else 'INFO',
    stream=sys.stderr,
)
if not args['-V']:
    logging.getLogger("sh").setLevel(logging.ERROR)


if args.get('lemp'):
    if args.get('setup'):
        server_lemp.setup_lemp_server(upgrade=False)  # TODO: may be changed upgrade=True
        server_lemp.config_lemp_server()
        server_lemp.restart_lemp_services()
    elif args.get('update'):
        server_lemp.setup_lemp_server()
    elif args.get('upgrade'):
        server_lemp.setup_lemp_server(upgrade=True)
        server_lemp.restart_lemp_services()
    elif args.get('config'):
        server_lemp.config_lemp_server()
        server_lemp.restart_lemp_services()
    elif args.get('newsite'):
        server_lemp.create_new_site(args['<user>'], args['<group>'], args['<dns>'])

elif args.get('odoo'):
    log.warn('Odoo Server Scripts not implemented yet ...')
