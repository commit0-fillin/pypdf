import binascii
import codecs
import hashlib
import re
from binascii import unhexlify
from math import log10
from typing import Any, Callable, ClassVar, Dict, Optional, Sequence, Union, cast
from .._codecs import _pdfdoc_encoding_rev
from .._protocols import PdfObjectProtocol, PdfWriterProtocol
from .._utils import StreamType, b_, deprecate_no_replacement, logger_warning, read_non_whitespace, read_until_regex, str_
from ..errors import STREAM_TRUNCATED_PREMATURELY, PdfReadError, PdfStreamError
__author__ = 'Mathieu Fenniak'
__author_email__ = 'biziqe@mathieu.fenniak.net'

class PdfObject(PdfObjectProtocol):
    hash_func: Callable[..., 'hashlib._Hash'] = hashlib.sha1
    indirect_reference: Optional['IndirectObject']

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'PdfObject':
        """
        Clone object into pdf_dest (PdfWriterProtocol which is an interface for PdfWriter).

        By default, this method will call ``_reference_clone`` (see ``_reference``).


        Args:
          pdf_dest: Target to clone to.
          force_duplicate: By default, if the object has already been cloned and referenced,
            the copy will be returned; when ``True``, a new copy will be created.
            (Default value = ``False``)
          ignore_fields: List/tuple of field names (for dictionaries) that will be ignored
            during cloning (applies to children duplication as well). If fields are to be
            considered for a limited number of levels, you have to add it as integer, for
            example ``[1,"/B","/TOTO"]`` means that ``"/B"`` will be ignored at the first
            level only but ``"/TOTO"`` on all levels.

        Returns:
          The cloned PdfObject
        """
        return self._reference_clone(self, pdf_dest, force_duplicate)

    def _reference_clone(self, clone: Any, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False) -> PdfObjectProtocol:
        """
        Reference the object within the _objects of pdf_dest only if
        indirect_reference attribute exists (which means the objects was
        already identified in xref/xobjstm) if object has been already
        referenced do nothing.

        Args:
          clone:
          pdf_dest:

        Returns:
          The clone
        """
        if hasattr(self, 'indirect_reference') and self.indirect_reference is not None:
            if not force_duplicate and self.indirect_reference.idnum in pdf_dest._id_translated:
                return pdf_dest._id_translated[self.indirect_reference.idnum]
            clone.indirect_reference = pdf_dest._add_object(clone)
        return clone

    def get_object(self) -> Optional['PdfObject']:
        """Resolve indirect references."""
        return self

class NullObject(PdfObject):

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'NullObject':
        """Clone object into pdf_dest."""
        return NullObject()

    def __repr__(self) -> str:
        return 'NullObject'

class BooleanObject(PdfObject):

    def __init__(self, value: Any) -> None:
        self.value = value

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'BooleanObject':
        """Clone object into pdf_dest."""
        return BooleanObject(self.value)

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, BooleanObject):
            return self.value == __o.value
        elif isinstance(__o, bool):
            return self.value == __o
        else:
            return False

    def __repr__(self) -> str:
        return 'True' if self.value else 'False'

class IndirectObject(PdfObject):

    def __init__(self, idnum: int, generation: int, pdf: Any) -> None:
        self.idnum = idnum
        self.generation = generation
        self.pdf = pdf

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'IndirectObject':
        """Clone object into pdf_dest."""
        obj = self.get_object()
        if obj is not None:
            return obj.clone(pdf_dest, force_duplicate, ignore_fields)
        return NullObject()

    def __deepcopy__(self, memo: Any) -> 'IndirectObject':
        return IndirectObject(self.idnum, self.generation, self.pdf)

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self._get_object_with_check(), name)
        except AttributeError:
            raise AttributeError(f'No attribute {name} found in IndirectObject or pointed object')

    def __getitem__(self, key: Any) -> Any:
        return self._get_object_with_check()[key]

    def __str__(self) -> str:
        return self.get_object().__str__()

    def __repr__(self) -> str:
        return f'IndirectObject({self.idnum!r}, {self.generation!r}, {id(self.pdf)})'

    def __eq__(self, other: object) -> bool:
        return other is not None and isinstance(other, IndirectObject) and (self.idnum == other.idnum) and (self.generation == other.generation) and (self.pdf is other.pdf)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)
