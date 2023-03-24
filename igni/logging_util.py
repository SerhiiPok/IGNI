from logging import config
import logging
from .settings import Settings
import sqlite3
import pandas


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


class DatabaseHandler(logging.Handler):

    def __init__(self, connection_path=None):
        logging.Handler.__init__(self)
        self.connection = None
        self.log_data = []
        if connection_path is not None:
            self.connection = sqlite3.connect(connection_path)

    def setConnectionPath(self, connection_path):
        self.connection = sqlite3.connect(connection_path)

    def emit(self, record):

        dt = {
            'timestamp': record.created,
            'level': record.levelname,
            'process_id': record.process,
            'thread_id': record.thread,
            'logger': record.name,
            'file': record.filename,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.msg,
            'args': str(record.args)
        }

        self.log_data.append(dt)

        if 'APPLICATION_SHUTDOWN' in dt['message']:
            pandas.DataFrame(self.log_data).to_sql('log', self.connection, if_exists='append', index=False)
            self.log_data = []
