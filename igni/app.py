from .logging_util import getMLogger
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
            self._logger = getMLogger(type(self).__name__, self.global_events_queue)
        return self._logger


class ApplicationShutdownTask(Task):

    def __init__(self, global_events_queue: Queue):
        Task.__init__(self, global_events_queue)

    def __call__(self):
        self.logger.error('APPLICATION_SHUTDOWN')

