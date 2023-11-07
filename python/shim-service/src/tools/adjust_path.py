import os
import sys

dir_name = os.path.dirname(os.path.realpath(__file__)) + "/.."

real_path = os.path.realpath(dir_name)
sys.path.insert(0, real_path)


def get_our_file_name():
    """
    Returns our file name.

    :return: the file name.
    """
    return os.path.basename(sys.argv[0])
