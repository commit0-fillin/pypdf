"""
Implementation of stream filters for PDF.

See TABLE H.1 Abbreviations for standard filter names
"""
__author__ = 'Mathieu Fenniak'
__author_email__ = 'biziqe@mathieu.fenniak.net'
import math
import struct
import zlib
from base64 import a85decode
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from ._utils import WHITESPACES_AS_BYTES, b_, deprecate_with_replacement, deprecation_no_replacement, logger_warning, ord_
from .constants import CcittFaxDecodeParameters as CCITT
from .constants import ColorSpaces
from .constants import FilterTypeAbbreviations as FTA
from .constants import FilterTypes as FT
from .constants import ImageAttributes as IA
from .constants import LzwFilterParameters as LZW
from .constants import StreamAttributes as SA
from .errors import DeprecationError, PdfReadError, PdfStreamError
from .generic import ArrayObject, DictionaryObject, IndirectObject, NullObject

def decompress(data: bytes) -> bytes:
    """
    Decompress the given data using zlib.

    This function attempts to decompress the input data using zlib. If the
    decompression fails due to a zlib error, it falls back to using a
    decompression object with a larger window size.

    Args:
        data: The input data to be decompressed.

    Returns:
        The decompressed data.
    """
    try:
        return zlib.decompress(data)
    except zlib.error:
        # If decompression fails, try with a larger window size
        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 32)
        return decompressor.decompress(data) + decompressor.flush()

class FlateDecode:

    @staticmethod
    def decode(data: bytes, decode_parms: Optional[DictionaryObject]=None, **kwargs: Any) -> bytes:
        """
        Decode data which is flate-encoded.

        Args:
          data: flate-encoded data.
          decode_parms: a dictionary of values, understanding the
            "/Predictor":<int> key only

        Returns:
          The flate-decoded data.

        Raises:
          PdfReadError:
        """
        try:
            data = decompress(data)
        except zlib.error as e:
            raise PdfReadError(f"Error decoding flate-encoded data: {e}")

        if decode_parms:
            predictor = decode_parms.get("/Predictor", 1)
            if predictor != 1:
                columns = decode_parms.get("/Columns", 1)
                colors = decode_parms.get("/Colors", 1)
                bits_per_component = decode_parms.get("/BitsPerComponent", 8)
                data = FlateDecode._decode_predictor(data, predictor, columns, colors, bits_per_component)
        return data

    @staticmethod
    def _decode_predictor(data: bytes, predictor: int, columns: int, colors: int, bits_per_component: int) -> bytes:
        # Implementation of predictor decoding
        # This is a simplified version and may need to be expanded for all predictor types
        if predictor == 2:  # TIFF Predictor
            output = bytearray()
            row_size = (columns * colors * bits_per_component + 7) // 8
            for i in range(0, len(data), row_size):
                row = data[i:i+row_size]
                for j in range(colors, len(row)):
                    row[j] = (row[j] + row[j-colors]) % 256
                output.extend(row)
            return bytes(output)
        elif predictor >= 10 and predictor <= 15:  # PNG Predictors
            output = bytearray()
            row_size = columns * colors * bits_per_component // 8 + 1
            for i in range(0, len(data), row_size):
                filter_type = data[i]
                row = data[i+1:i+row_size]
                if filter_type == 0:  # None
                    output.extend(row)
                elif filter_type == 1:  # Sub
                    for j in range(colors, len(row)):
                        row[j] = (row[j] + row[j-colors]) % 256
                    output.extend(row)
                # Add more PNG predictor types as needed
            return bytes(output)
        else:
            raise PdfReadError(f"Unsupported predictor: {predictor}")

    @staticmethod
    def encode(data: bytes, level: int=-1) -> bytes:
        """
        Compress the input data using zlib.

        Args:
            data: The data to be compressed.
            level: See https://docs.python.org/3/library/zlib.html#zlib.compress

        Returns:
            The compressed data.
        """
        return zlib.compress(data, level)