FLOAT_WRITE_PRECISION = 8

class FloatObject(float, PdfObject):

    def __new__(cls, value: Union[str, Any]='0.0', context: Optional[Any]=None) -> 'FloatObject':
        try:
            value = float(str_(value))
            return float.__new__(cls, value)
        except Exception as e:
            logger_warning(f'{e} : FloatObject ({value}) invalid; use 0.0 instead', __name__)
            return float.__new__(cls, 0.0)

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'FloatObject':
        """Clone object into pdf_dest."""
        return FloatObject(self)

    def __repr__(self) -> str:
        return self.myrepr()

class NumberObject(int, PdfObject):
    NumberPattern = re.compile(b'[^+-.0-9]')

    def __new__(cls, value: Any) -> 'NumberObject':
        try:
            return int.__new__(cls, int(value))
        except ValueError:
            logger_warning(f'NumberObject({value}) invalid; use 0 instead', __name__)
            return int.__new__(cls, 0)

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'NumberObject':
        """Clone object into pdf_dest."""
        return NumberObject(self)

class ByteStringObject(bytes, PdfObject):
    """
    Represents a string object where the text encoding could not be determined.

    This occurs quite often, as the PDF spec doesn't provide an alternate way to
    represent strings -- for example, the encryption data stored in files (like
    /O) is clearly not text, but is still stored in a "String" object.
    """

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'ByteStringObject':
        """Clone object into pdf_dest."""
        return ByteStringObject(self)

    @property
    def original_bytes(self) -> bytes:
        """For compatibility with TextStringObject.original_bytes."""
        return self

class TextStringObject(str, PdfObject):
    """
    A string object that has been decoded into a real unicode string.

    If read from a PDF document, this string appeared to match the
    PDFDocEncoding, or contained a UTF-16BE BOM mark to cause UTF-16 decoding
    to occur.
    """
    autodetect_pdfdocencoding: bool
    autodetect_utf16: bool
    utf16_bom: bytes

    def __new__(cls, value: Any) -> 'TextStringObject':
        if isinstance(value, bytes):
            value = value.decode('charmap')
        o = str.__new__(cls, value)
        o.autodetect_utf16 = False
        o.autodetect_pdfdocencoding = False
        o.utf16_bom = b''
        if value.startswith(('þÿ', 'ÿþ')):
            o.autodetect_utf16 = True
            o.utf16_bom = value[:2].encode('charmap')
        else:
            try:
                encode_pdfdocencoding(o)
                o.autodetect_pdfdocencoding = True
            except UnicodeEncodeError:
                o.autodetect_utf16 = True
        return o

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'TextStringObject':
        """Clone object into pdf_dest."""
        clone = TextStringObject(self)
        clone.autodetect_pdfdocencoding = self.autodetect_pdfdocencoding
        clone.autodetect_utf16 = self.autodetect_utf16
        clone.utf16_bom = self.utf16_bom
        return clone

    @property
    def original_bytes(self) -> bytes:
        """
        It is occasionally possible that a text string object gets created where
        a byte string object was expected due to the autodetection mechanism --
        if that occurs, this "original_bytes" property can be used to
        back-calculate what the original encoded bytes were.
        """
        if self.autodetect_utf16:
            return self.utf16_bom + self.encode("utf-16be")
        elif self.autodetect_pdfdocencoding:
            return encode_pdfdocencoding(self)
        else:
            raise UnicodeEncodeError("No information about original bytes")

class NameObject(str, PdfObject):
    delimiter_pattern = re.compile(b'\\s+|[\\(\\)<>\\[\\]{}/%]')
    surfix = b'/'
    renumber_table: ClassVar[Dict[str, bytes]] = {'#': b'#23', '(': b'#28', ')': b'#29', '/': b'#2F', '%': b'#25', **{chr(i): f'#{i:02X}'.encode() for i in range(33)}}

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'NameObject':
        """Clone object into pdf_dest."""
        return NameObject(self)
    CHARSETS = ('utf-8', 'gbk', 'latin1')
