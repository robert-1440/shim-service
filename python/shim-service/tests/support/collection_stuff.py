from functools import cmp_to_key
from typing import Any, Callable, Iterable, List


def sort(collection: Iterable[Any], comparator: Callable[[Any, Any], int]) -> List[Any]:
    """
    Convenience function that will sort the given collection using the given comparator.

    :param collection: the collection to sort.
    :param comparator:  the comparator to use.
    :return: the sorted list.
    """
    return sorted(collection, key=cmp_to_key(comparator))


def binary_search(entries: List[Any], key: Any, comparator: Callable[[Any, Any], int]) -> int:
    low = 0
    high = len(entries) - 1

    while low <= high:
        mid = low + (high - low) // 2
        entry = entries[mid]
        result = comparator(key, entry)
        if result == 0:
            return mid
        if result > 0:
            low = mid + 1
        else:
            high = mid - 1
    return -1
