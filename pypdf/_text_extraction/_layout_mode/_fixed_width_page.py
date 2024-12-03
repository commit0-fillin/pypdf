"""Extract PDF text preserving the layout of the source PDF"""
import sys
from itertools import groupby
from math import ceil
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from ..._utils import logger_warning
from .. import LAYOUT_NEW_BT_GROUP_SPACE_WIDTHS
from ._font import Font
from ._text_state_manager import TextStateManager
from ._text_state_params import TextStateParams
if sys.version_info >= (3, 8):
    from typing import Literal, TypedDict
else:
    from typing_extensions import Literal, TypedDict

class BTGroup(TypedDict):
    """
    Dict describing a line of text rendered within a BT/ET operator pair.
    If multiple text show operations render text on the same line, the text
    will be combined into a single BTGroup dict.

    Keys:
        tx: x coordinate of first character in BTGroup
        ty: y coordinate of first character in BTGroup
        font_size: nominal font size
        font_height: effective font height
        text: rendered text
        displaced_tx: x coordinate of last character in BTGroup
        flip_sort: -1 if page is upside down, else 1
    """
    tx: float
    ty: float
    font_size: float
    font_height: float
    text: str
    displaced_tx: float
    flip_sort: Literal[-1, 1]

def bt_group(tj_op: TextStateParams, rendered_text: str, dispaced_tx: float) -> BTGroup:
    """
    BTGroup constructed from a TextStateParams instance, rendered text, and
    displaced tx value.

    Args:
        tj_op (TextStateParams): TextStateParams instance
        rendered_text (str): rendered text
        dispaced_tx (float): x coordinate of last character in BTGroup
    """
    return {
        "tx": tj_op.tx,
        "ty": tj_op.ty,
        "font_size": tj_op.font_size,
        "font_height": tj_op.font_height,
        "text": rendered_text,
        "displaced_tx": dispaced_tx,
        "flip_sort": -1 if tj_op.flip_vertical else 1
    }

def recurs_to_target_op(ops: Iterator[Tuple[List[Any], bytes]], text_state_mgr: TextStateManager, end_target: Literal[b'Q', b'ET'], fonts: Dict[str, Font], strip_rotated: bool=True) -> Tuple[List[BTGroup], List[TextStateParams]]:
    """
    Recurse operators between BT/ET and/or q/Q operators managing the transform
    stack and capturing text positioning and rendering data.

    Args:
        ops: iterator of operators in content stream
        text_state_mgr: a TextStateManager instance
        end_target: Either b"Q" (ends b"q" op) or b"ET" (ends b"BT" op)
        fonts: font dictionary as returned by PageObject._layout_mode_fonts()

    Returns:
        tuple: list of BTGroup dicts + list of TextStateParams dataclass instances.
    """
    bt_groups = []
    text_state_params = []
    
    for operands, operator in ops:
        if operator == end_target:
            break
        elif operator == b'BT':
            sub_bt_groups, sub_text_state_params = recurs_to_target_op(ops, text_state_mgr, b'ET', fonts, strip_rotated)
            bt_groups.extend(sub_bt_groups)
            text_state_params.extend(sub_text_state_params)
        elif operator == b'q':
            text_state_mgr.add_q()
            sub_bt_groups, sub_text_state_params = recurs_to_target_op(ops, text_state_mgr, b'Q', fonts, strip_rotated)
            bt_groups.extend(sub_bt_groups)
            text_state_params.extend(sub_text_state_params)
        elif operator == b'cm':
            text_state_mgr.add_cm(*operands)
        elif operator == b'Tm':
            text_state_mgr.add_tm(operands)
        elif operator == b'Tf':
            font_name, font_size = operands
            text_state_mgr.set_font(fonts[font_name], font_size)
        elif operator in (b'Tc', b'Tw', b'Tz', b'TL', b'Ts'):
            text_state_mgr.set_state_param(operator, operands)
        elif operator in (b'Tj', b'TJ'):
            tj_op = text_state_mgr.text_state_params()
            rendered_text = ''.join(op if isinstance(op, str) else '' for op in operands[0]) if operator == b'TJ' else operands[0]
            displaced_tx = tj_op.displaced_transform()[4]
            if not (strip_rotated and tj_op.rotated):
                bt_groups.append(bt_group(tj_op, rendered_text, displaced_tx))
            text_state_params.append(tj_op)
    
    return bt_groups, text_state_params

