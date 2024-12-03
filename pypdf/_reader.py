import os
import re
from io import BytesIO, UnsupportedOperation
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type, Union, cast
from ._doc_common import PdfDocCommon, convert_to_int
from ._encryption import Encryption, PasswordType
from ._page import PageObject
from ._utils import StrByteType, StreamType, b_, logger_warning, read_non_whitespace, read_previous_line, read_until_whitespace, skip_over_comment, skip_over_whitespace
from .constants import TrailerKeys as TK
from .errors import EmptyFileError, FileNotDecryptedError, PdfReadError, PdfStreamError, WrongPasswordError
from .generic import ArrayObject, ContentStream, DecodedStreamObject, DictionaryObject, EncodedStreamObject, IndirectObject, NameObject, NullObject, NumberObject, PdfObject, TextStringObject, read_object
from .xmp import XmpInformation

class PdfReader(PdfDocCommon):
    """
    Initialize a PdfReader object.

    This operation can take some time, as the PDF stream's cross-reference
    tables are read into memory.

    Args:
        stream: A File object or an object that supports the standard read
            and seek methods similar to a File object. Could also be a
            string representing a path to a PDF file.
        strict: Determines whether user should be warned of all
            problems and also causes some correctable problems to be fatal.
            Defaults to ``False``.
        password: Decrypt PDF file at initialization. If the
            password is None, the file will not be decrypted.
            Defaults to ``None``.
    """

    def __init__(self, stream: Union[StrByteType, Path], strict: bool=False, password: Union[None, str, bytes]=None) -> None:
        self.strict = strict
        self.flattened_pages: Optional[List[PageObject]] = None
        self.resolved_objects: Dict[Tuple[Any, Any], Optional[PdfObject]] = {}
        self.xref_index = 0
        self.xref: Dict[int, Dict[Any, Any]] = {}
        self.xref_free_entry: Dict[int, Dict[Any, Any]] = {}
        self.xref_objStm: Dict[int, Tuple[Any, Any]] = {}
        self.trailer = DictionaryObject()
        self._page_id2num: Optional[Dict[Any, Any]] = None
        if hasattr(stream, 'mode') and 'b' not in stream.mode:
            logger_warning('PdfReader stream/file object is not in binary mode. It may not be read correctly.', __name__)
        self._stream_opened = False
        if isinstance(stream, (str, Path)):
            with open(stream, 'rb') as fh:
                stream = BytesIO(fh.read())
            self._stream_opened = True
        self.read(stream)
        self.stream = stream
        self._override_encryption = False
        self._encryption: Optional[Encryption] = None
        if self.is_encrypted:
            self._override_encryption = True
            id_entry = self.trailer.get(TK.ID)
            id1_entry = id_entry[0].get_object().original_bytes if id_entry else b''
            encrypt_entry = cast(DictionaryObject, self.trailer[TK.ENCRYPT].get_object())
            self._encryption = Encryption.read(encrypt_entry, id1_entry)
            pwd = password if password is not None else b''
            if self._encryption.verify(pwd) == PasswordType.NOT_DECRYPTED and password is not None:
                raise WrongPasswordError('Wrong password')
            self._override_encryption = False
        elif password is not None:
            raise PdfReadError('Not encrypted file')

    def __enter__(self) -> 'PdfReader':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> None:
        self.close()

    def close(self) -> None:
        """Close the stream if opened in __init__ and clear memory."""
        if self._stream_opened:
            self.stream.close()
        self.resolved_objects.clear()
        self.flattened_pages = None

    @property
    def root_object(self) -> DictionaryObject:
        """Provide access to "/Root". Standardized with PdfWriter."""
        return cast(DictionaryObject, self.trailer[TK.ROOT])

    @property
    def _info(self) -> Optional[DictionaryObject]:
        """
        Provide access to "/Info". Standardized with PdfWriter.

        Returns:
            /Info Dictionary; None if the entry does not exist
        """
        if TK.INFO not in self.trailer:
            return None
        return cast(DictionaryObject, self.trailer[TK.INFO].get_object())

    @property
    def _ID(self) -> Optional[ArrayObject]:
        """
        Provide access to "/ID". Standardized with PdfWriter.

        Returns:
            /ID array; None if the entry does not exist
        """
        if TK.ID not in self.trailer:
            return None
        return cast(ArrayObject, self.trailer[TK.ID])

    def _repr_mimebundle_(self, include: Union[None, Iterable[str]]=None, exclude: Union[None, Iterable[str]]=None) -> Dict[str, Any]:
        """
        Integration into Jupyter Notebooks.

        This method returns a dictionary that maps a mime-type to its
        representation.

        See https://ipython.readthedocs.io/en/stable/config/integrating.html
        """
        from io import BytesIO
        bio = BytesIO()
        self.stream.seek(0)
        bio.write(self.stream.read())
        bio.seek(0)
        return {"application/pdf": bio.getvalue()}

    @property
    def pdf_header(self) -> str:
        """
        The first 8 bytes of the file.

        This is typically something like ``'%PDF-1.6'`` and can be used to
        detect if the file is actually a PDF file and which version it is.
        """
        self.stream.seek(0)
        return self.stream.read(8).decode('ascii')

    @property
    def xmp_metadata(self) -> Optional[XmpInformation]:
        """XMP (Extensible Metadata Platform) data."""
        try:
            xmp_ref = self.trailer["/Root"]["/Metadata"]
        except KeyError:
            return None
        return XmpInformation(xmp_ref.get_object())

    def _get_page(self, page_number: int) -> PageObject:
        """
        Retrieve a page by number from this PDF file.

        Args:
            page_number: The page number to retrieve
                (pages begin at zero)

        Returns:
            A :class:`PageObject<pypdf._page.PageObject>` instance.
        """
        if self.flattened_pages is None:
            self._flatten()
        if page_number < 0 or page_number >= len(self.flattened_pages):
            raise IndexError("Page number {0} invalid".format(page_number))
        return cast(PageObject, self.flattened_pages[page_number])

    def _get_page_number_by_indirect(self, indirect_reference: Union[None, int, NullObject, IndirectObject]) -> Optional[int]:
        """
        Generate _page_id2num.

        Args:
            indirect_reference:

        Returns:
            The page number or None
        """
        if self._page_id2num is None:
            self._page_id2num = {}
            for i, page in enumerate(self.pages):
                if page.indirect_reference is not None:
                    self._page_id2num[page.indirect_reference.idnum] = i
        if indirect_reference is None or isinstance(indirect_reference, NullObject):
            return None
        if isinstance(indirect_reference, int):
            idnum = indirect_reference
        else:
            idnum = indirect_reference.idnum
        return self._page_id2num.get(idnum)

    def _basic_validation(self, stream: StreamType) -> None:
        """Ensure file is not empty. Read at most 5 bytes."""
        stream.seek(0)
        first_bytes = stream.read(5)
        if first_bytes == b"":
            raise EmptyFileError("Cannot read an empty file")
        if first_bytes != b"%PDF-":
            raise PdfReadError(f"PDF starts with {first_bytes!r}, not '%PDF-'")

    def _find_eof_marker(self, stream: StreamType) -> None:
        """
        Jump to the %%EOF marker.

        According to the specs, the %%EOF marker should be at the very end of
        the file. Hence for standard-compliant PDF documents this function will
        read only the last part (DEFAULT_BUFFER_SIZE).
        """
        stream.seek(-1024, 2)
        end = stream.read().lower()
        idx = end.rfind(b"%%eof")
        if idx == -1:
            raise PdfReadError("EOF marker not found")
        stream.seek(stream.tell() - (len(end) - idx))

    def _find_startxref_pos(self, stream: StreamType) -> int:
        """
        Find startxref entry - the location of the xref table.

        Args:
            stream:

        Returns:
            The bytes offset
        """
        stream.seek(-1024, 2)
        line = b""
        while b"startxref" not in line:
            line = read_previous_line(stream)
        return int(read_previous_line(stream))

    @staticmethod
    def _get_xref_issues(stream: StreamType, startxref: int) -> int:
        """
        Return an int which indicates an issue. 0 means there is no issue.

        Args:
            stream:
            startxref:

        Returns:
            0 means no issue, other values represent specific issues.
        """
        stream.seek(startxref)
        try:
            if stream.read(5) != b"xref ":
                return 1
        except UnicodeDecodeError:
            return 2
        return 0

    def decrypt(self, password: Union[str, bytes]) -> PasswordType:
        """
        When using an encrypted / secured PDF file with the PDF Standard
        encryption handler, this function will allow the file to be decrypted.
        It checks the given password against the document's user password and
        owner password, and then stores the resulting decryption key if either
        password is correct.

        It does not matter which password was matched. Both passwords provide
        the correct decryption key that will allow the document to be used with
        this library.

        Args:
            password: The password to match.

        Returns:
            An indicator if the document was decrypted and whether it was the
            owner password or the user password.
        """
        if not self.is_encrypted:
            raise PdfReadError("File is not encrypted")
        return self._encryption.verify(password)

    @property
    def is_encrypted(self) -> bool:
        """
        Read-only boolean property showing whether this PDF file is encrypted.

        Note that this property, if true, will remain true even after the
        :meth:`decrypt()<pypdf.PdfReader.decrypt>` method is called.
        """
        return self._encryption is not None

    def add_form_topname(self, name: str) -> Optional[DictionaryObject]:
        """
        Add a top level form that groups all form fields below it.

        Args:
            name: text string of the "/T" Attribute of the created object

        Returns:
            The created object. ``None`` means no object was created.
        """
        if "/AcroForm" not in self.root_object:
            return None
        acroform = cast(DictionaryObject, self.root_object["/AcroForm"])
        if "/Fields" not in acroform:
            return None
        fields = cast(ArrayObject, acroform["/Fields"])
        new_field = DictionaryObject()
        new_field[NameObject("/T")] = TextStringObject(name)
        new_field[NameObject("/Kids")] = fields
        acroform[NameObject("/Fields")] = ArrayObject([new_field])
        return new_field

    def rename_form_topname(self, name: str) -> Optional[DictionaryObject]:
        """
        Rename top level form field that all form fields below it.

        Args:
            name: text string of the "/T" field of the created object

        Returns:
            The modified object. ``None`` means no object was modified.
        """
        if "/AcroForm" not in self.root_object:
            return None
        acroform = cast(DictionaryObject, self.root_object["/AcroForm"])
        if "/Fields" not in acroform:
            return None
        fields = cast(ArrayObject, acroform["/Fields"])
        if len(fields) != 1:
            return None
        top_field = fields[0]
        if not isinstance(top_field, DictionaryObject):
            return None
        top_field[NameObject("/T")] = TextStringObject(name)
        return top_field
