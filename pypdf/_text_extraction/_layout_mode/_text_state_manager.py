"""manage the PDF transform stack during "layout" mode text extraction"""
from collections import ChainMap, Counter
from typing import Any, Dict, List, MutableMapping, Union
from typing import ChainMap as ChainMapType
from typing import Counter as CounterType
from ...errors import PdfReadError
from .. import mult
from ._font import Font
from ._text_state_params import TextStateParams
TextStateManagerChainMapType = ChainMapType[Union[int, str], Union[float, bool]]
TextStateManagerDictType = MutableMapping[Union[int, str], Union[float, bool]]

class TextStateManager:
    """
    Tracks the current text state including cm/tm/trm transformation matrices.

    Attributes:
        transform_stack (ChainMap): ChainMap of cm/tm transformation matrices
        q_queue (Counter[int]): Counter of q operators
        q_depth (List[int]): list of q operator nesting levels
        Tc (float): character spacing
        Tw (float): word spacing
        Tz (int): horizontal scaling
        TL (float): leading
        Ts (float): text rise
        font (Font): font object
        font_size (int | float): font size
    """

    def __init__(self) -> None:
        self.transform_stack: TextStateManagerChainMapType = ChainMap(self.new_transform())
        self.q_queue: CounterType[int] = Counter()
        self.q_depth = [0]
        self.Tc: float = 0.0
        self.Tw: float = 0.0
        self.Tz: float = 100.0
        self.TL: float = 0.0
        self.Ts: float = 0.0
        self.font: Union[Font, None] = None
        self.font_size: Union[int, float] = 0

    def set_state_param(self, op: bytes, value: Union[float, List[Any]]) -> None:
        """
        Set a text state parameter. Supports Tc, Tz, Tw, TL, and Ts operators.

        Args:
            op: operator read from PDF stream as bytes. No action is taken
                for unsupported operators (see supported operators above).
            value (float | List[Any]): new parameter value. If a list,
                value[0] is used.
        """
        if isinstance(value, list):
            value = value[0]
        
        if op == b'Tc':
            self.Tc = value
        elif op == b'Tw':
            self.Tw = value
        elif op == b'Tz':
            self.Tz = value
        elif op == b'TL':
            self.TL = value
        elif op == b'Ts':
            self.Ts = value

    def set_font(self, font: Font, size: float) -> None:
        """
        Set the current font and font_size.

        Args:
            font (Font): a layout mode Font
            size (float): font size
        """
        self.font = font
        self.font_size = size

    def text_state_params(self, value: Union[bytes, str]='') -> TextStateParams:
        """
        Create a TextStateParams instance to display a text string. Type[bytes] values
        will be decoded implicitly.

        Args:
            value (str | bytes): text to associate with the captured state.

        Raises:
            PdfReadError: if font not set (no Tf operator in incoming pdf content stream)

        Returns:
            TextStateParams: current text state parameters
        """
        if self.font is None:
            raise PdfReadError("Font not set. No Tf operator in incoming pdf content stream.")
        
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='ignore')
        
        return TextStateParams(
            txt=value,
            font=self.font,
            font_size=self.font_size,
            Tc=self.Tc,
            Tw=self.Tw,
            Tz=self.Tz,
            TL=self.TL,
            Ts=self.Ts,
            transform=self.effective_transform
        )

    @staticmethod
    def raw_transform(_a: float=1.0, _b: float=0.0, _c: float=0.0, _d: float=1.0, _e: float=0.0, _f: float=0.0) -> Dict[int, float]:
        """Only a/b/c/d/e/f matrix params"""
        return {0: _a, 1: _b, 2: _c, 3: _d, 4: _e, 5: _f}

    @staticmethod
    def new_transform(_a: float=1.0, _b: float=0.0, _c: float=0.0, _d: float=1.0, _e: float=0.0, _f: float=0.0, is_text: bool=False, is_render: bool=False) -> TextStateManagerDictType:
        """Standard a/b/c/d/e/f matrix params + 'is_text' and 'is_render' keys"""
        transform = TextStateManager.raw_transform(_a, _b, _c, _d, _e, _f)
        transform['is_text'] = is_text
        transform['is_render'] = is_render
        return transform

    def reset_tm(self) -> TextStateManagerChainMapType:
        """Clear all transforms from chainmap having is_text==True or is_render==True"""
        self.transform_stack = ChainMap(*[t for t in self.transform_stack.maps if not (t.get('is_text', False) or t.get('is_render', False))])
        return self.transform_stack

    def reset_trm(self) -> TextStateManagerChainMapType:
        """Clear all transforms from chainmap having is_render==True"""
        self.transform_stack = ChainMap(*[t for t in self.transform_stack.maps if not t.get('is_render', False)])
        return self.transform_stack

    def remove_q(self) -> TextStateManagerChainMapType:
        """Rewind to stack prior state after closing a 'q' with internal 'cm' ops"""
        if self.q_depth[-1] > 0:
            self.q_depth[-1] -= 1
            self.q_queue[self.q_depth[-1]] -= 1
            if self.q_queue[self.q_depth[-1]] == 0:
                del self.q_queue[self.q_depth[-1]]
                self.q_depth.pop()
        self.transform_stack = self.transform_stack.parents
        return self.transform_stack

    def add_q(self) -> None:
        """Add another level to q_queue"""
        self.q_depth.append(self.q_depth[-1] + 1)
        self.q_queue[self.q_depth[-1]] += 1

    def add_cm(self, *args: Any) -> TextStateManagerChainMapType:
        """Concatenate an additional transform matrix"""
        new_transform = self.new_transform(*args)
        self.transform_stack = self.transform_stack.new_child(new_transform)
        return self.transform_stack

    def _complete_matrix(self, operands: List[float]) -> List[float]:
        """Adds a, b, c, and d to an "e/f only" operand set (e.g Td)"""
        if len(operands) == 2:
            return [1, 0, 0, 1, operands[0], operands[1]]
        return operands

    def add_tm(self, operands: List[float]) -> TextStateManagerChainMapType:
        """Append a text transform matrix"""
        operands = self._complete_matrix(operands)
        new_transform = self.new_transform(*operands, is_text=True)
        self.transform_stack = self.transform_stack.new_child(new_transform)
        return self.transform_stack

    def add_trm(self, operands: List[float]) -> TextStateManagerChainMapType:
        """Append a text rendering transform matrix"""
        operands = self._complete_matrix(operands)
        new_transform = self.new_transform(*operands, is_text=True, is_render=True)
        self.transform_stack = self.transform_stack.new_child(new_transform)
        return self.transform_stack

    @property
    def effective_transform(self) -> List[float]:
        """Current effective transform accounting for cm, tm, and trm transforms"""
        result = [1, 0, 0, 1, 0, 0]
        for transform in reversed(self.transform_stack.maps):
            result = mult(result, [transform[i] for i in range(6)])
        return result
