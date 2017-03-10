# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import errno
import sys
import os
import json
import tempfile
import shutil
from ipykernel.kernelspec import make_ipkernel_cmd

from jupyter_client.kernelspec import KernelSpecManager

pjoin = os.path.join


KERNEL_NAME = 'async-python%i' % sys.version_info[0]


def make_asynckernel_cmd():
    return make_ipkernel_cmd(mod='jupytergl.kernel')


def get_kernel_dict():
    """Construct dict for kernel.json"""
    return {
        'argv': make_asynckernel_cmd(),
        'display_name': 'Async Python %i' % sys.version_info[0],
        'language': 'python',
    }


def write_kernel_spec(path=None):
    """Write a kernel spec directory to `path`

    If `path` is not specified, a temporary directory is created.
    If `overrides` is given, the kernelspec JSON is updated before writing.

    The path to the kernelspec is always returned.
    """
    if path is None:
        path = os.path.join(tempfile.mkdtemp(suffix='_kernels'), KERNEL_NAME)
        os.mkdir(path)

    # write kernel.json
    kernel_dict = get_kernel_dict()

    with open(pjoin(path, 'kernel.json'), 'w') as f:
        json.dump(kernel_dict, f, indent=1)

    return path


def install(kernel_spec_manager=None, user=False, prefix=None):
    """Install the IPython kernelspec for Jupyter

    Parameters
    ----------

    kernel_spec_manager: KernelSpecManager [optional]
        A KernelSpecManager to use for installation.
        If none provided, a default instance will be created.
    user: bool [default: False]
        Whether to do a user-only install, or system-wide.
    prefix: str, optional
        Specify an install prefix for the kernelspec.
        This is needed to install into a non-default location, such as a conda/virtual-env.
    Returns
    -------

    The path where the kernelspec was installed.
    """
    if kernel_spec_manager is None:
        kernel_spec_manager = KernelSpecManager()

    path = write_kernel_spec()
    dest = kernel_spec_manager.install_kernel_spec(path, user=user, prefix=prefix)
    # cleanup afterward
    shutil.rmtree(path)
    return dest



from traitlets.config import Application

class InstallAsyncPythonKernelSpecApp(Application):
    """Dummy app wrapping argparse"""
    name = 'async-python-kernel-install'

    def initialize(self, argv=None):
        if argv is None:
            argv = sys.argv[1:]
        self.argv = argv

    def start(self):
        import argparse
        parser = argparse.ArgumentParser(prog=self.name,
            description="Install the IPython kernel spec.")
        parser.add_argument('--user', action='store_true',
            help="Install for the current user instead of system-wide")
        parser.add_argument('--prefix', type=str,
            help="Specify an install prefix for the kernelspec."
            " This is needed to install into a non-default location, such as a conda/virtual-env.")
        parser.add_argument('--sys-prefix', action='store_const', const=sys.prefix, dest='prefix',
            help="Install to Python's sys.prefix."
            " Shorthand for --prefix='%s'. For use in conda/virtual-envs." % sys.prefix)
        opts = parser.parse_args(self.argv)
        try:
            dest = install(user=opts.user, prefix=opts.prefix)
        except OSError as e:
            if e.errno == errno.EACCES:
                print(e, file=sys.stderr)
                if opts.user:
                    print("Perhaps you want `sudo` or `--user`?", file=sys.stderr)
                self.exit(1)
            raise
        print("Installed kernelspec in %s" % dest)


if __name__ == '__main__':
    InstallAsyncPythonKernelSpecApp.launch_instance()
