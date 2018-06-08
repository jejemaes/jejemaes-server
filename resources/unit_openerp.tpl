[Unit]
Description=openerp/odoo %(branch)s

[Service]
Type=simple
User=odoo
LimitNOFILE=16384
ExecStart=/home/odoo/bin/openerp-%(branch)s
ExecStartPost=/bin/sh -c "/bin/echo $MAINPID > /home/odoo/log/openerp-%(branch)s.pid"
ExecStopPost=/bin/sh -c "/bin/rm /home/odoo/log/openerp-%(branch)s.pid"
TimeoutStopSec=5
KillMode=mixed
Restart=on-failure

[Install]
WantedBy=multi-user.target
