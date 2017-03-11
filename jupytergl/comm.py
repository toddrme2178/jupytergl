import asyncio
from ipykernel.comm import Comm


class QueryableComm(Comm):

    def __init__(self, *args, **kwargs):
        self.waiting_queries = {}
        super(QueryableComm, self).__init__(*args, **kwargs)

    def future_query_reply(self, cmd_id):
        future = asyncio.get_event_loop().create_future()
        self.waiting_queries[cmd_id] = future
        return future

    def clear_queue(self):
        n_cleared = 0
        for cmd_id, query in self.waiting_queries.items():
            n_cleared += 1
            query.cancel()
        return n_cleared

    def handle_msg(self, message):
        msg = message['content'].get('data')
        if msg and msg.get('type') == 'queryReply':
            query = self.waiting_queries.pop(message['metadata']['cmd_id'])
            query.set_result(msg['data'])
        elif msg and msg.get('type') == 'queryError':
            query = self.waiting_queries.pop(message['metadata']['cmd_id'])
            query.set_exception(RuntimeError(msg['data']))
        else:
            return super(QueryableComm, self).handle_msg(message)

QueryableComm.__init__.__doc__ = Comm.__init__.__doc__
