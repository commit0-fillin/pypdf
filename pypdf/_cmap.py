from binascii import unhexlify
from math import ceil
from typing import Any, Dict, List, Tuple, Union, cast
from ._codecs import adobe_glyphs, charset_encoding
from ._utils import b_, logger_error, logger_warning
from .generic import DecodedStreamObject, DictionaryObject, IndirectObject, NullObject, StreamObject

def build_char_map(font_name: str, space_width: float, obj: DictionaryObject) -> Tuple[str, float, Union[str, Dict[int, str]], Dict[Any, Any], DictionaryObject]:
    """
    Determine information about a font.

    Args:
        font_name: font name as a string
        space_width: default space width if no data is found.
        obj: XObject or Page where you can find a /Resource dictionary

    Returns:
        Font sub-type, space_width criteria (50% of width), encoding, map character-map, font-dictionary.
        The font-dictionary itself is suitable for the curious.
    """
    try:
        font_dict = cast(DictionaryObject, obj["/Resources"]["/Font"][font_name])
    except KeyError:
        logger_warning(f"Font {font_name} not found in Resources", "build_char_map")
        return unknown_char_map + (NullObject(),)

    subtype, space_width, encoding, char_map = build_char_map_from_dict(space_width, font_dict)
    return subtype, space_width, encoding, char_map, font_dict

def build_char_map_from_dict(space_width: float, ft: DictionaryObject) -> Tuple[str, float, Union[str, Dict[int, str]], Dict[Any, Any]]:
    """
    Determine information about a font.

    Args:
        space_width: default space with if no data found
             (normally half the width of a character).
        ft: Font Dictionary

    Returns:
        Font sub-type, space_width criteria(50% of width), encoding, map character-map.
        The font-dictionary itself is suitable for the curious.
    """
    subtype = ft.get("/Subtype", "")
    encoding: Union[str, Dict[int, str]] = "utf-8"
    char_map: Dict[Any, Any] = {}

    if "/Encoding" in ft:
        encoding = ft["/Encoding"]
        if isinstance(encoding, DictionaryObject):
            encoding = encoding.get("/BaseEncoding", "")
        if encoding in _predefined_cmap:
            encoding = _predefined_cmap[encoding]
        elif isinstance(encoding, str) and encoding.startswith("/"):
            encoding = encoding[1:]

    if "/ToUnicode" in ft:
        try:
            to_unicode = ft["/ToUnicode"]
            if isinstance(to_unicode, StreamObject):
                to_unicode = to_unicode.get_data()
            if isinstance(to_unicode, bytes):
                to_unicode = to_unicode.decode("utf-8")
            char_map = parse_to_unicode(to_unicode)
        except Exception as e:
            logger_error(f"Error parsing ToUnicode CMap: {e}", "build_char_map_from_dict")

    if "/FirstChar" in ft and "/LastChar" in ft and "/Widths" in ft:
        first_char = ft["/FirstChar"]
        last_char = ft["/LastChar"]
        widths = ft["/Widths"]
        if 32 in range(first_char, last_char + 1):
            space_index = 32 - first_char
            if 0 <= space_index < len(widths):
                space_width = widths[space_index] / 2

    return subtype, space_width, encoding, char_map
unknown_char_map: Tuple[str, float, Union[str, Dict[int, str]], Dict[Any, Any]] = ('Unknown', 9999, dict(zip(range(256), ['�'] * 256)), {})
_predefined_cmap: Dict[str, str] = {'/Identity-H': 'utf-16-be', '/Identity-V': 'utf-16-be', '/GB-EUC-H': 'gbk', '/GB-EUC-V': 'gbk', '/GBpc-EUC-H': 'gb2312', '/GBpc-EUC-V': 'gb2312', '/GBK-EUC-H': 'gbk', '/GBK-EUC-V': 'gbk', '/GBK2K-H': 'gb18030', '/GBK2K-V': 'gb18030', '/ETen-B5-H': 'cp950', '/ETen-B5-V': 'cp950', '/ETenms-B5-H': 'cp950', '/ETenms-B5-V': 'cp950', '/UniCNS-UTF16-H': 'utf-16-be', '/UniCNS-UTF16-V': 'utf-16-be'}
_default_fonts_space_width: Dict[str, int] = {'/Courier': 600, '/Courier-Bold': 600, '/Courier-BoldOblique': 600, '/Courier-Oblique': 600, '/Helvetica': 278, '/Helvetica-Bold': 278, '/Helvetica-BoldOblique': 278, '/Helvetica-Oblique': 278, '/Helvetica-Narrow': 228, '/Helvetica-NarrowBold': 228, '/Helvetica-NarrowBoldOblique': 228, '/Helvetica-NarrowOblique': 228, '/Times-Roman': 250, '/Times-Bold': 250, '/Times-BoldItalic': 250, '/Times-Italic': 250, '/Symbol': 250, '/ZapfDingbats': 278}