class ASCIIHexDecode:
    """
    The ASCIIHexDecode filter decodes data that has been encoded in ASCII
    hexadecimal form into a base-7 ASCII format.
    """

    @staticmethod
    def decode(data: Union[str, bytes], decode_parms: Optional[DictionaryObject]=None, **kwargs: Any) -> bytes:
        """
        Decode an ASCII-Hex encoded data stream.

        Args:
          data: a str sequence of hexadecimal-encoded values to be
            converted into a base-7 ASCII string
          decode_parms: a string conversion in base-7 ASCII, where each of its values
            v is such that 0 <= ord(v) <= 127.

        Returns:
          A string conversion in base-7 ASCII, where each of its values
          v is such that 0 <= ord(v) <= 127.

        Raises:
          PdfStreamError:
        """
        if isinstance(data, str):
            data = data.encode('ascii')
        
        try:
            # Remove whitespace and '>' character
            data = data.replace(b' ', b'').replace(b'\n', b'').replace(b'\r', b'').rstrip(b'>')
            
            # If odd number of digits, add a trailing 0
            if len(data) % 2 != 0:
                data += b'0'
            
            # Decode hex string
            return bytes.fromhex(data.decode('ascii'))
        except ValueError as e:
            raise PdfStreamError(f"Error decoding ASCII hex data: {e}")

class RunLengthDecode:
    """
    The RunLengthDecode filter decodes data that has been encoded in a
    simple byte-oriented format based on run length.
    The encoded data is a sequence of runs, where each run consists of
    a length byte followed by 1 to 128 bytes of data. If the length byte is
    in the range 0 to 127,
    the following length + 1 (1 to 128) bytes are copied literally during
    decompression.
    If length is in the range 129 to 255, the following single byte is to be
    copied 257 − length (2 to 128) times during decompression. A length value
    of 128 denotes EOD.
    """

    @staticmethod
    def decode(data: bytes, decode_parms: Optional[DictionaryObject]=None, **kwargs: Any) -> bytes:
        """
        Decode a run length encoded data stream.

        Args:
          data: a bytes sequence of length/data
          decode_parms: ignored.

        Returns:
          A bytes decompressed sequence.

        Raises:
          PdfStreamError:
        """
        decoded = bytearray()
        i = 0
        try:
            while i < len(data):
                length = data[i]
                if length == 128:
                    break  # EOD
                if length < 128:
                    decoded.extend(data[i+1:i+length+2])
                    i += length + 2
                else:
                    decoded.extend([data[i+1]] * (257 - length))
                    i += 2
            return bytes(decoded)
        except IndexError:
            raise PdfStreamError("Invalid run length encoded data")

