"""
algorithms.py — Part 2: hand-written sort and search algorithms.

IMPORTANT: No built-in sorted(), list.sort(), or any imported
search/sort utility is used anywhere in this file.
"""

# ---------------------------------------------------------------------------
# 1. Insertion Sort (descending by a numeric key)
# ---------------------------------------------------------------------------

def insertion_sort_by_key(items: list[dict], key: str) -> list[dict]:
    """
    Sort a list of dicts in DESCENDING order by a numeric key.

    Algorithm:
      - Outer loop: walk each element from index 1 onward (the "current" item).
      - Inner backward-swap loop: move the current element left until it finds
        its correct position (i.e., until the element to its left is >= it).

    No built-in sort of any kind.
    """
    # Work on a shallow copy so the original list is not mutated
    arr = list(items)
    n = len(arr)

    for i in range(1, n):
        current = arr[i]
        j = i - 1
        # Shift elements that are SMALLER than current one position to the right
        # (gives descending order)
        while j >= 0 and arr[j][key] < current[key]:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = current

    return arr


# ---------------------------------------------------------------------------
# 2. Binary Search — Iterative
# ---------------------------------------------------------------------------

def binary_search_iterative(sorted_titles: list[str], target: str) -> int:
    """
    Return the index of `target` in an already-sorted (A→Z) list of titles,
    or -1 if absent.

    Uses the overflow-safe midpoint: start + (end - start) // 2
    Implemented iteratively (no recursion).
    """
    start = 0
    end = len(sorted_titles) - 1

    while start <= end:
        mid = start + (end - start) // 2
        mid_val = sorted_titles[mid]

        if mid_val == target:
            return mid
        elif mid_val < target:
            start = mid + 1
        else:
            end = mid - 1

    return -1


# ---------------------------------------------------------------------------
# 3. Binary Search — Recursive
# ---------------------------------------------------------------------------

def binary_search_recursive(
    sorted_titles: list[str],
    target: str,
    start: int,
    end: int,
) -> int:
    """
    Recursive binary search on an already-sorted list of titles.
    Base case: start > end → return -1 (target not found).
    """
    # Base case
    if start > end:
        return -1

    mid = start + (end - start) // 2
    mid_val = sorted_titles[mid]

    if mid_val == target:
        return mid
    elif mid_val < target:
        return binary_search_recursive(sorted_titles, target, mid + 1, end)
    else:
        return binary_search_recursive(sorted_titles, target, start, mid - 1)


# ---------------------------------------------------------------------------
# 4. Linear Search with found-flag pattern
# ---------------------------------------------------------------------------

def linear_search(items: list[dict], key: str, value) -> dict | None:
    """
    Scan a list sequentially using an explicit found-flag pattern.
    Returns the first dict whose `key` matches `value`, or None.
    """
    found = False
    result = None

    for item in items:
        if item.get(key) == value:
            found = True
            result = item
            break          # stop at the first match

    if found:
        return result
    return None
