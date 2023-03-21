import logging
from multiprocessing import Queue
from pandas import DataFrame


class PersistenceTask:

    def __init__(self, table_name: str, data: DataFrame):
        self.dest: str = table_name
        self.data: DataFrame = data


class Task:

    """
    a task that is executed in a separate process
    implementors must be pickleable
    """

    def __init__(self, feedback_queue: Queue):
        self._logger = None
        self._feedback_queue = feedback_queue

    @property
    def logger(self):
        if self._logger is None:
            if self._feedback_queue is None:
                raise Exception("can't configure logger for multiprocessed task because logging queue is not set")
            queue_handler = logging.handlers.QueueHandler(self._feedback_queue)
            self._logger = logging.getLogger(type(self).__name__)
            self._logger.setLevel(logging.ERROR)
            self._logger.addHandler(queue_handler)
        return self._logger
