from typing import Any, Tuple, Collection, Optional, Callable, Iterable, TypeVar, Generic, List, Iterator

EMPTY_TUPLE = tuple()
T = TypeVar("T")
O = TypeVar("O")


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


class BufferedList(Generic[T], Iterable[T]):
    def __init__(self, max_size: int, flusher: Callable[[List[T]], None]):
        self.__max_size = max_size
        self.__flusher = flusher
        self.__source = []

    def add(self, obj: T):
        if len(self.__source) == self.__max_size:
            self.flush()
        self.__source.append(obj)

    def add_all(self, obj_list: Iterable[T]):
        if not isinstance(obj_list, list):
            for obj in obj_list:
                self.add(obj)
            return
        left = len(obj_list)
        start = 0
        while left > 0:
            if len(self.__source) == self.__max_size:
                self.flush()
            count = min(left, self.__max_size - len(self.__source))
            self.__source.extend(obj_list[start:start + count])
            left -= count
            start += count

    def flush(self):
        if len(self.__source) > 0:
            self.__flusher(list(self.__source))
            self.__source.clear()

    def __len__(self):
        return len(self.__source)

    def __iter__(self):
        return self.__source.__iter__()


class __TransformerIterator(Generic[T, O], Iterable[O]):
    def __init__(self, source: Iterable[T], transformer: Callable[[T], O]):
        self.__source = source
        self.__source_iter: Optional[Iterator] = None
        self.__transformer = transformer
        self.__transformed_iterator: Optional[Iterator] = None

    def __iter__(self):
        self.__source_iter = iter(self.__source)
        return self

    def __next__(self):
        if self.__transformed_iterator is not None:
            try:
                return next(self.__transformed_iterator)
            except StopIteration:
                self.__transformed_iterator = None
        self.__transformed_iterator = iter(self.__transformer(next(self.__source_iter)))
        return self.__next__()


def flat_iterator(source: Iterable[T], transformer: Callable[[T], Iterable[O]]) -> Iterable[O]:
    """
    Used to create an iterator that will transform each object in the given source using the given transformer.
    The transformer should return an iterable.

    :param source: the source iterable.
    :param transformer: the transformer to call.
    :return: an iterable that can be used to iterate over the transformed objects.
    """
    return __TransformerIterator(source, transformer)


def to_collection(thing: Any) -> Collection:
    """
    Ensure the given thing is a collection and return one if it is not.

    :param thing: the thing
    :return: the thing as a collection
    """
    if thing is not None:
        if not isinstance(thing, Collection):
            return (thing,)
        if len(thing) == 0:
            return None
    return thing
