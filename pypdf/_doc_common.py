import struct
import zlib
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple, Union, cast
from ._encryption import Encryption
from ._page import PageObject, _VirtualList
from ._page_labels import index2label as page_index2page_label
from ._utils import b_, deprecate_with_replacement, logger_warning, parse_iso8824_date
from .constants import CatalogAttributes as CA
from .constants import CatalogDictionary as CD
from .constants import CheckboxRadioButtonAttributes, GoToActionArguments, UserAccessPermissions
from .constants import Core as CO
from .constants import DocumentInformationAttributes as DI
from .constants import FieldDictionaryAttributes as FA
from .constants import PageAttributes as PG
from .constants import PagesAttributes as PA
from .errors import PdfReadError
from .generic import ArrayObject, BooleanObject, ByteStringObject, Destination, DictionaryObject, EncodedStreamObject, Field, Fit, FloatObject, IndirectObject, NameObject, NullObject, NumberObject, PdfObject, TextStringObject, TreeObject, ViewerPreferences, create_string_object
from .types import OutlineType, PagemodeType
from .xmp import XmpInformation

class DocumentInformation(DictionaryObject):
    """
    A class representing the basic document metadata provided in a PDF File.
    This class is accessible through
    :py:class:`PdfReader.metadata<pypdf.PdfReader.metadata>`.

    All text properties of the document metadata have
    *two* properties, e.g. author and author_raw. The non-raw property will
    always return a ``TextStringObject``, making it ideal for a case where the
    metadata is being displayed. The raw property can sometimes return a
    ``ByteStringObject``, if pypdf was unable to decode the string's text
    encoding; this requires additional safety in the caller and therefore is not
    as commonly accessed.
    """

    def __init__(self) -> None:
        DictionaryObject.__init__(self)

    @property
    def title(self) -> Optional[str]:
        """
        Read-only property accessing the document's title.

        Returns a ``TextStringObject`` or ``None`` if the title is not
        specified.
        """
        return self.get("/Title", None)

    @property
    def title_raw(self) -> Optional[str]:
        """The "raw" version of title; can return a ``ByteStringObject``."""
        return self.get("/Title", None)

    @property
    def author(self) -> Optional[str]:
        """
        Read-only property accessing the document's author.

        Returns a ``TextStringObject`` or ``None`` if the author is not
        specified.
        """
        return self.get("/Author", None)

    @property
    def author_raw(self) -> Optional[str]:
        """The "raw" version of author; can return a ``ByteStringObject``."""
        return self.get("/Author", None)

    @property
    def subject(self) -> Optional[str]:
        """
        Read-only property accessing the document's subject.

        Returns a ``TextStringObject`` or ``None`` if the subject is not
        specified.
        """
        return self.get("/Subject", None)

    @property
    def subject_raw(self) -> Optional[str]:
        """The "raw" version of subject; can return a ``ByteStringObject``."""
        return self.get("/Subject", None)

    @property
    def creator(self) -> Optional[str]:
        """
        Read-only property accessing the document's creator.

        If the document was converted to PDF from another format, this is the
        name of the application (e.g. OpenOffice) that created the original
        document from which it was converted. Returns a ``TextStringObject`` or
        ``None`` if the creator is not specified.
        """
        return self.get("/Creator", None)

    @property
    def creator_raw(self) -> Optional[str]:
        """The "raw" version of creator; can return a ``ByteStringObject``."""
        return self.get("/Creator", None)

    @property
    def producer(self) -> Optional[str]:
        """
        Read-only property accessing the document's producer.

        If the document was converted to PDF from another format, this is the
        name of the application (for example, macOS Quartz) that converted it to
        PDF. Returns a ``TextStringObject`` or ``None`` if the producer is not
        specified.
        """
        return self.get("/Producer", None)

    @property
    def producer_raw(self) -> Optional[str]:
        """The "raw" version of producer; can return a ``ByteStringObject``."""
        return self.get("/Producer", None)

    @property
    def creation_date(self) -> Optional[datetime]:
        """Read-only property accessing the document's creation date."""
        date_str = self.get("/CreationDate", None)
        if date_str is not None:
            return parse_iso8824_date(date_str)
        return None

    @property
    def creation_date_raw(self) -> Optional[str]:
        """
        The "raw" version of creation date; can return a ``ByteStringObject``.

        Typically in the format ``D:YYYYMMDDhhmmss[+Z-]hh'mm`` where the suffix
        is the offset from UTC.
        """
        return self.get("/CreationDate", None)

    @property
    def modification_date(self) -> Optional[datetime]:
        """
        Read-only property accessing the document's modification date.

        The date and time the document was most recently modified.
        """
        date_str = self.get("/ModDate", None)
        if date_str is not None:
            return parse_iso8824_date(date_str)
        return None

    @property
    def modification_date_raw(self) -> Optional[str]:
        """
        The "raw" version of modification date; can return a
        ``ByteStringObject``.

        Typically in the format ``D:YYYYMMDDhhmmss[+Z-]hh'mm`` where the suffix
        is the offset from UTC.
        """
        return self.get("/ModDate", None)

