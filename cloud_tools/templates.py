# -*- coding: utf-8 -*-

from mako.template import Template

from . import DIR_TEMPLATE


######################################################
### TEMPLATES
######################################################

def load_template(template_name):
    tmpl_file_path = '%s%s.txt' % (DIR_TEMPLATE, template_name)
    content = ''
    with open(tmpl_file_path, 'r') as content_file:
        content = content_file.read()
    return content


def render_template(template_name, context):
    template_content = load_template(template_name)
    return Template(template_content).render(**context)
