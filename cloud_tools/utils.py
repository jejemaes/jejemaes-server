# -*- coding: utf-8 -*-

from subprocess import PIPE, Popen


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
