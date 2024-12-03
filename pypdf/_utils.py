"""Utility functions for PDF library."""
__author__ = 'Mathieu Fenniak'
__author_email__ = 'biziqe@mathieu.fenniak.net'
import functools
import logging
import re
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from io import DEFAULT_BUFFER_SIZE, BytesIO
from os import SEEK_CUR
from typing import IO, Any, Dict, List, Optional, Pattern, Tuple, Union, cast, overload
if sys.version_info[:2] >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias
from .errors import STREAM_TRUNCATED_PREMATURELY, DeprecationError, PdfStreamError
TransformationMatrixType: TypeAlias = Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]
CompressedTransformationMatrix: TypeAlias = Tuple[float, float, float, float, float, float]
StreamType = IO[Any]
StrByteType = Union[str, StreamType]

def read_until_whitespace(stream: StreamType, maxchars: Optional[int]=None) -> bytes:
    """
    Read non-whitespace characters and return them.

    Stops upon encountering whitespace or when maxchars is reached.

    Args:
        stream: The data stream from which was read.
        maxchars: The maximum number of bytes returned; by default unlimited.

    Returns:
        The data which was read.
    """
    result = b""
    while maxchars is None or len(result) < maxchars:
        byte = stream.read(1)
        if byte in WHITESPACES or byte == b"":
            break
        result += byte
    return result

def read_non_whitespace(stream: StreamType) -> bytes:
    """
    Find and read the next non-whitespace character (ignores whitespace).

    Args:
        stream: The data stream from which was read.

    Returns:
        The data which was read.
    """
    while True:
        byte = stream.read(1)
        if byte not in WHITESPACES:
            return byte
        if byte == b"":
            raise PdfStreamError(STREAM_TRUNCATED_PREMATURELY)

def skip_over_whitespace(stream: StreamType) -> bool:
    """
    Similar to read_non_whitespace, but return a boolean if more than one
    whitespace character was read.

    Args:
        stream: The data stream from which was read.

    Returns:
        True if more than one whitespace was skipped, otherwise return False.
    """
    skipped = False
    while True:
        byte = stream.read(1)
        if byte not in WHITESPACES:
            stream.seek(-1, SEEK_CUR)
            return skipped
        skipped = True

def check_if_whitespace_only(value: bytes) -> bool:
    """
    Check if the given value consists of whitespace characters only.

    Args:
        value: The bytes to check.

    Returns:
        True if the value only has whitespace characters, otherwise return False.
    """
    return all(byte in WHITESPACES for byte in value)

def read_until_regex(stream: StreamType, regex: Pattern[bytes]) -> bytes:
    """
    Read until the regular expression pattern matched (ignore the match).
    Treats EOF on the underlying stream as the end of the token to be matched.

    Args:
        regex: re.Pattern

    Returns:
        The read bytes.
    """
    result = b""
    while True:
        byte = stream.read(1)
        if byte == b"":
            break
        result += byte
        if regex.search(result):
            break
    return result

def read_block_backwards(stream: StreamType, to_read: int) -> bytes:
    """
    Given a stream at position X, read a block of size to_read ending at position X.

    This changes the stream's position to the beginning of where the block was
    read.

    Args:
        stream:
        to_read:

    Returns:
        The data which was read.
    """
    current_pos = stream.tell()
    start_pos = max(0, current_pos - to_read)
    stream.seek(start_pos)
    data = stream.read(current_pos - start_pos)
    stream.seek(start_pos)
    return data

def read_previous_line(stream: StreamType) -> bytes:
    """
    Given a byte stream with current position X, return the previous line.

    All characters between the first CR/LF byte found before X
    (or, the start of the file, if no such byte is found) and position X
    After this call, the stream will be positioned one byte after the
    first non-CRLF character found beyond the first CR/LF byte before X,
    or, if no such byte is found, at the beginning of the stream.

    Args:
        stream: StreamType:

    Returns:
        The data which was read.
    """
    current_pos = stream.tell()
    line = b""
    while current_pos > 0:
        current_pos -= 1
        stream.seek(current_pos)
        char = stream.read(1)
        if char in (b'\r', b'\n'):
            if line:
                stream.seek(current_pos + 1)
                return line[::-1]
        else:
            line += char
    return line[::-1]

def mark_location(stream: StreamType) -> None:
    """Create text file showing current location in context."""
    RADIUS = 5000
    stream.seek(-RADIUS, 1)
    data = stream.read(RADIUS)
    with open('pypdf_pdfLocation.txt', 'wb') as f:
        f.write(data)
B_CACHE: Dict[Union[str, bytes], bytes] = {}
WHITESPACES = (b' ', b'\n', b'\r', b'\t', b'\x00')
WHITESPACES_AS_BYTES = b''.join(WHITESPACES)
WHITESPACES_AS_REGEXP = b'[' + WHITESPACES_AS_BYTES + b']'

def deprecate_with_replacement(old_name: str, new_name: str, removed_in: str) -> None:
    """Raise an exception that a feature will be removed, but has a replacement."""
    warnings.warn(
        f"{old_name} is deprecated and will be removed in {removed_in}. "
        f"Use {new_name} instead.",
        DeprecationWarning,
        stacklevel=2,
    )

def deprecation_with_replacement(old_name: str, new_name: str, removed_in: str) -> None:
    """Raise an exception that a feature was already removed, but has a replacement."""
    raise DeprecationError(
        f"{old_name} was removed in {removed_in}. Use {new_name} instead."
    )

def deprecate_no_replacement(name: str, removed_in: str) -> None:
    """Raise an exception that a feature will be removed without replacement."""
    warnings.warn(
        f"{name} is deprecated and will be removed in {removed_in}.",
        DeprecationWarning,
        stacklevel=2,
    )

