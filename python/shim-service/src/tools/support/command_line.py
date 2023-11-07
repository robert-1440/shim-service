import os
import re
import sys
from typing import Optional, List, Callable, Tuple, Union, Any, Dict, Iterable

from tools.support import utils
from tools.support.utils import is_not_empty


class CommandLineException(Exception):
    def __init__(self, message: str):
        super(CommandLineException, self).__init__(message)
        self.message = message


class PropertySet:
    def __init__(self, source: Dict[str, Any], usage_func: Callable):
        self.__source = source
        self.__usage_func = usage_func

    def __getitem__(self, item):
        return self.get_required(item)

    def get(self, key: str, default_value: Union[str, Callable] = None) -> Optional[str]:
        v = self.__source.get(key.lower())
        if v is None and default_value is not None:
            v = default_value if not callable(default_value) else default_value()

        return v

    def get_required(self, key: str, transformer: Callable[[str], Any] = None) -> Any:
        v = self.get(key.lower())
        if v is None:
            self.__usage_func(f"Missing required setting: {key}.")
            exit(2)
        if transformer is not None:
            try:
                v = transformer(v)
            except Exception as ex:
                self.__usage_func(f"Invalid value for {key}: {v} - {ex}.")
                exit(2)

        return v


def set_env(name_and_value: str):
    """
    Sets the environment variable for the given name and value.

    Example: AWS_PROFILE=local

    If there is no value, the variable is removed.
    i.e. AWS_PROFILE= results in the variable being removed.

    :param name_and_value: the NAME=VALUE to set.

    :raises ValueError: if the name and value is not properly formatted (key=value)
    """
    if name_and_value is None:
        return
    index = name_and_value.find('=')
    if index < 1:
        raise ValueError(f"Expecting name=value formatted.")
    name = name_and_value[0:index:].strip()
    value = name_and_value[index + 1::]
    if len(value) == 0:
        if name in os.environ:
            del os.environ[name]
    os.environ[name] = value


def _check_env_args(argv: List[str], env_name: str) -> List[str]:
    argv = list(argv)
    if env_name is not None:
        cmd = os.environ.get(env_name)
        if is_not_empty(cmd):
            print(f"NOTE: Appending args from environment variable {env_name}.")
            cmds = re.findall(r"(\w[\w']*\w|\w)", cmd)
            argv.extend(cmds)
    return argv


