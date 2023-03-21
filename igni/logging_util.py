from logging import Logger as Logger_, Formatter, FileHandler, StreamHandler, config
from typing import Any
from .settings import Settings


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


# custom logger class for the igni modules
class IgniLogger(Logger_):

    LOGGING_SETTINGS_TEMPLATE = Settings({
        'level': {'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'},
        'appender': {
            'type': {'STDOUT', 'FILE'},
            'output-file': str,
            'output-file-writing-mode': {'append', 'overwrite'},
            'format': str
        }
    })

    LOGGING_DEFAULT_SETTINGS = Settings({
        'level': 'INFO',
        'appender': {
            'type': 'STDOUT',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    })

    def __init__(self, name: str, settings: Settings = Settings()):
        super().__init__(name, 'DEBUG')

        # -- logging settings
        self.settings = self.LOGGING_DEFAULT_SETTINGS
        if len(settings) > 0:
            self.settings.read_dict(settings).using_type_hint(self.LOGGING_SETTINGS_TEMPLATE)

        self.setLevel(self.settings['level'])
        logging_formatter = Formatter(self.settings['appender']['format'])
        handler = None

        if self.settings['appender']['type'] == 'FILE':
            handler = FileHandler(
                self.settings['appender']['output-file'],
                'a' if self.settings['appender']['output-file-writing-mode'] == 'append' else 'w'
            )
        elif self.settings['appender']['type'] == 'STDOUT':
            handler = StreamHandler()

        handler.setLevel(self.settings['level'])
        handler.setFormatter(logging_formatter)
        self.addHandler(handler)
        # --

        self.context = {}  # arbitrary key-value pairs describing logging context, are written in the logged message
        self.input_file = None  # optional path to a file associated with an igni process, is written in the logged message

    def __decorate_message_with_context_info__(self, message):

        message_object = {'msg': message}

        if self.input_file is not None:
            message_object['input'] = str(self.input_file)

        if self.context is not None and isinstance(self.context, dict):
            message_object['context'] = self.context

        return str(message_object)

    def debug(self, msg: Any, *args: Any, **kwargs: Any):
        super().debug(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any):
        super().info(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any):
        super().warning(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

    def warn(self, msg: Any, *args: Any, **kwargs: Any):
        super().warn(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any):
        super().error(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any):
        super().critical(self.__decorate_message_with_context_info__(msg), *args, **kwargs)