class LZWDecode:
    """
    Taken from:

    http://www.java2s.com/Open-Source/Java-Document/PDF/PDF-
    Renderer/com/sun/pdfview/decode/LZWDecode.java.htm
    """

    class Decoder:

        def __init__(self, data: bytes) -> None:
            self.STOP = 257
            self.CLEARDICT = 256
            self.data = data
            self.bytepos = 0
            self.bitpos = 0
            self.dict = [''] * 4096
            for i in range(256):
                self.dict[i] = chr(i)
            self.reset_dict()

        def decode(self) -> str:
            """
            TIFF 6.0 specification explains in sufficient details the steps to
            implement the LZW encode() and decode() algorithms.

            algorithm derived from:
            http://www.rasip.fer.hr/research/compress/algorithms/fund/lz/lzw.html
            and the PDFReference

            Raises:
              PdfReadError: If the stop code is missing
            """
            cW = self.get_next_code()
            result = self.dict[cW]
            old = cW
            while True:
                cW = self.get_next_code()
                if cW == self.STOP:
                    break
                if cW == self.CLEARDICT:
                    self.reset_dict()
                    cW = self.get_next_code()
                    result += self.dict[cW]
                    old = cW
                else:
                    try:
                        s = self.dict[cW]
                    except IndexError:
                        s = self.dict[old] + self.dict[old][0]
                    result += s
                    self.add_code_to_dict(self.dict[old] + s[0])
                    old = cW
            return result

        def get_next_code(self) -> int:
            fillbits = self.curr_code_size
            value = 0
            while fillbits > 0:
                if self.bytepos >= len(self.data):
                    raise PdfReadError("LZW stream is missing stop code")
                nextbits = ord(self.data[self.bytepos : self.bytepos + 1])
                bitsfromhere = 8 - self.bitpos
                if bitsfromhere > fillbits:
                    bitsfromhere = fillbits
                value |= (((nextbits >> (8 - self.bitpos - bitsfromhere)) &
                           (0xff >> (8 - bitsfromhere))) <<
                          (fillbits - bitsfromhere))
                fillbits -= bitsfromhere
                self.bitpos += bitsfromhere
                if self.bitpos >= 8:
                    self.bitpos = 0
                    self.bytepos += 1
            return value

        def add_code_to_dict(self, newstring: str) -> None:
            self.dict[self.dict_size] = newstring
            self.dict_size += 1
            if self.dict_size == 512:
                self.curr_code_size = 10
            elif self.dict_size == 1024:
                self.curr_code_size = 11
            elif self.dict_size == 2048:
                self.curr_code_size = 12

        def reset_dict(self) -> None:
            self.dict_size = 258
            self.curr_code_size = 9

    @staticmethod
    def decode(data: bytes, decode_parms: Optional[DictionaryObject]=None, **kwargs: Any) -> str:
        """
        Decode an LZW encoded data stream.

        Args:
          data: ``bytes`` or ``str`` text to decode.
          decode_parms: a dictionary of parameter values.

        Returns:
          decoded data.
        """
        decoder = LZWDecode.Decoder(data)
        return decoder.decode()

class ASCII85Decode:
    """Decodes string ASCII85-encoded data into a byte format."""

    @staticmethod
    def decode(data: Union[str, bytes], decode_parms: Optional[DictionaryObject]=None, **kwargs: Any) -> bytes:
        """
        Decode an Ascii85 encoded data stream.

        Args:
          data: ``bytes`` or ``str`` text to decode.
          decode_parms: a dictionary of parameter values.

        Returns:
          decoded data.
        """
        if isinstance(data, str):
            data = data.encode('ascii')
        
        # Remove whitespace and '<~' '~>' delimiters if present
        data = data.replace(b' ', b'').replace(b'\n', b'').replace(b'\r', b'')
        if data.startswith(b'<~') and data.endswith(b'~>'):
            data = data[2:-2]
        
        return a85decode(data)

class DCTDecode:
    pass

class JPXDecode:
    pass

class CCITParameters:
    """§7.4.6, optional parameters for the CCITTFaxDecode filter."""

    def __init__(self, K: int=0, columns: int=0, rows: int=0) -> None:
        self.K = K
        self.EndOfBlock = None
        self.EndOfLine = None
        self.EncodedByteAlign = None
        self.columns = columns
        self.rows = rows
        self.DamagedRowsBeforeError = None

class CCITTFaxDecode:
    """
    §7.4.6, CCITTFaxDecode filter (ISO 32000).

    Either Group 3 or Group 4 CCITT facsimile (fax) encoding.
    CCITT encoding is bit-oriented, not byte-oriented.

    §7.4.6, optional parameters for the CCITTFaxDecode filter.
    """

