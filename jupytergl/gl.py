from contextlib import contextmanager
from asyncio import Future, ensure_future, get_event_loop

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


class ChunkContext:
    """A context that accumulates instructions for later execution"""
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

    _cmd_id = 0

    def __init__(self):
        self._context = None
        self._comm = None
        self._open()
        self._constants = {}
        self._methods = []
        self._request_constants()
        self._request_methods()
        self._prev_sent = get_event_loop().create_future()
        self._prev_sent.set_result(None)

    def __del__(self):
        self._close()

    def __dir__(self):
        d = list(self.__dict__.keys())
        if self._constants:
            d.extend(self._constants.keys())
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
            self._context = ChunkContext(self._constants, self._methods)
        yield self
        if outermost:
            try:
                self._send_instructions(self._context, 'exec')
            finally:
                self._context = None

    def branch(self):
        return BranchContext(self)

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
        cmd_id = self._send_instructions([Instruction(name, args)], 'query')
        return self._comm.future_query_reply(cmd_id)

    @contextmanager
    def orbitView(self, fov=None, near=None, far=None):
        if self._context is not None:
            raise ValueError('Cannot call orbit view from chunk!')
        self._context = ChunkContext(self._constants, self._methods)
        yield self

        instructions = list(self._context)
        self._context = None

        async def send_command():
            nonlocal instructions
            instructions, buffers = await self._separate_buffers(instructions)
            command = dict(
                type='command',
                command=dict(
                    op='orbitView',
                    args=[fov, near, far],
                    instructions=instructions,
                )
            )
            await prev_sent
            self._send(command, None, buffers)
        prev_sent = self._prev_sent  # Put into closure
        self._prev_sent = ensure_future(send_command())

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

    def _get_futures(self, instructions):
        return [a for i in instructions for a in i.args if isinstance(a, Future)]

    async def _separate_buffers(self, instructions):
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
                elif isinstance(a, Future):
                    processed_args.append(await a)
                else:
                    raise TypeError(
                        'Invalid argument to method %s: %r' % (i.name, a))
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
        async def send_resolved():
            nonlocal instructions
            instructions, buffers = await self._separate_buffers(instructions)
            msg = dict(
                type=mode,
                instructions=instructions,
            )
            await prev_sent
            self._send(msg, metadata, buffers)

        JupyterGL._cmd_id += 1
        metadata = dict(cmd_id=JupyterGL._cmd_id)
        prev_sent = self._prev_sent  # Put into closure
        self._prev_sent = ensure_future(send_resolved())
        return metadata['cmd_id']

    def _send(self, msg, metadata=None, buffers=None):
        """Sends a message to the model in the front-end."""
        if self._comm is not None and self._comm.kernel is not None:
            self._comm.send(data=msg, metadata=metadata, buffers=buffers)

    def _handle_msg(self, message):
        """Called when a msg is received from the front-end"""
        msg = message['content']['data']
        if 'type' not in msg:
            raise ValueError('Invalid message received: %s', message)
        if msg['type'] == 'constantsReply':
            # TODO: Sanitize constants?
            self._constants.clear()
            self._constants.update(msg['data'])
        elif msg['type'] == 'methodsReply':
            # TODO: Sanitize methods?
            self._methods[:] = msg['data']
        elif msg['type'] == 'queryReply':
            # This should have been handled in QueryableComm!
            raise ValueError(msg)
        else:
            raise ValueError('Invalid message received: %s', message)


class BranchContext(JupyterGL):
    """A context that is not part of the normal, serial execution.

    This needs to be used for all coroutines to avoid circular
    dependenices of futures.
    """

    def __init__(self, gl):
        self._context = None
        self._comm = gl._comm
        self._constants = gl._constants
        self._methods = gl._methods
        self._prev_sent = gl._prev_sent
        self._gl = gl

    def __del__(self):
        pass  # Do not close comms!
