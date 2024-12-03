"""A dataclass that captures the CTM and Text State for a tj operation"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union
from .. import mult, orient
from ._font import Font

@dataclass
class TextStateParams:
    """
    Text state parameters and operator values for a single text value in a
    TJ or Tj PDF operation.

    Attributes:
        txt (str): the text to be rendered.
        font (Font): font object
        font_size (int | float): font size
        Tc (float): character spacing. Defaults to 0.0.
        Tw (float): word spacing. Defaults to 0.0.
        Tz (float): horizontal scaling. Defaults to 100.0.
        TL (float): leading, vertical displacement between text lines. Defaults to 0.0.
        Ts (float): text rise. Used for super/subscripts. Defaults to 0.0.
        transform (List[float]): effective transformation matrix.
        tx (float): x cood of rendered text, i.e. self.transform[4]
        ty (float): y cood of rendered text. May differ from self.transform[5] per self.Ts.
        displaced_tx (float): x coord immediately following rendered text
        space_tx (float): tx for a space character
        font_height (float): effective font height accounting for CTM
        flip_vertical (bool): True if y axis has been inverted (i.e. if self.transform[3] < 0.)
        rotated (bool): True if the text orientation is rotated with respect to the page.
    """
    txt: str
    font: Font
    font_size: Union[int, float]
    Tc: float = 0.0
    Tw: float = 0.0
    Tz: float = 100.0
    TL: float = 0.0
    Ts: float = 0.0
    transform: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    tx: float = field(default=0.0, init=False)
    ty: float = field(default=0.0, init=False)
    displaced_tx: float = field(default=0.0, init=False)
    space_tx: float = field(default=0.0, init=False)
    font_height: float = field(default=0.0, init=False)
    flip_vertical: bool = field(default=False, init=False)
    rotated: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if orient(self.transform) in (90, 270):
            self.transform = mult([1.0, -self.transform[1], -self.transform[2], 1.0, 0.0, 0.0], self.transform)
            self.rotated = True
        if orient(self.transform) == 180 and self.transform[0] < -1e-06:
            self.transform = mult([-1.0, 0.0, 0.0, -1.0, 0.0, 0.0], self.transform)
            self.rotated = True
        self.displaced_tx = self.displaced_transform()[4]
        self.tx = self.transform[4]
        self.ty = self.render_transform()[5]
        self.space_tx = round(self.word_tx(' '), 3)
        if self.space_tx < 1e-06:
            self.space_tx = round(self.word_tx('', self.font.space_width * -2), 3)
        self.font_height = self.font_size * math.sqrt(self.transform[1] ** 2 + self.transform[3] ** 2)
        self.flip_vertical = self.transform[3] < -1e-06

    def font_size_matrix(self) -> List[float]:
        """Font size matrix"""
        return [self.font_size * self.Tz / 100, 0, 0, self.font_size, 0, 0]

    def displaced_transform(self) -> List[float]:
        """Effective transform matrix after text has been rendered."""
        displacement = self.displacement_matrix()
        return mult(displacement, self.transform)

    def render_transform(self) -> List[float]:
        """Effective transform matrix accounting for font size, Tz, and Ts."""
        font_matrix = self.font_size_matrix()
        text_rise = [1, 0, 0, 1, 0, self.Ts]
        return mult(mult(text_rise, font_matrix), self.transform)

    def displacement_matrix(self, word: Union[str, None]=None, TD_offset: float=0.0) -> List[float]:
        """
        Text displacement matrix

        Args:
            word (str, optional): Defaults to None in which case self.txt displacement is
                returned.
            TD_offset (float, optional): translation applied by TD operator. Defaults to 0.0.
        """
        if word is None:
            word = self.txt
        tx = self.word_tx(word, TD_offset)
        return [1, 0, 0, 1, tx, 0]

    def word_tx(self, word: str, TD_offset: float=0.0) -> float:
        """Horizontal text displacement for any word according this text state"""
        word_width = self.font.word_width(word)
        space_count = word.count(' ')
        tx = ((word_width - space_count) * self.font_size + space_count * self.Tw + len(word) * self.Tc) * self.Tz / 100
        return tx + TD_offset

    @staticmethod
    def to_dict(inst: 'TextStateParams') -> Dict[str, Any]:
        """Dataclass to dict for json.dumps serialization"""
        return {
            'txt': inst.txt,
            'font': Font.to_dict(inst.font),
            'font_size': inst.font_size,
            'Tc': inst.Tc,
            'Tw': inst.Tw,
            'Tz': inst.Tz,
            'TL': inst.TL,
            'Ts': inst.Ts,
            'transform': inst.transform,
            'tx': inst.tx,
            'ty': inst.ty,
            'displaced_tx': inst.displaced_tx,
            'space_tx': inst.space_tx,
            'font_height': inst.font_height,
            'flip_vertical': inst.flip_vertical,
            'rotated': inst.rotated
        }