def deprecation_no_replacement(name: str, removed_in: str) -> None:
    """Raise an exception that a feature was already removed without replacement."""
    raise DeprecationError(
        f"{name} was removed in {removed_in}."
    )

def logger_error(msg: str, src: str) -> None:
    """
    Use this instead of logger.error directly.

    That allows people to overwrite it more easily.

    See the docs on when to use which:
    https://pypdf.readthedocs.io/en/latest/user/suppress-warnings.html
    """
    logging.getLogger(src).error(msg)

def logger_warning(msg: str, src: str) -> None:
    """
    Use this instead of logger.warning directly.

    That allows people to overwrite it more easily.

    ## Exception, warnings.warn, logger_warning
    - Exceptions should be used if the user should write code that deals with
      an error case, e.g. the PDF being completely broken.
    - warnings.warn should be used if the user needs to fix their code, e.g.
      DeprecationWarnings
    - logger_warning should be used if the user needs to know that an issue was
      handled by pypdf, e.g. a non-compliant PDF being read in a way that
      pypdf could apply a robustness fix to still read it. This applies mainly
      to strict=False mode.
    """
    logging.getLogger(src).warning(msg)

def rename_kwargs(func_name: str, kwargs: Dict[str, Any], aliases: Dict[str, str], fail: bool=False) -> None:
    """
    Helper function to deprecate arguments.

    Args:
        func_name: Name of the function to be deprecated
        kwargs:
        aliases:
        fail:
    """
    for old_arg, new_arg in aliases.items():
        if old_arg in kwargs:
            if new_arg in kwargs:
                raise TypeError(f"{func_name}() received both {old_arg} and {new_arg}")
            warnings.warn(
                f"{old_arg} is deprecated and will be removed in a future version. Use {new_arg} instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            kwargs[new_arg] = kwargs.pop(old_arg)
        elif fail and new_arg not in kwargs:
            raise TypeError(f"{func_name}() missing required argument: {new_arg}")

class classproperty:
    """
    Decorator that converts a method with a single cls argument into a property
    that can be accessed directly from the class.
    """

    def __init__(self, method=None):
        self.fget = method

    def __get__(self, instance, cls=None) -> Any:
        return self.fget(cls)

@dataclass
class File:
    from .generic import IndirectObject
    name: str
    data: bytes
    image: Optional[Any] = None
    indirect_reference: Optional[IndirectObject] = None

    def __str__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name}, data: {_human_readable_bytes(len(self.data))})'

    def __repr__(self) -> str:
        return self.__str__()[:-1] + f', hash: {hash(self.data)})'

@dataclass
class ImageFile(File):
    from .generic import IndirectObject
    image: Optional[Any] = None
    indirect_reference: Optional[IndirectObject] = None

    def replace(self, new_image: Any, **kwargs: Any) -> None:
        """
        Replace the Image with a new PIL image.

        Args:
            new_image (PIL.Image.Image): The new PIL image to replace the existing image.
            **kwargs: Additional keyword arguments to pass to `Image.Image.save()`.

        Raises:
            TypeError: If the image is inline or in a PdfReader.
            TypeError: If the image does not belong to a PdfWriter.
            TypeError: If `new_image` is not a PIL Image.

        Note:
            This method replaces the existing image with a new image.
            It is not allowed for inline images or images within a PdfReader.
            The `kwargs` parameter allows passing additional parameters
            to `Image.Image.save()`, such as quality.
        """
        from PIL import Image
        
        if self.indirect_reference is None:
            raise TypeError("Cannot replace inline images or images in a PdfReader")
        
        if not isinstance(new_image, Image.Image):
            raise TypeError("new_image must be a PIL Image")
        
        pdf_writer = self.indirect_reference.pdf
        if pdf_writer is None or not hasattr(pdf_writer, '_objects'):
            raise TypeError("Image does not belong to a PdfWriter")
        
        # Save the new image to a bytes buffer
        buffer = BytesIO()
        new_image.save(buffer, format='PDF', **kwargs)
        new_image_data = buffer.getvalue()
        
        # Update the image data
        self.data = new_image_data
        self.image = new_image
        
        # Update the PDF object
        obj = pdf_writer._objects[self.indirect_reference.idnum - 1]
        obj['/Filter'] = '/DCTDecode'
        obj['/ColorSpace'] = '/DeviceRGB'
        obj['/BitsPerComponent'] = 8
        obj['/Width'] = new_image.width
        obj['/Height'] = new_image.height
        obj._data = new_image_data

@functools.total_ordering
class Version:
    COMPONENT_PATTERN = re.compile('^(\\d+)(.*)$')

    def __init__(self, version_str: str) -> None:
        self.version_str = version_str
        self.components = self._parse_version(version_str)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self.components == other.components

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            raise ValueError(f'Version cannot be compared against {type(other)}')
        min_len = min(len(self.components), len(other.components))
        for i in range(min_len):
            self_value, self_suffix = self.components[i]
            other_value, other_suffix = other.components[i]
            if self_value < other_value:
                return True
            elif self_value > other_value:
                return False
            if self_suffix < other_suffix:
                return True
            elif self_suffix > other_suffix:
                return False
        return len(self.components) < len(other.components)

    def _parse_version(self, version_str: str) -> List[Tuple[int, str]]:
        components = []
        for part in version_str.split('.'):
            match = self.COMPONENT_PATTERN.match(part)
            if match:
                value, suffix = match.groups()
                components.append((int(value), suffix))
            else:
                components.append((0, part))
        return components

    def __str__(self) -> str:
        return self.version_str

    def __repr__(self) -> str:
        return f"Version('{self.version_str}')"
