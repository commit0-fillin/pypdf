from typing import Any, Tuple, Union
from ._base import FloatObject, NumberObject
from ._data_structures import ArrayObject

class RectangleObject(ArrayObject):
    """
    This class is used to represent *page boxes* in pypdf.

    These boxes include:

    * :attr:`artbox <pypdf._page.PageObject.artbox>`
    * :attr:`bleedbox <pypdf._page.PageObject.bleedbox>`
    * :attr:`cropbox <pypdf._page.PageObject.cropbox>`
    * :attr:`mediabox <pypdf._page.PageObject.mediabox>`
    * :attr:`trimbox <pypdf._page.PageObject.trimbox>`
    """

    def __init__(self, arr: Union['RectangleObject', Tuple[float, float, float, float]]) -> None:
        assert len(arr) == 4
        ArrayObject.__init__(self, [self._ensure_is_number(x) for x in arr])

    def __repr__(self) -> str:
        return f'RectangleObject({list(self)!r})'

    @property
    def lower_left(self) -> Tuple[float, float]:
        """
        Property to read and modify the lower left coordinate of this box
        in (x,y) form.
        """
        return (float(self[0]), float(self[1]))

    @property
    def lower_right(self) -> Tuple[float, float]:
        """
        Property to read and modify the lower right coordinate of this box
        in (x,y) form.
        """
        return (float(self[2]), float(self[1]))

    @property
    def upper_left(self) -> Tuple[float, float]:
        """
        Property to read and modify the upper left coordinate of this box
        in (x,y) form.
        """
        return (float(self[0]), float(self[3]))

    @property
    def upper_right(self) -> Tuple[float, float]:
        """
        Property to read and modify the upper right coordinate of this box
        in (x,y) form.
        """
        return (float(self[2]), float(self[3]))
