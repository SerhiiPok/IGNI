import yaml


class Settings:

    """
    this is a utility class for settings
    usage: TODO
    """

    @classmethod
    def from_yaml(cls, fpath):
        data = yaml.load(fpath)
        return Settings(data)

    @classmethod
    def from_cmd_args(cls, cmd_args):
        settings = Settings()

        for cmd_arg in cmd_args:
            key_and_value = cmd_arg.split('=')
            if len(key_and_value) != 2:
                raise Exception('invalid command line setting: "{}"'.format(cmd_arg))

            key = key_and_value[0]
            while key.startswith('-'):
                key = key[1:]

            val = key_and_value[1]

            settings.set(key, val)

        return settings

    def __init__(self, settings={}):
        self._settings: dict = settings

    def _get_path(self, setting_name) -> dict:
        path = setting_name.split('.')

        if len(path) == 1:  # this is a setting in the root
            return self._settings

        current_node = self._settings.get(path[0], None)
        for i in range(1, len(path)-1):
            if current_node is not None:
                current_node = current_node.get(path[i], None)
        return current_node

    def _create_path(self, setting_name) -> dict:
        path = setting_name.split('.')
        current_node = self._settings
        for i in range(0, len(path)-1):
            if path[i] not in current_node:
                current_node[path[i]] = {}
            current_node = current_node[path[i]]
        return current_node

    def _setting_name(self, setting_name) -> str:
        path = setting_name.split('.')
        return path[len(path)-1]

    def set(self, setting_path, setting_value):
        setting_name = self._setting_name(setting_path)
        pth = self._get_path(setting_path)
        if pth is None:
            pth = self._create_path(setting_path)
        pth[setting_name] = setting_value
        return self

    def get(self, setting_path, default=None):
        pth = self._get_path(setting_path)
        setting_name = self._setting_name(setting_path)
        if ((pth is None) or (setting_name not in pth)) and (default is None):
            raise Exception('missing required property "{}"'.format(setting_path))
        elif (pth is None) or (setting_name not in pth):
            return default
        else:
            val = pth[self._setting_name(setting_path)]
            if isinstance(val, dict):
                return Settings(val)
            else:
                return val
