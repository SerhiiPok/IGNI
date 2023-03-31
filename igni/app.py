from .logging_util import get_interprocess_queue_logger
from multiprocessing import Queue, Process, Manager, cpu_count, current_process
from concurrent.futures import ProcessPoolExecutor
from .settings import Settings
import logging
import sqlite3
from threading import Thread
import pandas
from .resources import ResourceManager, Directory
import os.path
import time
import math


class PersistenceTask:

    def __init__(self, table_name: str, dataset: pandas.DataFrame):
        self.table_name = table_name
        self.dataset = dataset


class IgniApplicationReference:

    def __init__(self):
        self._logging_queue = None
        self._application_events_queue = None
        self._persistence_events_queue = None

    def submit_task(self, task):

        if isinstance(task, PersistenceTask):
            self.submit_persistence_task(task)
        elif isinstance(task, IgniApplicationEntity):
            self._application_events_queue.put(task)
        else:
            raise Exception("task submitted to application must be an application entity or a persistence task")

    def submit_persistence_task(self, task: PersistenceTask):
        self._persistence_events_queue.put(task)

    def persist_data(self, table_name: str, dataset: pandas.DataFrame):
        self.submit_persistence_task(PersistenceTask(table_name, dataset))


_Application: IgniApplicationReference = None


def _set_up_app_reference_for_child_process(logging_queue: Queue,
                                            application_events_queue: Queue,
                                            application_db_events_queue: Queue):
    global _Application
    _Application = IgniApplicationReference()
    _Application._logging_queue = logging_queue
    _Application._application_events_queue = application_events_queue
    _Application._persistence_events_queue = application_db_events_queue


def Application():
    if _Application is None:
        raise Exception('application not configured for process {}'.format(current_process().pid))
    return _Application


