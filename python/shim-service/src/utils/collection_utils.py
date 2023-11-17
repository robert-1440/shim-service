from typing import Any, Tuple, Collection, Optional, Callable, Iterable

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


def partition(collection: Iterable[Any], partition_size: int,
              transformer: Callable[[Any], Any] = None) -> Iterable[Iterable[Any]]:
    """
    Used to partition the given iterable into a list of lists, with each list being no larger than partition_size.
    :param collection: the collection to split.
    :param partition_size: the max size of each list.
    :param transformer: optional transformer to use for each object.
    :return: the list of lists.
    """
    assert partition_size > 0
    if isinstance(collection, list):
        if len(collection) <= partition_size:
            return [collection]
        if transformer is None:
            return [collection[i:i + partition_size] for i in range(0, len(collection), partition_size)]

    page = []
    page_list = []

    for obj in collection:
        if len(page) == partition_size:
            page_list.append(page)
            page = []
        if transformer is not None:
            obj = transformer(obj)
        page.append(obj)

    if len(page) > 0:
        page_list.append(page)

    return page_list
