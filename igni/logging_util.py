from logging import config
import logging
from logging.handlers import QueueHandler
from .settings import Settings
import sqlite3
import pandas
import time


DEFAULT_LOGGING_SETTINGS = {
    # TODO
}


class Configurer:

    def __init__(self, settings: Settings):
        self.settings = settings

    def configure(self):
        config.dictConfig(self.settings)

    def __call__(self):
        self.configure()


class IgniQueueHandler(QueueHandler):

    def __init__(self, queue):
        QueueHandler.__init__(self, queue)

    def prepare(self, record):
        """
        put to the queue as is
        """
        return record


class DatabaseHandler(logging.Handler):

    LOG_ATTRIBUTE_TO_DB = {
        'asctime': 'timestamp',
        'levelname': 'level',
        'process': 'process_id',
        'thread': 'thread_id',
        'name': 'logger',
        'filename': 'filename',
        'funcName': 'function',
        'lineno': 'line',
        'msg': 'message'
    }

    def __create_table_name_for_session__(self):
        return 'session_' + str(time.time())

    def __init__(self, connection_path=None):

        logging.Handler.__init__(self)
        self.connection = None
        self.log_data = []
        self.table_name = self.__create_table_name_for_session__()
        if connection_path is not None:
            self.connection = sqlite3.connect(connection_path)

    def setConnectionPath(self, connection_path):
        self.connection = sqlite3.connect(connection_path)

    def _prepare_db_entry_from_record(self, record: logging.LogRecord):

        db_entry = {}

        for key, value in self.LOG_ATTRIBUTE_TO_DB.items():
            db_entry[value] = str(getattr(record, key))

        for name in record.__dict__:
            if not name.startswith('_') and not name in self.LOG_ATTRIBUTE_TO_DB:
                if type(record.__dict__[name] == str):
                    db_entry[name] = str(record.__dict__[name])

        return db_entry

    def emit(self, record):

        entry = self._prepare_db_entry_from_record(record)
        self.log_data.append(entry)

        if 'APPLICATION_SHUTDOWN' in entry['message']:
            pandas.DataFrame(self.log_data).to_sql(self.table_name, self.connection, if_exists='append', index=False)
            self.log_data = []


def getMLogger(name: str, global_events_queue):

    """
    get a logger for a multiprocess application (sends logs to a shared queue)
    """

    if global_events_queue is None:
        raise Exception("can't configure logger for process because logging queue was not supplied")
    queue_handler = IgniQueueHandler(global_events_queue)
    logger = logging.getLogger(name)
    logger.setLevel(logging.ERROR)
    logger.addHandler(queue_handler)

    return logging.LoggerAdapter(logger, {'source_mdb': None, 'node': None})
