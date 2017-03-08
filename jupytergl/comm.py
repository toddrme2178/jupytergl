import time
from ipykernel.comm import Comm


class QueryableComm(Comm):

    def await_query_reply(self, timeout=None):
        self._query_reply_received = False
        self._query_reply = None
        start_time = time.time()
        if timeout is None:
            timeout = 10
        while start_time + timeout > time.time() and not self._query_reply_received:
            self.kernel.do_one_iteration()
        if not self._query_reply_received:
            raise TimeoutError()
        return self._query_reply

    def handle_msg(self, message):
        msg = message['content'].get('data')
        if msg and msg.get('type') == 'queryReply':
            self._query_reply_received = True
            self._query_reply = msg.get('data')
        else:
            return super(QueryableComm, self).handle_msg(message)
