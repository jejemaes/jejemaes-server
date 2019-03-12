# -*- coding: utf-8 -*-
import sh
import os

from pipes import quote
import random
import string

from subprocess import PIPE, Popen

from . import DIR_RESOURCE


# ----------------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------------

def _load_template(template_name):
    tmpl_file_path = '%s%s.tpl' % (DIR_RESOURCE, template_name)
    return file_read(tmpl_file_path)

def render_template(template_name, context):
    template_content = load_template(template_name)
    return template_content.format(**context)

# ----------------------------------------------------------------------------
# Files and Directory
# ----------------------------------------------------------------------------

def is_file(path):
    return os.path.isfile(path)

def is_dir(path):
    return os.path.isdir(path)

def is_link(path):
    return os.path.islink(path)

def file_create(path, content):
    """ Create a new file at the given absolute path with the given content """
    with open(path, 'w') as file_conf:
        file_conf.write(content)
        return path
    return False

def file_read(path):
    content = ''
    with open(path, 'r') as content_file:
        content = content_file.read()
    return content

def file_from_template(path, template_name, context, use_sudo=False):
    if use_sudo:
        with sh.contrib.sudo:
            return _file_from_template(path, template_name, context)
    return _file_from_template(path, template_name, context)

def _file_from_template(path, template_name, context):
    content = render_template(template_name, context)
    return file_create(path, content) 

# ----------------------------------------------------------------------------
# Unix Users and Groups
# ----------------------------------------------------------------------------

def group_exists(name):
    """
    Check if a group exists.
    """
    return bool(_run('getent group %(name)s' % locals()))


def group_create(name, gid=None):
    """
    Create a new group.
    """
    args = []
    if gid:
        args.append('-g %s' % gid)
    args.append(name)
    args = ' '.join(args)
    return _run('groupadd %s' % args)

_SALT_CHARS = string.ascii_letters + string.digits + './'


def _crypt_password(password):
    from crypt import crypt
    random.seed()
    salt = ''
    for _ in range(2):
        salt += random.choice(_SALT_CHARS)
    crypted_password = crypt(password, salt)
    return crypted_password


def user_exists(name):
    """
    Check if a user exists.
    """
    return bool(_run('getent passwd %(name)s' % locals()))


def user_create(name, comment=None, home=None, create_home=None, skeleton_dir=None,
           group=None, create_group=True, password=None,
           system=False, shell=None, uid=None,
           non_unique=False):
    """
    Create a new user and its home directory.

    If *create_home* is ``None`` (the default), a home directory will be
    created for normal users, but not for system users.
    You can override the default behaviour by setting *create_home* to
    ``True`` or ``False``.

    If *system* is ``True``, the user will be a system account. Its UID
    will be chosen in a specific range, and it will not have a home
    directory, unless you explicitely set *create_home* to ``True``.

    If *shell* is ``None``, the user's login shell will be the system's
    default login shell (usually ``/bin/sh``).
    """

    # Note that we use useradd (and not adduser), as it is the most
    # portable command to create users across various distributions:
    # http://refspecs.linuxbase.org/LSB_4.1.0/LSB-Core-generic/LSB-Core-generic/useradd.html

    args = []
    if comment:
        args.append('-c %s' % quote(comment))
    if home:
        args.append('-d %s' % quote(home))
    if group:
        args.append('-g %s' % quote(group))
        if create_group:
            if not group_exists(group):
                group_create(group)

    if create_home is None:
        create_home = not system
    if create_home is True:
        args.append('-m')
    elif create_home is False:
        args.append('-M')

    if skeleton_dir:
        args.append('-k %s' % quote(skeleton_dir))
    if password:
        crypted_password = _crypt_password(password)
        args.append('-p %s' % quote(crypted_password))
    if system:
        args.append('-r')
    if shell:
        args.append('-s %s' % quote(shell))
    if uid:
        args.append('-u %s' % uid)
        if non_unique:
            args.append('-o')
    args.append(name)
    args = ' '.join(args)
    return _run('useradd %s' % args)

# ----------------------------------------------------------------------------
# Private unix command execution
# ----------------------------------------------------------------------------

def run_as_sudo(cmd):
    with sh.contrib.sudo:
        return _run(cmd)


def _run(cmd):
    """ Execute the given unix command and raise an exception if it fails, or the result as a strings
        :param cmd: unix command
    """
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _err = result.stderr.read()
    if _err:
        raise Exception(_err)
    _out = result.stdout.read()
    return _out.replace('\\n', '\n')

# ----------------------------------------------------------------------------
# Patch of SH lib
# ----------------------------------------------------------------------------

OK_RET_CODES = [0]


class _AttributeString(str):
    """
    Simple string subclass to allow arbitrary attribute access.
    """
    @property
    def stdout(self):
        return str(self)


def run(command):
    process = Popen(
        args=command,
        stdout=PIPE,
        stderr=PIPE,
        shell=True
    )
    (result_stdout, result_stderr) = process.communicate()
    status = process.returncode

    out = _AttributeString(result_stdout)
    err = _AttributeString(result_stderr)

    # Error handling
    out.failed = False
    out.command = command
    if status not in OK_RET_CODES:
        out.failed = True
        msg = "%s() received nonzero return code %s while executing" % (command, status,)
        msg += " '%s'!" % command
        out.err = "message=%s, stdout=%s, stderr=%s" % (msg, out, err)

    # Attach return code to output string so users who have set things to
    # warn only, can inspect the error code.
    out.return_code = status

    # Convenience mirror of .failed
    out.succeeded = not out.failed

    # Attach stderr for anyone interested in that.
    out.stderr = err

    return out
