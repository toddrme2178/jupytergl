import asyncio
from ipykernel.comm import Comm
from queue import Queue, Empty


class QueryableComm(Comm):

    def __init__(self, *args, **kwargs):
        self.waiting_queries = Queue()
        super(QueryableComm, self).__init__(*args, **kwargs)

    def future_query_reply(self):
        future = asyncio.Future()
        self.waiting_queries.put_nowait(future)
        return future

    def clear_queue(self):
        n_cleared = 0
        try:
            while True:
                query = self.waiting_queries.get_nowait()
                n_cleared += 1
                query.cancel()
        except Empty:
            pass
        return n_cleared

    def handle_msg(self, message):
        msg = message['content'].get('data')
        if msg and msg.get('type') == 'queryReply':
            query = self.waiting_queries.get_nowait()
            query.set_result(msg['data'])
        elif msg and msg.get('type') == 'queryError':
            query = self.waiting_queries.get_nowait()
            query.set_exception(RuntimeError(msg['data']))
        else:
            return super(QueryableComm, self).handle_msg(message)

QueryableComm.__init__.__doc__ = Comm.__init__.__doc__
