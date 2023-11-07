import os
import pathlib
import sys
from typing import Optional, Any


def prompt_yes(message: str, exit_code_on_no: Optional[int] = None) -> bool:
    """
    Prevents us from having to add a "confirm" function every time we want to prompt the user for a "Yes".

    :param message: The message to display.  If the "?" is not in the message, then "(Yes)?" is added.
    :param exit_code_on_no: If not None, the exit code to exit with if the answer is "no".
    :return: True if the user entered "yes" (NOT case sensitive).

    """
    if "?" not in message:
        message += " (Yes)?"
    resp = input(message + " ")
    result = resp.lower() == "yes"
    if not result and exit_code_on_no is not None:
        exit(exit_code_on_no)
    return result


def is_empty(v: Any) -> bool:
    return v is None or len(v) == 0


def is_not_empty(v: Any) -> bool:
    return not is_empty(v)



def get_our_file_name():
    """
    Returns our file name.

    :return: the file name.
    """
    return os.path.basename(sys.argv[0])

def cap_first_character(text: str) -> str:
    """
    Capitalizes the first character in the given string.
    :param text: the string to capitalize.
    :returns: the capitalized text.
    """
    if is_not_empty(text) and text[0].isalpha() and not text[0].isupper():
        text = text[0].upper() + text[1::]

    return text

def get_home_path(sub_dir: str = None,
                  create_dirs: bool = False,
                  file_name: str = None):
    """
    Returns the home path, with optional sub-folder and file name.

    :param sub_dir: the sub-directory under home
    :param create_dirs: True to create sub dir if it does not exist
    :param file_name: optional file name to include in, path
    :returns: the path
    """

    folder = pathlib.Path.home()
    if sub_dir is not None:
        folder = os.path.join(folder, sub_dir)
    if create_dirs and not os.path.isdir(folder):
        os.makedirs(folder)
    if file_name is not None:
        return os.path.join(folder, file_name)
    return folder


def check_home_in_path(path: str) -> str:
    if path is not None and path.startswith("~/"):
        return get_home_path(path[2::])
    return path