def decode_stream_data(stream: Any) -> Union[bytes, str]:
    """
    Decode the stream data based on the specified filters.

    This function decodes the stream data using the filters provided in the
    stream. It supports various filter types, including FlateDecode,
    ASCIIHexDecode, RunLengthDecode, LZWDecode, ASCII85Decode, DCTDecode, JPXDecode, and
    CCITTFaxDecode.

    Args:
        stream: The input stream object containing the data and filters.

    Returns:
        The decoded stream data.

    Raises:
        NotImplementedError: If an unsupported filter type is encountered.
    """
    filters = stream.get("/Filter", ())
    if isinstance(filters, IndirectObject):
        filters = filters.get_object()
    if isinstance(filters, ArrayObject):
        filters = [f.get_object() if isinstance(f, IndirectObject) else f for f in filters]
    elif isinstance(filters, NullObject):
        filters = []
    elif isinstance(filters, str):
        filters = [filters]
    elif isinstance(filters, IndirectObject):
        filters = [filters.get_object()]
    else:
        raise PdfReadError(f"Unsupported Filter type: {type(filters)}")

    decode_params = stream.get("/DecodeParms", {})
    if isinstance(decode_params, IndirectObject):
        decode_params = decode_params.get_object()
    if isinstance(decode_params, ArrayObject):
        decode_params = [dp.get_object() if isinstance(dp, IndirectObject) else dp for dp in decode_params]
    elif isinstance(decode_params, NullObject):
        decode_params = {}
    elif isinstance(decode_params, DictionaryObject):
        decode_params = [decode_params]
    else:
        raise PdfReadError(f"Unsupported DecodeParms type: {type(decode_params)}")

    data = stream._data
    for i, filter_type in enumerate(filters):
        if filter_type in ["/FlateDecode", "/Fl"]:
            data = FlateDecode.decode(data, decode_params[i] if i < len(decode_params) else None)
        elif filter_type == "/ASCIIHexDecode":
            data = ASCIIHexDecode.decode(data)
        elif filter_type == "/RunLengthDecode":
            data = RunLengthDecode.decode(data)
        elif filter_type == "/LZWDecode":
            data = LZWDecode.decode(data, decode_params[i] if i < len(decode_params) else None)
        elif filter_type == "/ASCII85Decode":
            data = ASCII85Decode.decode(data)
        elif filter_type in ["/DCTDecode", "/JPXDecode", "/CCITTFaxDecode"]:
            # These filters require image processing libraries, so we'll return the raw data
            return data
        else:
            raise NotImplementedError(f"Unsupported filter type: {filter_type}")

    return data

def decodeStreamData(stream: Any) -> Union[str, bytes]:
    """Deprecated. Use decode_stream_data."""
    deprecation_with_replacement("decodeStreamData", "decode_stream_data", "3.0.0")
    return decode_stream_data(stream)

def _xobj_to_image(x_object_obj: Dict[str, Any]) -> Tuple[Optional[str], bytes, Any]:
    """
    Users need to have the pillow package installed.

    It's unclear if pypdf will keep this function here, hence it's private.
    It might get removed at any point.

    Args:
      x_object_obj:

    Returns:
        Tuple[file extension, bytes, PIL.Image.Image]
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("pillow is required to use _xobj_to_image")

    size = (x_object_obj['/Width'], x_object_obj['/Height'])
    color_space = x_object_obj['/ColorSpace']
    color_components = 3 if color_space == '/DeviceRGB' else 1

    if '/Filter' in x_object_obj:
        data = decode_stream_data(x_object_obj)
    else:
        data = x_object_obj.get_data()

    mode, color_inverted = _get_imagemode(color_space, color_components, '', 0)

    if x_object_obj['/Filter'] == '/FlateDecode':
        img, image_format, extension, color_inverted = _handle_flate(size, data, mode, color_space, color_components, str(x_object_obj))
    elif x_object_obj['/Filter'] == '/DCTDecode':
        img = Image.open(BytesIO(data))
        image_format = 'JPEG'
        extension = '.jpg'
    elif x_object_obj['/Filter'] == '/JPXDecode':
        img, image_format, extension, color_inverted = _handle_jpx(size, data, mode, color_space, color_components)
    else:
        raise NotImplementedError(f"Unsupported filter: {x_object_obj['/Filter']}")

    if color_inverted:
        img = Image.fromarray(255 - np.array(img))

    return extension, data, img