class CommandLineProcessor:
    """
    Contains useful command line parsing utility methods.
    """

    def __init__(self, usage_func=None, easy_usage_func=None, param_config: Optional[dict] = None,
                 argv: List[str] = None,
                 args_env_name: str = None,
                 env_switch_name: str = None,
                 no_help: bool = False):
        """
        Creates a new command line reader.

        :param usage_func: the function to call to invoke the usage
        :param easy_usage_func: a function that accepts argv[0] as an argument
        :param argv: arguments to use instead of sys.argv
        :param args_env_name: name of environment variable to look for additional arguments
        :param env_switch_name: name of environment variable setting switch (i.e. --env or -D, etc.) Used to set
        :param no_help: set to True to not check for --help.
        environment variables.  Example: --env AWS_PROFILE=local
        """
        if argv is None:
            self.argv = _check_env_args(sys.argv, args_env_name)
        else:
            self.argv = list(argv)
        self.count = len(self.argv)
        self.index = 1
        self.usage_func = usage_func
        self.easy_usage_func = easy_usage_func
        self.us = os.path.basename(self.argv[0])
        self.param_config = param_config
        self.auto_exit = argv is None
        if env_switch_name:
            self.process_env_switches(env_switch_name)
        if not no_help and "--help" in self.argv and (usage_func or easy_usage_func):
            self.invoke_usage()

    def assert_args(self, *args):
        index = self.index
        for arg in args:
            if index == self.count:
                self.__fail(arg)
            index += 1
        if index < self.count:
            self.invoke_usage_with_bad_arg(self.argv[index])

    def skip_args(self, *args):
        for arg in args:
            if self.index == self.count:
                self.__fail(arg)
            self.index += 1

    def has_next_optional_switch(self, switch_name: str) -> bool:
        if self.index == self.count:
            return False
        arg = self.get_next_arg()
        if arg == switch_name:
            return True
        self.invoke_usage_with_bad_arg(arg)
        return False

    def find_and_remove_arg_plus_int(self, name: str, default_value: int = None) -> Optional[int]:
        """
        Looks for the command line argument that matches the given name and removes it along with the following
        argument.

        :param name: the name to look for.
        :param default_value: the default value to use if not found.
        :returns: the argument after the named argument as an int if found, otherwise default_value.
        """

        result = self.find_and_remove(name, 1)
        if result:
            r = result[0]
            if r.isdigit():
                return int(r)
            self.invoke_usage(f"{name} must be specified with an integer value (vs {r}).")
        return default_value

    def find_and_remove_arg_plus_1(self, name: str, default_value: str = None) -> Optional[str]:
        """
        Looks for the command line argument that matches the given name and removes it along with the following
        argument.

        :param name: the name to look for.
        :param default_value: the default value to use if not found.
        :returns: the argument after the named argument if found, otherwise default_value.
        """

        result = self.find_and_remove(name, 1)
        if result:
            return result[0]
        return default_value

    def find_and_remove(self, name: str, extra_number_of_args: int = 0) -> Union[bool, Tuple]:
        """
        Looks for the command line argument that matches the given name and removes it.

        :param name: the name to look for.
        :param extra_number_of_args: if > 0, the number of additional arguments after the argument found is also removed.
        :returns: True if found and extra_number_of_args is 0. If extra_number_of_args is > 0, then a tuple of the extra args
        removed. False if the argument was not found.
        """

        remove_at = None
        for i in range(self.index, len(self.argv)):
            v = self.argv[i]
            if v == name:
                remove_at = i
                break

        if remove_at is None:
            return False
        counter = 0
        captured = [] if extra_number_of_args > 0 else True
        while self.count > remove_at:
            v = self.argv[remove_at]
            del self.argv[remove_at]
            self.count -= 1
            if counter > 0:
                captured.append(v)
            if counter == extra_number_of_args:
                break
            counter += 1

        if extra_number_of_args > 0:
            if len(captured) != extra_number_of_args:
                self.invoke_usage()
            return tuple(captured)
        return captured

    def find_and_remove_args(self, name: str, num_args: int) -> Tuple:
        """
        Looks for the command line argument that matches, plus the given number of arguments after.

        Example:
        given: --opt a b c
        calling: find_and_remove_args("--opt", 3) would return ('a','b','c')
        calling: find_and_remove_args("--other", 3) would return None

        :param name: the name to look for.
        :param num_args: the number of additional arguments after the argument found is also removed.
        :returns: A tuple of none values if the argument did not exist.  Otherwise, the tuple of argument values after the argument.
        """
        assert num_args > 0
        v = self.find_and_remove(name, num_args)
        if type(v) is bool:
            return tuple(map(lambda a: None, range(num_args)))
        return v

    def pre_process(self, arg_name: str, caller: Callable):
        """
        Can be used to look for argument switches that appear before expected arguments.
        :param arg_name: the value ot look for in the arguments, such as "--env"
        :param caller: the callable to call if there is an argument match. The processor is passed into the caller.
        """
        while self.has_more():
            arg = self.peek()
            if arg == arg_name:
                self.index += 1
                caller(self)
            else:
                break

    def process_env_switches(self, switch_name: str = "--env"):
        """
        A convenience method to look for --env NAME=VALUE settings on the command line and apply them
        to the os.environ dictionary.

        :param switch_name: The switch name (i.e. --env, -D, etc)
        """
        while True:
            value = self.find_and_remove_arg_plus_1(switch_name)
            if value is None:
                break
            set_env(value)

    def peek(self) -> Optional[str]:
        if self.index == self.count:
            return None
        return self.argv[self.index]

    def skip(self, numargs=1, expected_name=None):
        """
        Skip command line arguments.

        :param numargs:int number of arguments to skip.
        :param expected_name:str the name of the argument that is expected
        """
        if self.index + numargs > self.count:
            self.__fail(expected_name)
        self.index += numargs

    def skip_next_arg(self, expected_name=None):
        """
        Skip the next command line argument.

        :param expected_name: the name to include in the error message if there are no more arguments.
        """
        self.skip(expected_name=expected_name)

    def invoke_usage_with_bad_arg(self, arg):
        """
        Invokes the usage function. The message will include the given argument.
        :param arg:str the argument name
        """
        if arg == "--help":
            self.invoke_usage()
        self.invoke_usage(f"Unrecognized command line argument: '{arg}'")

    def invoke_usage(self, message=None):
        """
        Invokes the usage function with the given message.

        :param message:str the message to include when invoking the usage function
        """
        if self.easy_usage_func is not None or self.usage_func is not None:
            if message is not None:
                print(message, file=sys.stderr)
            if self.easy_usage_func:
                self.easy_usage_func(f"Usage: {self.us}")
            else:
                if type(self.usage_func) is str:
                    print(f"{self.usage_func}", file=sys.stderr)
                    exit(2)
                else:
                    self.usage_func()
        elif self.param_config:
            self.__do_param_usage()
        if self.auto_exit:
            exit(2)

    def get_remaining_args(self) -> List[str]:
        if self.index == self.count:
            return []
        arr = self.argv[self.index::]
        self.index = self.count
        return arr

    def get_remaining_props(self, prop_set: Iterable[str]) -> PropertySet:
        if isinstance(prop_set, dict):
            prop_set = prop_set.values()
        prop_set = set(map(lambda k: k.lower(), prop_set))

        def split_two(s: str) -> Tuple[str, str]:
            index = s.find('=')
            if 0 < index < len(s) - 1:
                k = s[0:index:].lower()
                v = s[index + 1::]
                if k not in prop_set:
                    self.invoke_usage(f"Invalid argument: {s}")
                return k, v
            self.invoke_usage(f"Invalid command-line argument: {s}. Expecting key=value.")

        props = {}
        while self.has_more():
            name, value = split_two(self.get_next_arg())
            props[name] = value
        return PropertySet(props, self.invoke_usage)

    def __do_param_usage(self):

        def get_arg_name(arg_config: dict, name: str):
            sn = arg_config.get("subname")
            if sn is not None:
                name += sn
            return name

        max_name_len = 0
        print(f"Usage: {utils.get_our_file_name()}", end="", file=sys.stderr)
        for k, v in self.param_config.items():
            arg = get_arg_name(v, k)
            max_name_len = max(max_name_len, len(arg))
            if not v.get("required"):
                print(f" [{arg}]", end="", file=sys.stderr)
            else:
                print(f" {arg}", end="", file=sys.stderr)

        print("\n", file=sys.stderr)
        fmt = f"{{:>{max_name_len}s}}"
        for k, v in self.param_config.items():
            arg = get_arg_name(v, k)
            name_fmt = fmt.format(arg)
            print(f"\t{name_fmt}: {v['usage']}", file=sys.stderr)
        if self.auto_exit:
            exit(2)

    def __fail(self, expected_name=None):
        if expected_name is not None:
            message = f"Expected '{expected_name}' to be passed to the command line"
        else:
            message = None
        self.invoke_usage(message)
        raise CommandLineException(message)

    def get_next_arg_as_float(self, expected_name=None) -> float:
        arg = self.get_next_arg(expected_name)

        try:
            return float(arg)
        except Exception:
            self.invoke_usage(f"{arg} is not a valid float value.")

    def get_next_arg_as_int(self, expected_name=None) -> int:
        arg = self.get_next_arg(expected_name)
        try:
            return int(arg)
        except Exception:
            if expected_name is not None:
                raise CommandLineException(f"Invalid integer for {expected_name}: {arg}")

            else:
                raise CommandLineException(f"Invalid integer: {arg}")

    def get_next_args(self, *args) -> tuple:
        result = ()
        for arg in args:
            value = self.get_next_arg(arg)
            result += (value,)
        return result

    def get_next_args_as_dict(self, *args) -> dict:
        result = {}
        arg_type = None
        for arg in args:
            if isinstance(arg, type):
                if arg_type is not None:
                    raise SyntaxError("More than one concurrent type specified")
                arg_type = arg
            elif type(arg) is str:
                v = self.get_next_arg(arg)
                if arg_type is not None:
                    v = arg_type(v)
                    arg_type = None
                result[arg] = v
            else:
                raise SyntaxError(f"Unrecognized argument: {arg}")
        if arg_type is not None:
            raise SyntaxError(f"Type ({arg_type}) specified with no argument name")
        return result

    def get_next_arg(self, expected_name=None) -> str:
        """
        Returns the next argument.  If there are no more arguments, the usage function is called.

        :param expected_name: the name of the expected argument.
        :return:str the next argument
        """
        if self.index == self.count:
            self.__fail(expected_name)
        arg = self.argv[self.index]
        self.index += 1
        return arg

    def get_next_arg_as_filename(self, expected_name=None) -> str:
        """
        Returns the next argument, checking for ~ and replacing it with the home path.

        :param expected_name: the name of the expected argument.
        :return:str the next argument
        """
        n = self.get_next_arg(expected_name)
        return utils.check_home_in_path(n)

    def skip_next_arg_if_equal_to(self, arg):
        """
        Skips the next argument if it is equal to the given arg.

        :param arg:str the argument name
        :return:bool True if the argument was skipped.
        """
        if self.index < self.count:
            v = self.argv[self.index]
            if v == arg:
                self.index += 1
                return True

        return False

    def assert_no_more(self):
        """
        Used to ensure there are no more command line arguments.  If so, the usage function is called with
        the next argument.
        """
        if self.has_more():
            arg = self.get_next_arg()
            self.invoke_usage(f"Unexpected argument '{arg}'")

    def assert_has_more(self):
        """
        Used to ensure there are more arguments.
        """
        if not self.has_more():
            self.invoke_usage()

    def has_more(self):
        """
        Whether there are more command-line arguments.

        :return:bool True if there are more command line arguments.
        """
        return self.index < self.count

    @staticmethod
    def __convert_value(arg_config: dict,
                        key_name: str,
                        value: str,
                        arg_collector: dict):
        t = arg_config.get('type')
        if t is not None:
            value = t(value)
        handler = arg_config.get('handler')
        if handler is not None:
            if t is None:
                v = arg_config.get('handler_arg')
                if v is not None:
                    handler(v)
                else:
                    handler()
            else:
                handler(value)
        else:
            if key_name.endswith("="):
                key_name = key_name[0:len(key_name) - 1:]
            arg_collector[key_name] = value

    def process_configured_args(self) -> dict:
        unhandled_args = {}
        if self.index != 1:
            raise Exception("Can't call this now.")

        if self.param_config is None:
            raise Exception("No param config provided")

        for k, v in self.param_config.items():
            if v.get("required"):
                self.__convert_value(v, k, self.get_next_arg(k), unhandled_args)

        while self.has_more():
            key = arg = self.get_next_arg()
            arg_config = self.param_config.get(arg)
            if arg_config is None:
                idx = arg.rfind("=")
                if idx > 0:
                    nkey = arg[0:idx + 1:]
                    arg_config = self.param_config.get(f"{nkey}")
                    if arg_config is not None:
                        arg = arg[idx + 1::]
                if arg_config is None:
                    self.invoke_usage_with_bad_arg(arg)

            self.__convert_value(arg_config, key, arg, unhandled_args)
        return unhandled_args


def get_arg_from_command_line(usage: Callable, arg_name: str) -> str:
    """
    Used to retrieve the single argument from the command line.

    :param usage: the usage function to call if there is no argument.
    :param arg_name: the name of the argument (used in case no argument is provided).
    :returns: the argument value.
    """
    cli = CommandLineProcessor(usage)
    result = cli.get_next_arg(arg_name)
    cli.assert_no_more()
    return result


def get_args_from_command_line(usage: Callable, *args) -> Tuple:
    """
    Used to retrieve the exact number of command-line arguments.

    :param usage: the usage function to call in the event that not all arguments are present, or there are too many.
    :param args: the names of the arguments.
    :returns: a Tuple of the argument values.

    """
    results = []
    cli = CommandLineProcessor(usage)
    for arg_name in args:
        results.append(cli.get_next_arg(arg_name))
    cli.assert_no_more()
    return tuple(results)
