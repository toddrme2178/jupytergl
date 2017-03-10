from tornado.ioloop import IOLoop
from tornado.platform.asyncio import AsyncIOMainLoop
import asyncio
import zmq.asyncio
import zmq.eventloop
import ipykernel.kernelapp

p = asyncio.get_event_loop_policy()


class ZMQPolicy(p.__class__):

    def __init__(self):
        self._created_once = False
        super(ZMQPolicy, self).__init__()

    def get_event_loop(self):
        return super(ZMQPolicy, self).get_event_loop()

    def new_event_loop(self):
        if self._created_once:
            return super(ZMQPolicy, self).new_event_loop()
        else:
            self._created_once = True
            return zmq.asyncio.ZMQEventLoop()

    def set_event_loop(self, loop):
        super(ZMQPolicy, self).set_event_loop(loop)


def install_loop():
    """Install and return the global ZMQEventLoop
    registers the loop with asyncio.set_event_loop
    """
    # check if tornado's IOLoop is already initialized to something other
    # than the pyzmq IOLoop instance:
    assert (not IOLoop.initialized()) or \
        IOLoop.instance() is AsyncIOMainLoop.instance(), "tornado IOLoop already initialized"

    # First, set asyncio to use ZMQEventLoop (ZMQSelector) as its loop
    asyncio.set_event_loop_policy(ZMQPolicy())
    # Next have tornado work on top of current asyncio loop
    AsyncIOMainLoop().install()


ipykernel.kernelapp.zmq_ioloop.install = install_loop


class AsyncApp(ipykernel.kernelapp.IPKernelApp):

    name='asyncio-ipython-kernel'

    def start(self):
        if self.subapp is not None:
            return self.subapp.start()
        if self.poller is not None:
            self.poller.start()
        self.kernel.start()
        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass


def main():
    """Run an IPKernel as an application"""
    app = AsyncApp.instance()
    app.initialize()
    app.start()


if __name__ == '__main__':
    main()
