from contextlib import contextmanager

import numpy as np

from .comm import QueryableComm


def _is_json_primitive(value):
    return value is None or isinstance(
        value, (str, list, dict, bool, int, float))


class Instruction:
    def __init__(self, name, args=None, gl=None):
        self.name = name
        self.gl = gl
        if args is not None:
            self.args = args

    def __call__(self, *args):
        self.args = args
        if self.gl is not None:
            return self.gl.query(self.name, args)

    def _serialize(self):
        return dict(op=self.name, args=self.args)


class RemoteContext:
    def __init__(self, constants, methods):
        self._constants = constants
        self._methods = methods
        self._instructions = []

    def __getattr__(self, name):
        if self._constants and name in self._constants:
            return self._constants[name]
        elif self._methods and name in self._methods:
            method = Instruction(name)
            self._instructions.append(method)
            return method
        else:
            raise AttributeError(name)

    def __iter__(self):
        for instruction in self._instructions:
            if not hasattr(instruction, 'args'):
                raise ValueError(
                    'Function "%s" was never called!' % instruction.name)
            yield instruction


class JupyterGL:
    def __init__(self, query_timeout=10):
        self._context = None
        self._comm = None
        self._query_timeout = query_timeout
        self._open()
        self._constants = None
        self._methods = None
        self._request_constants()
        self._request_methods()

    def __del__(self):
        self._close()

    def __dir__(self):
        d = list(self.__dict__.keys())
        if self._constants:
            d.extend(self._constants)
        if self._methods:
            d.extend(self._methods)
        return d

    def _open(self):
        """Open a _comm to the frontend if one isn't already open."""
        if self._comm is None:
            self._comm = QueryableComm(target_name='jupytergl')
            self._comm.on_msg(self._handle_msg)
            self._comm.kernel

    def _close(self):
        """Close the underlying _comm."""
        if self._comm is not None:
            self._comm.close()
            self._comm = None

    @contextmanager
    def chunk(self):
        outermost = self._context is None
        if outermost:
            self._context = RemoteContext(self._constants, self._methods)
        yield self
        if outermost:
            self._send_instructions(self._context, 'exec')
            self._context = None

    def exec_(self, name, args):
        if self.context is None:
            self._send_instructions([Instruction(name, args)], 'exec')
        else:
            getattr(self._context, name)(*args)

    def query(self, name, args):
        if self._context is not None:
            raise RuntimeError(
                'Cannot directly query a JupyterGL method within '
                'an active context')
        self._send_instructions([Instruction(name, args)], 'query')
        return self._comm.await_query_reply(timeout=self._query_timeout)

    def __getattr__(self, name):
        if self._constants and name in self._constants:
            return self._constants[name]
        elif self._methods and name in self._methods:
            if self._context is None:
                method = Instruction(name, gl=self)
                return method
            else:
                return getattr(self._context, name)
        else:
            raise AttributeError(name)

    def _separate_buffers(self, instructions):
        buffers = []
        processed_instructions = []
        for i in instructions:
            processed_args = []
            for a in i.args:
                if _is_json_primitive(a):
                    processed_args.append(a)
                elif isinstance(a, (np.ndarray, np.generic)):
                    processed_args.append('buffer%s' % a.dtype)
                    buffers.append(memoryview(a))
                elif isinstance(a, (memoryview, bytes, bytearray)):
                    processed_args.append('buffer%s' % a.dtype)
                    buffers.append(a)
                else:
                    raise TypeError(
                        'Invalid argument to method %s: %r', i.name, a)
            processed_instructions.append(Instruction(i.name, processed_args)._serialize())
        return processed_instructions, buffers

    def _request_constants(self):
        msg = dict(type="getConstants", target="context")
        self._send(msg)

    def _request_methods(self):
        msg = dict(type="getMethods", target="context")
        self._send(msg)

    def _send_instructions(self, instructions, mode):
        if not instructions:
            return
        instructions, buffers = self._separate_buffers(instructions)
        msg = dict(
            type=mode,
            instructions=instructions
        )
        self._send(msg, buffers)

    def _send(self, msg, buffers=None):
        """Sends a message to the model in the front-end."""
        if self._comm is not None and self._comm.kernel is not None:
            self._comm.send(data=msg, buffers=buffers)

    def _handle_msg(self, message):
        """Called when a msg is received from the front-end"""
        msg = message['content']['data']
        if 'type' not in msg:
            raise ValueError('Invalid message received: %s', message)
        if msg['type'] == 'constantsReply':
            self._constants = msg['data']
        elif msg['type'] == 'methodsReply':
            self._methods = msg['data']
        elif msg['type'] == 'queryReply':
            # This should have been handled in QueryableComm!
            raise ValueError(msg)
        else:
            raise ValueError('Invalid message received: %s', message)
