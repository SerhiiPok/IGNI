import logging
from multiprocessing import Queue


class Task:

    """
    a task that is executed in a separate process
    implementors must be pickleable
    """

    def __init__(self, global_events_queue: Queue):
        self._logger = None
        self.global_events_queue = global_events_queue

    @property
    def logger(self):
        if self._logger is None:
            if self.global_events_queue is None:
                raise Exception("can't configure logger for multiprocessed task because logging queue is not set")
            queue_handler = logging.handlers.QueueHandler(self.global_events_queue)
            self._logger = logging.getLogger(type(self).__name__)
            self._logger.setLevel(logging.ERROR)
            self._logger.addHandler(queue_handler)
        return self._logger