class IgniApplication:

    class ChildProcessApplicationInitializer:

        def __init__(self, logging_queue, application_events_queue, application_db_events_queue):
            self.logging_queue = logging_queue
            self.application_events_queue = application_events_queue
            self.application_db_events_queue = application_db_events_queue

        def __call__(self):
            _set_up_app_reference_for_child_process(self.logging_queue,
                                                    self.application_events_queue,
                                                    self.application_db_events_queue)

    def __init__(self, application_settings: Settings):

        self._logging_queue: Queue = None                            # queue accepting logging events
        self._application_events_queue: Queue = None                 # queue accepting application events
        self._application_shutdown_queue: Queue = None               # queue accepting application shutdown event
        self._application_db_events_queue: Queue = None              # queue accepting db-related tasks

        self._global_logger_process: Process = None                  # process that handles logs
        self._persistence_task_listener_process: Process = None      # process that handles saving to db
        self._application_event_dispatcher_thread: Thread = None     # application events dispatcher
        self._task_executor: ProcessPoolExecutor = None              # application events executor

        self._running_tasks = []                                     # keep track of tasks currently executed

        self._application_settings = application_settings
        self._available_task_processes: int = None

        self._logger = None
        self._application_reference: IgniApplicationReference = None

        self._IDLE_TIME_SHUTDOWN = 5                                 # idle time after which application shuts down
        self._initiation_time = time.time()

        self.resource_manager = None

        self._initialize()

    @property
    def logger(self):
        if self._logger is None:
            self._logger = get_interprocess_queue_logger('IgniApplication', self._logging_queue)
        return self._logger

    @property
    def application_reference(self):
        if self._application_reference is None:
            self._application_reference = IgniApplicationReference()
            self._application_reference._logging_queue = self._logging_queue
            self._application_reference._application_events_queue = self._application_events_queue
            self._application_reference._persistence_events_queue = self._application_db_events_queue
        return self._application_reference

    @staticmethod
    def _logging_events_monitoring_loop(logging_queue: Queue,
                                        application_shutdown_queue: Queue,
                                        logging_settings: dict):

        logging.config.dictConfig(logging_settings)
        shutdown_scheduled = False
        while True:
            if not application_shutdown_queue.empty():
                shutdown_scheduled = True

            if not logging_queue.empty():
                logging_event = logging_queue.get()
                logger = logging.getLogger(logging_event.name)
                logger.handle(logging_event)
            elif shutdown_scheduled:

                # this is necessary to make db handler write all logs to db...
                # logging.getLogger('IgniApplication').critical('APPLICATION_SHUTDOWN')  # TODO can't log because expects source_mdb property...
                return

    @staticmethod
    def _db_events_monitoring_loop(persistence_tasks_queue: Queue,
                                   application_shutdown_queue: Queue,
                                   conn_path: str):

        conn = sqlite3.connect(os.path.join(conn_path, 'export_meta.db'))
        shutdown_scheduled = False

        while True:
            if not application_shutdown_queue.empty():
                shutdown_scheduled = True

            if not persistence_tasks_queue.empty():
                persistence_event = persistence_tasks_queue.get()
                persistence_event.dataset.to_sql(
                    persistence_event.table_name,
                    conn,
                    if_exists='append',
                    index=False
                )
            elif shutdown_scheduled:
                conn.close()
                return

    @staticmethod
    def _application_events_monitoring_loop(app):  # pass reference to application itself, this will be rolling in a thread

        # TODO custom callbacks
        def _task_execution_callback(future):
            if future.exception():
                app.logger.error(future.exception())
            app._running_tasks.remove(future)

        application_events_queue = app._application_events_queue
        task_executor = app._task_executor
        while True:
            if not app._application_shutdown_queue.empty():
                return  # TODO correct?

            if not application_events_queue.empty():
                application_event = application_events_queue.get()
                future = task_executor.submit(application_event)
                future.add_done_callback(_task_execution_callback)
                app._running_tasks.append(future)


    def _initialize(self):

        self._logging_queue = Manager().Queue()
        self._application_events_queue = Manager().Queue()
        self._application_db_events_queue = Manager().Queue()
        self._application_shutdown_queue = Manager().Queue()

        self.logger.info('initializing processes...')

        self._global_logger_process = Process(
            target=self._logging_events_monitoring_loop,
            args=(
                self._logging_queue,
                self._application_shutdown_queue,
                self._application_settings['logging']
            )
        )
        self._persistence_task_listener_process = Process(
            target=self._db_events_monitoring_loop,
            args=(
                self._application_db_events_queue,
                self._application_shutdown_queue,
                self._application_settings['db-path']
            )
        )
        self._application_event_dispatcher_thread = Thread(
            target=self._application_events_monitoring_loop,
            args=(self,)
        )

        available_cpus = cpu_count()
        allocated_cpus = 2  # logger and application events handler processes
        self._available_task_processes = available_cpus - allocated_cpus if available_cpus - allocated_cpus > 0 else 1

        self.logger.info('initializing resource manager...')
        self.resource_manager = ResourceManager(Directory(self._application_settings['witcher-data']))

    def start(self):

        # initialize application context in child processes
        child_process_application_initializer = self.ChildProcessApplicationInitializer(
            self._logging_queue,
            self._application_events_queue,
            self._application_db_events_queue
        )

        self.logger.info('starting processes and task executor...')
        self._global_logger_process.start()
        self._persistence_task_listener_process.start()
        self._task_executor = ProcessPoolExecutor(
            max_workers=self._available_task_processes,
            initializer=child_process_application_initializer)
        self._application_event_dispatcher_thread.start()

    def _is_idle(self):
        return (self._logging_queue.empty()
                and self._application_events_queue.empty()
                and self._application_db_events_queue.empty()
                and len(self._running_tasks) == 0)

    def shutdown_on_idle(self):

        """
        blocking request to shut down
        will wait for all pending tasks to finish
        """

        shutdown_trigger = False

        while True:  # waiting for the application events to complete
            if shutdown_trigger:
                break
            elif self._is_idle():
                was_idle = time.time()
                while self._is_idle():
                    if time.time() - was_idle > self._IDLE_TIME_SHUTDOWN:
                        shutdown_trigger = True
                        break
            else:
                pass  # wait for the events to complete

        self.logger.critical('shutting down on idle...')

        elapsed_time = time.time() - self._initiation_time
        self.logger.critical('finished work in {} minutes {} seconds'.format(
            math.floor(elapsed_time/60.0),
            round(elapsed_time % 60, 3)
        ))

        self._task_executor.shutdown(wait=True)  # TODO reliable shutdown so that no tasks are lost?
        self._application_shutdown_queue.put('()')  # sending shutdown 'event'

        while True:
            try:
                self._global_logger_process.join()
                self._application_event_dispatcher_thread.join()
                self._persistence_task_listener_process.join()

                self._global_logger_process.close()
                self._persistence_task_listener_process.close()

                break
            except Exception as e:
                print(e)
                break

        return

    def submit_task(self, task):
        """
        non-blocking task execution
        """
        self.application_reference.submit_task(task)

    def submit_persistence_task(self, task):
        self.application_reference.submit_persistence_task(task)

    def persist_data(self, table_name: str, dataset: pandas.DataFrame):
        self.application_reference.persist_data(table_name, dataset)

    def execute_task(self, task):
        """
        blocking task execution
        """
        task()  # TODO


_IGNI_APPLICATION: IgniApplication = None


class IgniApplicationEntity:

    """
    a task that is executed in a separate process
    implementors must be pickleable
    """

    def __init__(self):

        self._logger = None

    @property
    def logger(self):
        global _Application  # get reference to running igni application
        if self._logger is None:
            if _Application:
                self._logger = get_interprocess_queue_logger(type(self).__name__,
                                                             _Application._logging_queue)
            else:
                raise Exception('missing reference to running igni application for process {}'.format(
                    current_process().pid
                ))
        return self._logger

    def run(self):
        raise Exception('not implemented')

    def __call__(self):
        self.run()


def start_new_application(application_settings: Settings=None):
    global _IGNI_APPLICATION
    if _IGNI_APPLICATION is None:
        _IGNI_APPLICATION = IgniApplication(application_settings)
        _IGNI_APPLICATION.start()
    return _IGNI_APPLICATION
