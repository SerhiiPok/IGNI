import multiprocessing


class AsyncTaskExecutor:

    def __init__(self):
        self.tasks = multiprocessing.Queue()
        self.process = multiprocessing.Process(target=self.main_loop)
        self.process.start()

    def _execute_pending_tasks_(self):
        if not self.tasks.empty():
            self.tasks.get()()

    def main_loop(self):
        while True:
            self._execute_pending_tasks_()

    def stop(self):
        while not self.tasks.empty():
            pass
        self.process.kill()

