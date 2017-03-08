
from contextlib import contextmanager
from ipykernel.comm import Comm

import numpy as np


def _is_json_primitive(value):
    return value is None or isinstance(
        value, (str, list, dict, bool, int, float))


class Instruction:
    def __init__(self, name, args=None):
        self.name = name
        if args is not None:
            self.args = args

    def __call__(self, *args):
        self.args = args


class RemoteContext:
    def __init__(self, mode, constants, methods):
        self._mode = mode
        self._constants = constants
        self._methods = methods
        self._instructions = []

    def __dir__(self):
        d = super(JupyterGL, self).__dir__()
        if self._constants:
            d.extend(self._constants)
        if self._methods:
            d.extend(self._methods)
        return d

    def __getattr__(self, name):
        if self._constants and name in self._constants:
            return self._constants[name]
        elif self._methods and name in self._methods:
            method = Instruction(name)
            self._instructions.append(method)
            return method
        else:
            raise AttributeError()

    def __iter__(self):
        for instruction in self._instructions:
            if not hasattr(instruction, 'args'):
                raise ValueError(
                    'Function "%s" was never called!' % instruction.name)
            yield instruction


class JupyterGL:
    def __init__(self, **kwargs):
        self._context = None
        self.open()
        self._constants = None
        self._methods = None

    def __del__(self):
        self.close()

    def open(self):
        """Open a comm to the frontend if one isn't already open."""
        if self.comm is None:
            self.comm = Comm(target_name='jupytergl')
            self.comm.on_msg(self._handle_msg)

    def close(self):
        """Close the underlying comm."""
        if self.comm is not None:
            self.comm.close()
            self.comm = None

    @contextmanager
    def context(self, mode='exec'):
        outermost = self._context is None
        if outermost:
            self._context = RemoteContext(mode, self._constants, self._methods)
        yield self._context
        if outermost:
            self._send_instructions(self._context)
            self._context = None
            if mode == 'query':
                raise NotImplementedError()

    def exec_(self, name, args):
        if self.context is None:
            self._send_instructions([Instruction(name, args)])
        else:
            getattr(self._context, name)(*args)

    def query(self, name, args):
        if self._context is not None:
            raise RuntimeError(
                'Cannot directly query a JupyterGL method within '
                'an active context')
        self._send_instructions([Instruction(name, args)])
        # TODO: Await response to return
        raise NotImplementedError()

    def _separate_buffers(self, instructions):
        buffers = []
        processed_instructions = []
        for i in instructions:
            processed_args = []
            for a in i.args:
                if _is_json_primitive(a):
                    processed_args.append(a)
                elif isinstance(a, (np.ndarray, np.generic)):
                    processed_args.append('buffer%d' % len(buffers))
                    buffers.append(memoryview(a))
                elif isinstance(a, (memoryview, bytes, bytearray)):
                    processed_args.append('buffer%d' % len(buffers))
                    buffers.append(a)
                else:
                    raise TypeError(
                        'Invalid argument to method %s: %r', i.name, a)
            processed_instructions.append(Instruction(i.name, processed_args))
        return processed_instructions, buffers

    def _request_constants(self):
        msg = dict(type="getConstants", target="context")
        self._send(msg)

    def _request_methods(self):
        msg = dict(type="getMethods", target="context")
        self._send(msg)

    def _send_instructions(self, instructions, mode):
        instructions, buffers = self._separate_buffers(instructions)
        msg = dict(
            type=mode,
            instructions=instructions
        )
        self._send(msg, buffers)

    def _send(self, msg, buffers=None):
        """Sends a message to the model in the front-end."""
        if self.comm is not None and self.comm.kernel is not None:
            self.comm.send(data=msg, buffers=buffers)

    def _handle_msg(self, msg):
        """Called when a msg is received from the front-end"""
        if msg.type == 'constantsReply':
            self._constants = msg.data
        elif msg.type == 'methodsReply':
            self._methods = msg.data
        elif msg.type == 'queryReply':
            # Signal query reply to anything that is waiting for it!
            raise NotImplementedError()
        else:
            raise ValueError('Invalid message received: %s', msg)
