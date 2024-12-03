"""
Page labels are shown by PDF viewers as "the page number".

A page has a numeric index, starting at 0. Additionally, the page
has a label. In the most simple case:

    label = index + 1

However, the title page and the table of contents might have Roman numerals as
page labels. This makes things more complicated.

Example 1
---------

>>> reader.root_object["/PageLabels"]["/Nums"]
[0, IndirectObject(18, 0, 139929798197504),
 8, IndirectObject(19, 0, 139929798197504)]
>>> reader.get_object(reader.root_object["/PageLabels"]["/Nums"][1])
{'/S': '/r'}
>>> reader.get_object(reader.root_object["/PageLabels"]["/Nums"][3])
{'/S': '/D'}

Example 2
---------
The following is a document with pages labeled
i, ii, iii, iv, 1, 2, 3, A-8, A-9, ...

1 0 obj
    << /Type /Catalog
       /PageLabels << /Nums [
                        0 << /S /r >>
                        4 << /S /D >>
                        7 << /S /D
                             /P ( A- )
                             /St 8
                        >>
                        % A number tree containing
                        % three page label dictionaries
                        ]
                   >>
    ...
    >>
endobj


§12.4.2 PDF Specification 1.7 and 2.0
=====================================

Entries in a page label dictionary
----------------------------------
The /S key:
D       Decimal Arabic numerals
R       Uppercase Roman numerals
r       Lowercase Roman numerals
A       Uppercase letters (A to Z for the first 26 pages,
                           AA to ZZ for the next 26, and so on)
a       Lowercase letters (a to z for the first 26 pages,
                           aa to zz for the next 26, and so on)
"""
from typing import Iterator, List, Optional, Tuple, cast
from ._protocols import PdfCommonDocProtocol
from ._utils import logger_warning
from .generic import ArrayObject, DictionaryObject, NullObject, NumberObject

def index2label(reader: PdfCommonDocProtocol, index: int) -> str:
    """
    See 7.9.7 "Number Trees".

    Args:
        reader: The PdfReader
        index: The index of the page

    Returns:
        The label of the page, e.g. "iv" or "4".
    """
    if "/PageLabels" not in reader.root_object:
        return str(index + 1)

    nums = reader.root_object["/PageLabels"]["/Nums"]
    label_dict = None
    start_index = 0

    for i in range(0, len(nums), 2):
        if nums[i] > index:
            break
        start_index = nums[i]
        label_dict = reader.get_object(nums[i + 1])

    if label_dict is None:
        return str(index + 1)

    style = label_dict.get("/S", "D")
    prefix = label_dict.get("/P", "")
    start = label_dict.get("/St", 1)

    page_index = index - start_index + start

    if style == "/D":
        return f"{prefix}{page_index}"
    elif style == "/R":
        return f"{prefix}{to_roman(page_index).upper()}"
    elif style == "/r":
        return f"{prefix}{to_roman(page_index).lower()}"
    elif style == "/A":
        return f"{prefix}{to_alpha(page_index).upper()}"
    elif style == "/a":
        return f"{prefix}{to_alpha(page_index).lower()}"
    else:
        return str(index + 1)

def to_roman(num: int) -> str:
    roman_symbols = [
        ("M", 1000), ("CM", 900), ("D", 500), ("CD", 400), ("C", 100), ("XC", 90),
        ("L", 50), ("XL", 40), ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1)
    ]
    result = ""
    for symbol, value in roman_symbols:
        while num >= value:
            result += symbol
            num -= value
    return result

def to_alpha(num: int) -> str:
    result = ""
    while num > 0:
        num, remainder = divmod(num - 1, 26)
        result = chr(65 + remainder) + result
    return result

def nums_insert(key: NumberObject, value: DictionaryObject, nums: ArrayObject) -> None:
    """
    Insert a key, value pair in a Nums array.

    See 7.9.7 "Number Trees".

    Args:
        key: number key of the entry
        value: value of the entry
        nums: Nums array to modify
    """
    for i in range(0, len(nums), 2):
        if nums[i] > key:
            nums.insert(i, value)
            nums.insert(i, key)
            return
    nums.extend([key, value])

def nums_clear_range(key: NumberObject, page_index_to: int, nums: ArrayObject) -> None:
    """
    Remove all entries in a number tree in a range after an entry.

    See 7.9.7 "Number Trees".

    Args:
        key: number key of the entry before the range
        page_index_to: The page index of the upper limit of the range
        nums: Nums array to modify
    """
    start_index = nums.index(key) if key in nums else -2
    i = start_index + 2
    while i < len(nums):
        if nums[i] >= page_index_to:
            break
        i += 2
    del nums[start_index+2:i]

def nums_next(key: NumberObject, nums: ArrayObject) -> Tuple[Optional[NumberObject], Optional[DictionaryObject]]:
    """
    Return the (key, value) pair of the entry after the given one.

    See 7.9.7 "Number Trees".

    Args:
        key: number key of the entry
        nums: Nums array
    """
    for i in range(0, len(nums), 2):
        if nums[i] > key:
            return nums[i], nums[i+1]
    return None, None