class PdfDocCommon:
    """
    Common functions from PdfWriter and PdfReader objects.

    This root class is strongly abstracted.
    """
    strict: bool = False
    _encryption: Optional[Encryption] = None

    @property
    def metadata(self) -> Optional[DocumentInformation]:
        """
        Retrieve the PDF file's document information dictionary, if it exists.

        Note that some PDF files use metadata streams instead of document
        information dictionaries, and these metadata streams will not be
        accessed by this function.
        """
        if "/Info" not in self.trailer:
            return None
        info = self.trailer["/Info"]
        if not isinstance(info, DictionaryObject):
            return None
        retval = DocumentInformation()
        retval.update(info)
        return retval

    @abstractmethod
    def _repr_mimebundle_(self, include: Union[None, Iterable[str]]=None, exclude: Union[None, Iterable[str]]=None) -> Dict[str, Any]:
        """
        Integration into Jupyter Notebooks.

        This method returns a dictionary that maps a mime-type to its
        representation.

        See https://ipython.readthedocs.io/en/stable/config/integrating.html
        """
        pass

    @property
    def viewer_preferences(self) -> Optional[ViewerPreferences]:
        """Returns the existing ViewerPreferences as an overloaded dictionary."""
        pass
    flattened_pages: Optional[List[PageObject]] = None

    def get_num_pages(self) -> int:
        """
        Calculate the number of pages in this PDF file.

        Returns:
            The number of pages of the parsed PDF file.

        Raises:
            PdfReadError: if file is encrypted and restrictions prevent
                this action.
        """
        pass

    def get_page(self, page_number: int) -> PageObject:
        """
        Retrieve a page by number from this PDF file.
        Most of the time ``.pages[page_number]`` is preferred.

        Args:
            page_number: The page number to retrieve
                (pages begin at zero)

        Returns:
            A :class:`PageObject<pypdf._page.PageObject>` instance.
        """
        pass

    @property
    def named_destinations(self) -> Dict[str, Any]:
        """
        A read-only dictionary which maps names to
        :class:`Destinations<pypdf.generic.Destination>`
        """
        pass

    def _get_named_destinations(self, tree: Union[TreeObject, None]=None, retval: Optional[Any]=None) -> Dict[str, Any]:
        """
        Retrieve the named destinations present in the document.

        Args:
            tree:
            retval:

        Returns:
            A dictionary which maps names to
            :class:`Destinations<pypdf.generic.Destination>`.
        """
        pass

    def get_fields(self, tree: Optional[TreeObject]=None, retval: Optional[Dict[Any, Any]]=None, fileobj: Optional[Any]=None, stack: Optional[List[PdfObject]]=None) -> Optional[Dict[str, Any]]:
        """
        Extract field data if this PDF contains interactive form fields.

        The *tree*, *retval*, *stack* parameters are for recursive use.

        Args:
            tree: Current object to parse.
            retval: In-progress list of fields.
            fileobj: A file object (usually a text file) to write
                a report to on all interactive form fields found.
            stack: List of already parsed objects.

        Returns:
            A dictionary where each key is a field name, and each
            value is a :class:`Field<pypdf.generic.Field>` object. By
            default, the mapping name is used for keys.
            ``None`` if form data could not be located.
        """
        pass

    def get_form_text_fields(self, full_qualified_name: bool=False) -> Dict[str, Any]:
        """
        Retrieve form fields from the document with textual data.

        Args:
            full_qualified_name: to get full name

        Returns:
            A dictionary. The key is the name of the form field,
            the value is the content of the field.

            If the document contains multiple form fields with the same name, the
            second and following will get the suffix .2, .3, ...
        """
        pass

    def get_pages_showing_field(self, field: Union[Field, PdfObject, IndirectObject]) -> List[PageObject]:
        """
        Provides list of pages where the field is called.

        Args:
            field: Field Object, PdfObject or IndirectObject referencing a Field

        Returns:
            List of pages:
                - Empty list:
                    The field has no widgets attached
                    (either hidden field or ancestor field).
                - Single page list:
                    Page where the widget is present
                    (most common).
                - Multi-page list:
                    Field with multiple kids widgets
                    (example: radio buttons, field repeated on multiple pages).
        """
        pass

    @property
    def open_destination(self) -> Union[None, Destination, TextStringObject, ByteStringObject]:
        """
        Property to access the opening destination (``/OpenAction`` entry in
        the PDF catalog). It returns ``None`` if the entry does not exist
        or is not set.

        Raises:
            Exception: If a destination is invalid.
        """
        pass

    @property
    def outline(self) -> OutlineType:
        """
        Read-only property for the outline present in the document
        (i.e., a collection of 'outline items' which are also known as
        'bookmarks').
        """
        pass

    @property
    def threads(self) -> Optional[ArrayObject]:
        """
        Read-only property for the list of threads.

        See §12.4.3 from the PDF 1.7 or 2.0 specification.

        It is an array of dictionaries with "/F" (the first bead in the thread)
        and "/I" (a thread information dictionary containing information about
        the thread, such as its title, author, and creation date) properties or
        None if there are no articles.

        Since PDF 2.0 it can also contain an indirect reference to a metadata
        stream containing information about the thread, such as its title,
        author, and creation date.
        """
        pass

    def get_page_number(self, page: PageObject) -> Optional[int]:
        """
        Retrieve page number of a given PageObject.

        Args:
            page: The page to get page number. Should be
                an instance of :class:`PageObject<pypdf._page.PageObject>`

        Returns:
            The page number or None if page is not found
        """
        pass

    def get_destination_page_number(self, destination: Destination) -> Optional[int]:
        """
        Retrieve page number of a given Destination object.

        Args:
            destination: The destination to get page number.

        Returns:
            The page number or None if page is not found
        """
        pass

    @property
    def pages(self) -> List[PageObject]:
        """
        Property that emulates a list of :class:`PageObject<pypdf._page.PageObject>`.
        This property allows to get a page or a range of pages.

        Note:
            For PdfWriter only: Provides the capability to remove a page/range of
            page from the list (using the del operator). Remember: Only the page
            entry is removed, as the objects beneath can be used elsewhere. A
            solution to completely remove them - if they are not used anywhere - is
            to write to a buffer/temporary file and then load it into a new
            PdfWriter.

        """
        pass

    @property
    def page_labels(self) -> List[str]:
        """
        A list of labels for the pages in this document.

        This property is read-only. The labels are in the order that the pages
        appear in the document.
        """
        pass

    @property
    def page_layout(self) -> Optional[str]:
        """
        Get the page layout currently being used.

        .. list-table:: Valid ``layout`` values
           :widths: 50 200

           * - /NoLayout
             - Layout explicitly not specified
           * - /SinglePage
             - Show one page at a time
           * - /OneColumn
             - Show one column at a time
           * - /TwoColumnLeft
             - Show pages in two columns, odd-numbered pages on the left
           * - /TwoColumnRight
             - Show pages in two columns, odd-numbered pages on the right
           * - /TwoPageLeft
             - Show two pages at a time, odd-numbered pages on the left
           * - /TwoPageRight
             - Show two pages at a time, odd-numbered pages on the right
        """
        pass

    @property
    def page_mode(self) -> Optional[PagemodeType]:
        """
        Get the page mode currently being used.

        .. list-table:: Valid ``mode`` values
           :widths: 50 200

           * - /UseNone
             - Do not show outline or thumbnails panels
           * - /UseOutlines
             - Show outline (aka bookmarks) panel
           * - /UseThumbs
             - Show page thumbnails panel
           * - /FullScreen
             - Fullscreen view
           * - /UseOC
             - Show Optional Content Group (OCG) panel
           * - /UseAttachments
             - Show attachments panel
        """
        pass

    def remove_page(self, page: Union[int, PageObject, IndirectObject], clean: bool=False) -> None:
        """
        Remove page from pages list.

        Args:
            page:
                * :class:`int`: Page number to be removed.
                * :class:`~pypdf._page.PageObject`: page to be removed. If the page appears many times
                  only the first one will be removed.
                * :class:`~pypdf.generic.IndirectObject`: Reference to page to be removed.

            clean: replace PageObject with NullObject to prevent annotations
                or destinations to reference a detached page.
        """
        pass

    def _get_indirect_object(self, num: int, gen: int) -> Optional[PdfObject]:
        """
        Used to ease development.

        This is equivalent to generic.IndirectObject(num,gen,self).get_object()

        Args:
            num: The object number of the indirect object.
            gen: The generation number of the indirect object.

        Returns:
            A PdfObject
        """
        pass

    def decode_permissions(self, permissions_code: int) -> Dict[str, bool]:
        """Take the permissions as an integer, return the allowed access."""
        pass

    @property
    def user_access_permissions(self) -> Optional[UserAccessPermissions]:
        """Get the user access permissions for encrypted documents. Returns None if not encrypted."""
        pass

    @property
    @abstractmethod
    def is_encrypted(self) -> bool:
        """
        Read-only boolean property showing whether this PDF file is encrypted.

        Note that this property, if true, will remain true even after the
        :meth:`decrypt()<pypdf.PdfReader.decrypt>` method is called.
        """
        pass

    def _list_attachments(self) -> List[str]:
        """
        Retrieves the list of filenames of file attachments.

        Returns:
            list of filenames
        """
        pass

    def _get_attachments(self, filename: Optional[str]=None) -> Dict[str, Union[bytes, List[bytes]]]:
        """
        Retrieves all or selected file attachments of the PDF as a dictionary of file names
        and the file data as a bytestring.

        Args:
            filename: If filename is None, then a dictionary of all attachments
                will be returned, where the key is the filename and the value
                is the content. Otherwise, a dictionary with just a single key
                - the filename - and its content will be returned.

        Returns:
            dictionary of filename -> Union[bytestring or List[ByteString]]
            If the filename exists multiple times a list of the different versions will be provided.
        """
        pass

class LazyDict(Mapping[Any, Any]):

    def __init__(self, *args: Any, **kw: Any) -> None:
        self._raw_dict = dict(*args, **kw)

    def __getitem__(self, key: str) -> Any:
        func, arg = self._raw_dict.__getitem__(key)
        return func(arg)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._raw_dict)

    def __len__(self) -> int:
        return len(self._raw_dict)

    def __str__(self) -> str:
        return f'LazyDict(keys={list(self.keys())})'
