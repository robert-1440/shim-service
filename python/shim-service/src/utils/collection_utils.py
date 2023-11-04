from typing import Any, Tuple, Collection, Optional, Callable

EMPTY_TUPLE = tuple()


def to_non_none_tuple(*args) -> Tuple[Any, ...]:
    """
    Creates a tuple from the given arguments, filtering out None values.

    :param args: the args.
    :return: the tuple.
    """
    return tuple(filter(lambda n: n is not None, args))


def to_flat_list(*args):
    new_list = []
    for arg in args:
        if type(arg) in (tuple, list):
            new_list.extend(arg)
        else:
            new_list.append(arg)
    return new_list


def find_first_match(collection: Collection[Any], matcher: Callable[[Any], bool]) -> Optional[Any]:
    for entry in filter(matcher, collection):
        return entry
    return None
