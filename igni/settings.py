import yaml


def force_type(type_hint, prop_value):

    # only a subset of values allowed
    if isinstance(type_hint, set):
        allowed_set = type_hint
        if prop_value not in allowed_set:
            raise ValueError('value not in set of allowed values')
        else:
            return prop_value

    # boolean also needs special handling
    elif type_hint is bool:
        if type(prop_value) is str:
            if prop_value.lower() in ['yes', 'y', '1', 'true', 't']:
                return True
            elif prop_value.lower() in ['no', 'n', '0', 'false', 'f']:
                return False
            else:
                raise ValueError('cannot parse boolean value from string "{}"'.format(prop_value))
        else:
            return bool(prop_value)

    # some other combination of types that are not equal
    else:
        try:
            return type_hint(prop_value)
        except Exception as e:
            raise ValueError('error while trying to convert from "{}" to "{}"'.format(type(prop_value), type_hint))


class Settings(dict):

    def __init__(self, data={}):
        super().__init__()
        self.read_dict(data)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise KeyError('missing required property "{}"'.format(key))

    def __get_type_hint_else_empty__(self):
        if self.type_hint is None:
            return {}
        else:
            return self.type_hint

    def get(self, key, **kwargs):
        property_path = key.split('.')
        result = self

        try:
            for key in property_path:
                if type(result) is not type(self):
                    raise KeyError('property "{}" does not exist'.format(key))
                result = result[key]
        except KeyError as ke:
            if 'default' in kwargs:
                return kwargs['default']
            else:
                raise ke

        return result

    def using_type_hint(self, type_hint):

        def recursive_force_type_hint(settings, type_hint):
            SETTINGS = type(self)

            if settings is None or type_hint is None or len(settings) == 0 or len(type_hint) == 0:
                return
            for key in type_hint:
                if key not in settings:
                    return
                if type(settings[key]) is SETTINGS and type(type_hint[key]) is SETTINGS:
                    recursive_force_type_hint(settings[key], type_hint[key])
                elif type(settings[key]) is not SETTINGS and type(type_hint[key]) is not SETTINGS:
                    settings[key] = force_type(type_hint[key], settings[key])

        recursive_force_type_hint(self, type_hint)

        return self

    def read_dict(self, dict_: dict):
        for key in dict_.keys():
            if isinstance(dict_[key], dict):
                if key in self and isinstance(self[key], type(self)):
                    self[key].read_dict(dict_[key])
                else:
                    self[key] = type(self)(dict_[key])
            else:
                self[key] = dict_[key]

        return self

    def read_props(self, props: dict):
        deep_from_shallow = {}

        for key in props:
            parts = key.split('.')

            if len(parts) == 1:
                deep_from_shallow[parts[0]] = props[key]
                continue

            current_level = deep_from_shallow.get(parts[0], None)
            if current_level is None:
                deep_from_shallow[parts[0]] = {}
                current_level = deep_from_shallow[parts[0]]

            for part in parts[1:len(parts)-1]:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

            current_level[parts[len(parts)-1]] = props[key]

        return self.read_dict(deep_from_shallow)

    def read_cmd_args(self, cmd_args):
        return self.read_props({arg_name: arg_val for arg_name, arg_val in [cmd_arg.split('=') for cmd_arg in cmd_args]})

    def read_yaml(self, path):
        with open(path, 'r') as stream:
            return self.read_dict(yaml.safe_load(stream))
