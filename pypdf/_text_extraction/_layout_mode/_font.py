"""Font constants and classes for "layout" mode text operations"""
from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Union
from ...generic import IndirectObject
from ._font_widths import STANDARD_WIDTHS

@dataclass
class Font:
    """
    A font object formatted for use during "layout" mode text extraction

    Attributes:
        subtype (str): font subtype
        space_width (int | float): width of a space character
        encoding (str | Dict[int, str]): font encoding
        char_map (dict): character map
        font_dictionary (dict): font dictionary
    """
    subtype: str
    space_width: Union[int, float]
    encoding: Union[str, Dict[int, str]]
    char_map: Dict[Any, Any]
    font_dictionary: Dict[Any, Any]
    width_map: Dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.encoding, dict) and '/Widths' in self.font_dictionary:
            first_char = self.font_dictionary.get('/FirstChar', 0)
            self.width_map = {self.encoding.get(idx + first_char, chr(idx + first_char)): width for idx, width in enumerate(self.font_dictionary['/Widths'])}
        if '/DescendantFonts' in self.font_dictionary:
            d_font: Dict[Any, Any]
            for d_font_idx, d_font in enumerate(self.font_dictionary['/DescendantFonts']):
                while isinstance(d_font, IndirectObject):
                    d_font = d_font.get_object()
                self.font_dictionary['/DescendantFonts'][d_font_idx] = d_font
                ord_map = {ord(_target): _surrogate for _target, _surrogate in self.char_map.items() if isinstance(_target, str)}
                skip_count = 0
                _w = d_font.get('/W', [])
                for idx, w_entry in enumerate(_w):
                    if skip_count:
                        skip_count -= 1
                        continue
                    if not isinstance(w_entry, (int, float)):
                        continue
                    if isinstance(_w[idx + 1], Sequence):
                        start_idx, width_list = _w[idx:idx + 2]
                        self.width_map.update({ord_map[_cidx]: _width for _cidx, _width in zip(range(start_idx, start_idx + len(width_list), 1), width_list) if _cidx in ord_map})
                        skip_count = 1
                    if not isinstance(_w[idx + 1], Sequence) and (not isinstance(_w[idx + 2], Sequence)):
                        start_idx, stop_idx, const_width = _w[idx:idx + 3]
                        self.width_map.update({ord_map[_cidx]: const_width for _cidx in range(start_idx, stop_idx + 1, 1) if _cidx in ord_map})
                        skip_count = 2
        if not self.width_map and '/BaseFont' in self.font_dictionary:
            for key in STANDARD_WIDTHS:
                if self.font_dictionary['/BaseFont'].startswith(f'/{key}'):
                    self.width_map = STANDARD_WIDTHS[key]
                    break

    def word_width(self, word: str) -> float:
        """Sum of character widths specified in PDF font for the supplied word"""
        return sum(self.width_map.get(char, self.space_width) for char in word)

    @staticmethod
    def to_dict(font_instance: 'Font') -> Dict[str, Any]:
        """Dataclass to dict for json.dumps serialization."""
        return {
            'subtype': font_instance.subtype,
            'space_width': font_instance.space_width,
            'encoding': font_instance.encoding,
            'char_map': font_instance.char_map,
            'font_dictionary': font_instance.font_dictionary,
            'width_map': font_instance.width_map
        }
