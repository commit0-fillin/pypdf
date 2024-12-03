import codecs
from typing import Dict, List, Tuple, Union
from .._codecs import _pdfdoc_encoding
from .._utils import StreamType, b_, logger_warning, read_non_whitespace
from ..errors import STREAM_TRUNCATED_PREMATURELY, PdfStreamError
from ._base import ByteStringObject, TextStringObject

def create_string_object(string: Union[str, bytes], forced_encoding: Union[None, str, List[str], Dict[int, str]]=None) -> Union[TextStringObject, ByteStringObject]:
    """
    Create a ByteStringObject or a TextStringObject from a string to represent the string.

    Args:
        string: The data being used
        forced_encoding: Typically None, or an encoding string

    Returns:
        A ByteStringObject or TextStringObject

    Raises:
        TypeError: If string is not of type str or bytes.
    """
    if isinstance(string, str):
        return TextStringObject(string)
    elif isinstance(string, bytes):
        if forced_encoding:
            if isinstance(forced_encoding, str):
                return TextStringObject(string.decode(forced_encoding))
            elif isinstance(forced_encoding, list):
                for encoding in forced_encoding:
                    try:
                        return TextStringObject(string.decode(encoding))
                    except UnicodeDecodeError:
                        pass
            elif isinstance(forced_encoding, dict):
                for encoding in forced_encoding.values():
                    try:
                        return TextStringObject(string.decode(encoding))
                    except UnicodeDecodeError:
                        pass
        try:
            return TextStringObject(string.decode('utf-16'))
        except UnicodeDecodeError:
            try:
                return TextStringObject(string.decode('utf-8'))
            except UnicodeDecodeError:
                return ByteStringObject(string)
    else:
        raise TypeError("create_string_object should be called with a str or bytes")