def y_coordinate_groups(bt_groups: List[BTGroup], debug_path: Optional[Path]=None) -> Dict[int, List[BTGroup]]:
    """
    Group text operations by rendered y coordinate, i.e. the line number.

    Args:
        bt_groups: list of dicts as returned by text_show_operations()
        debug_path (Path, optional): Path to a directory for saving debug output.

    Returns:
        Dict[int, List[BTGroup]]: dict of lists of text rendered by each BT operator
            keyed by y coordinate
    """
    y_groups = {}
    for group in bt_groups:
        y = int(round(group['ty']))
        if y not in y_groups:
            y_groups[y] = []
        y_groups[y].append(group)
    
    # Sort groups by x coordinate
    for y in y_groups:
        y_groups[y].sort(key=lambda g: g['tx'])
    
    if debug_path:
        with open(debug_path / 'y_coordinate_groups.txt', 'w') as f:
            for y, groups in sorted(y_groups.items()):
                f.write(f"Y: {y}\n")
                for group in groups:
                    f.write(f"  {group['text']} (x: {group['tx']})\n")
                f.write("\n")
    
    return y_groups

def text_show_operations(ops: Iterator[Tuple[List[Any], bytes]], fonts: Dict[str, Font], strip_rotated: bool=True, debug_path: Optional[Path]=None) -> List[BTGroup]:
    """
    Extract text from BT/ET operator pairs.

    Args:
        ops (Iterator[Tuple[List, bytes]]): iterator of operators in content stream
        fonts (Dict[str, Font]): font dictionary
        strip_rotated: Removes text if rotated w.r.t. to the page. Defaults to True.
        debug_path (Path, optional): Path to a directory for saving debug output.

    Returns:
        List[BTGroup]: list of dicts of text rendered by each BT operator
    """
    text_state_mgr = TextStateManager()
    bt_groups = []
    
    for operands, operator in ops:
        if operator == b'BT':
            sub_bt_groups, _ = recurs_to_target_op(ops, text_state_mgr, b'ET', fonts, strip_rotated)
            bt_groups.extend(sub_bt_groups)
        elif operator == b'q':
            text_state_mgr.add_q()
            sub_bt_groups, _ = recurs_to_target_op(ops, text_state_mgr, b'Q', fonts, strip_rotated)
            bt_groups.extend(sub_bt_groups)
        elif operator == b'Q':
            text_state_mgr.remove_q()
        elif operator == b'cm':
            text_state_mgr.add_cm(*operands)
    
    if debug_path:
        with open(debug_path / 'text_show_operations.txt', 'w') as f:
            for group in bt_groups:
                f.write(f"Text: {group['text']}\n")
                f.write(f"Position: (x: {group['tx']}, y: {group['ty']})\n")
                f.write(f"Font size: {group['font_size']}\n")
                f.write(f"Font height: {group['font_height']}\n")
                f.write("\n")
    
    return bt_groups

def fixed_char_width(bt_groups: List[BTGroup], scale_weight: float=1.25) -> float:
    """
    Calculate average character width weighted by the length of the rendered
    text in each sample for conversion to fixed-width layout.

    Args:
        bt_groups (List[BTGroup]): List of dicts of text rendered by each
            BT operator
        scale_weight (float): Weight factor for scaling. Defaults to 1.25.

    Returns:
        float: fixed character width
    """
    total_width = 0
    total_chars = 0
    total_weight = 0
    
    for group in bt_groups:
        text_length = len(group['text'])
        if text_length > 0:
            width = (group['displaced_tx'] - group['tx']) / text_length
            weight = text_length ** scale_weight
            total_width += width * weight
            total_chars += text_length
            total_weight += weight
    
    if total_weight > 0:
        return total_width / total_weight
    else:
        return 0  # Default to 0 if no valid text groups are found

def fixed_width_page(ty_groups: Dict[int, List[BTGroup]], char_width: float, space_vertically: bool) -> str:
    """
    Generate page text from text operations grouped by rendered y coordinate.

    Args:
        ty_groups: dict of text show ops as returned by y_coordinate_groups()
        char_width: fixed character width
        space_vertically: include blank lines inferred from y distance + font height.

    Returns:
        str: page text in a fixed width format that closely adheres to the rendered
            layout in the source pdf.
    """
    lines = []
    y_coords = sorted(ty_groups.keys(), reverse=True)
    
    for i, y in enumerate(y_coords):
        line = ""
        for group in ty_groups[y]:
            x_pos = int(round(group['tx'] / char_width))
            while len(line) < x_pos:
                line += " "
            line += group['text']
        
        lines.append(line.rstrip())
        
        if space_vertically and i < len(y_coords) - 1:
            next_y = y_coords[i + 1]
            line_height = int(round((y - next_y) / (char_width * 2)))  # Assuming line height is twice the char width
            lines.extend([""] * (line_height - 1))
    
    return "\n".join(lines)
