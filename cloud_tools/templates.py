# -*- coding: utf-8 -*-

from mako.template import Template

from . import DIR_TEMPLATE
from . import utils

######################################################
### TEMPLATES
######################################################

def load_template(template_name):
    tmpl_file_path = '%s%s.txt' % (DIR_TEMPLATE, template_name)
    return utils.file_read(tmpl_file_path)


def render_template(template_name, context):
    template_content = load_template(template_name)
    return Template(template_content).render(**context)
