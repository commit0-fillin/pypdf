import collections
import decimal
import enum
import hashlib
import re
import uuid
from io import BytesIO, FileIO, IOBase
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Callable, Deque, Dict, Iterable, List, Optional, Pattern, Tuple, Type, Union, cast
from ._cmap import _default_fonts_space_width, build_char_map_from_dict
from ._doc_common import PdfDocCommon
from ._encryption import EncryptAlgorithm, Encryption
from ._page import PageObject
from ._page_labels import nums_clear_range, nums_insert, nums_next
from ._reader import PdfReader
from ._utils import StrByteType, StreamType, _get_max_pdf_version_header, b_, deprecate_with_replacement, logger_warning
from .constants import AnnotationDictionaryAttributes as AA
from .constants import CatalogAttributes as CA
from .constants import CatalogDictionary, FileSpecificationDictionaryEntries, GoToActionArguments, ImageType, InteractiveFormDictEntries, PageLabelStyle, TypFitArguments, UserAccessPermissions
from .constants import Core as CO
from .constants import FieldDictionaryAttributes as FA
from .constants import PageAttributes as PG
from .constants import PagesAttributes as PA
from .constants import TrailerKeys as TK
from .errors import PyPdfError
from .generic import PAGE_FIT, ArrayObject, BooleanObject, ByteStringObject, ContentStream, DecodedStreamObject, Destination, DictionaryObject, Fit, FloatObject, IndirectObject, NameObject, NullObject, NumberObject, PdfObject, RectangleObject, StreamObject, TextStringObject, TreeObject, ViewerPreferences, create_string_object, hex_to_rgb
from .pagerange import PageRange, PageRangeSpec
from .types import AnnotationSubtype, BorderArrayType, LayoutType, OutlineItemType, OutlineType, PagemodeType
from .xmp import XmpInformation
ALL_DOCUMENT_PERMISSIONS = UserAccessPermissions.all()
DEFAULT_FONT_HEIGHT_IN_MULTILINE = 12

class ObjectDeletionFlag(enum.IntFlag):
    NONE = 0
    TEXT = enum.auto()
    LINKS = enum.auto()
    ATTACHMENTS = enum.auto()
    OBJECTS_3D = enum.auto()
    ALL_ANNOTATIONS = enum.auto()
    XOBJECT_IMAGES = enum.auto()
    INLINE_IMAGES = enum.auto()
    DRAWING_IMAGES = enum.auto()
    IMAGES = XOBJECT_IMAGES | INLINE_IMAGES | DRAWING_IMAGES

class PdfWriter(PdfDocCommon):
    """
    Write a PDF file out, given pages produced by another class or through
    cloning a PDF file during initialization.

    Typically data is added from a :class:`PdfReader<pypdf.PdfReader>`.
    """

    def __init__(self, fileobj: Union[None, PdfReader, StrByteType, Path]='', clone_from: Union[None, PdfReader, StrByteType, Path]=None) -> None:
        self._header = b'%PDF-1.3'
        self._objects: List[PdfObject] = []
        'The indirect objects in the PDF.'
        self._idnum_hash: Dict[bytes, IndirectObject] = {}
        'Maps hash values of indirect objects to their IndirectObject instances.'
        self._id_translated: Dict[int, Dict[int, int]] = {}
        pages = DictionaryObject()
        pages.update({NameObject(PA.TYPE): NameObject('/Pages'), NameObject(PA.COUNT): NumberObject(0), NameObject(PA.KIDS): ArrayObject()})
        self._pages = self._add_object(pages)
        self.flattened_pages = []
        info = DictionaryObject()
        info.update({NameObject('/Producer'): create_string_object('pypdf')})
        self._info_obj: PdfObject = self._add_object(info)
        self._root_object = DictionaryObject()
        self._root_object.update({NameObject(PA.TYPE): NameObject(CO.CATALOG), NameObject(CO.PAGES): self._pages})
        self._root = self._add_object(self._root_object)

        def _get_clone_from(fileobj: Union[None, PdfReader, str, Path, IO[Any], BytesIO], clone_from: Union[None, PdfReader, str, Path, IO[Any], BytesIO]) -> Union[None, PdfReader, str, Path, IO[Any], BytesIO]:
            if not isinstance(fileobj, (str, Path, IO, BytesIO)) or (fileobj != '' and clone_from is None):
                cloning = True
                if not (not isinstance(fileobj, (str, Path)) or (Path(str(fileobj)).exists() and Path(str(fileobj)).stat().st_size > 0)):
                    cloning = False
                if isinstance(fileobj, (IO, BytesIO)):
                    t = fileobj.tell()
                    fileobj.seek(-1, 2)
                    if fileobj.tell() == 0:
                        cloning = False
                    fileobj.seek(t, 0)
                if cloning:
                    clone_from = fileobj
            return clone_from
        clone_from = _get_clone_from(fileobj, clone_from)
        self.temp_fileobj = fileobj
        self.fileobj = ''
        self.with_as_usage = False
        if clone_from is not None:
            if not isinstance(clone_from, PdfReader):
                clone_from = PdfReader(clone_from)
            self.clone_document_from_reader(clone_from)
        self._encryption: Optional[Encryption] = None
        self._encrypt_entry: Optional[DictionaryObject] = None
        self._ID: Union[ArrayObject, None] = None

    @property
    def is_encrypted(self) -> bool:
        """
        Read-only boolean property showing whether this PDF file is encrypted.

        Note that this property, if true, will remain true even after the
        :meth:`decrypt()<pypdf.PdfReader.decrypt>` method is called.
        """
        return self._encryption is not None

    @property
    def root_object(self) -> DictionaryObject:
        """
        Provide direct access to PDF Structure.

        Note:
            Recommended only for read access.
        """
        return self._root_object

    @property
    def _info(self) -> Optional[DictionaryObject]:
        """
        Provide access to "/Info". Standardized with PdfReader.

        Returns:
            /Info Dictionary; None if the entry does not exist
        """
        return self._info_obj if isinstance(self._info_obj, DictionaryObject) else None

    @property
    def xmp_metadata(self) -> Optional[XmpInformation]:
        """XMP (Extensible Metadata Platform) data."""
        if "/Metadata" not in self._root_object:
            return None
        return XmpInformation(self._root_object["/Metadata"])

    @xmp_metadata.setter
    def xmp_metadata(self, value: Optional[XmpInformation]) -> None:
        """XMP (Extensible Metadata Platform) data."""
        if value is None:
            del self._root_object["/Metadata"]
        else:
            self._root_object[NameObject("/Metadata")] = value.xmp_document

    def __enter__(self) -> 'PdfWriter':
        """Store that writer is initialized by 'with'."""
        t = self.temp_fileobj
        self.__init__()
        self.with_as_usage = True
        self.fileobj = t
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        """Write data to the fileobj."""
        if self.fileobj:
            self.write(self.fileobj)

    def _repr_mimebundle_(self, include: Union[None, Iterable[str]]=None, exclude: Union[None, Iterable[str]]=None) -> Dict[str, Any]:
        """
        Integration into Jupyter Notebooks.

        This method returns a dictionary that maps a mime-type to its
        representation.

        See https://ipython.readthedocs.io/en/stable/config/integrating.html
        """
        from io import BytesIO
        
        buffer = BytesIO()
        self.write(buffer)
        buffer.seek(0)
        
        data = buffer.getvalue()
        
        return {
            'application/pdf': data,
            'text/plain': f'PDF document, version {self.pdf_header[5:]}',
        }

    @property
    def pdf_header(self) -> str:
        """
        Read/Write property of the PDF header that is written.

        This should be something like ``'%PDF-1.5'``. It is recommended to set
        the lowest version that supports all features which are used within the
        PDF file.

        Note: `pdf_header` returns a string but accepts bytes or str for writing
        """
        return self._header.decode('ascii')

    @pdf_header.setter
    def pdf_header(self, value: Union[str, bytes]) -> None:
        if isinstance(value, str):
            value = value.encode('ascii')
        self._header = value

    def set_need_appearances_writer(self, state: bool=True) -> None:
        """
        Sets the "NeedAppearances" flag in the PDF writer.

        The "NeedAppearances" flag indicates whether the appearance dictionary
        for form fields should be automatically generated by the PDF viewer or
        if the embedded appearance should be used.

        Args:
            state: The actual value of the NeedAppearances flag.

        Returns:
            None
        """
        if "/AcroForm" not in self._root_object:
            self._root_object[NameObject("/AcroForm")] = DictionaryObject()

        need_appearances = NameObject("/NeedAppearances")
        self._root_object["/AcroForm"][need_appearances] = BooleanObject(state)

    def add_page(self, page: PageObject, excluded_keys: Iterable[str]=()) -> PageObject:
        """
        Add a page to this PDF file.

        Recommended for advanced usage including the adequate excluded_keys.

        The page is usually acquired from a :class:`PdfReader<pypdf.PdfReader>`
        instance.

        Args:
            page: The page to add to the document. Should be
                an instance of :class:`PageObject<pypdf._page.PageObject>`
            excluded_keys:

        Returns:
            The added PageObject.
        """
        pass

    def insert_page(self, page: PageObject, index: int=0, excluded_keys: Iterable[str]=()) -> PageObject:
        """
        Insert a page in this PDF file. The page is usually acquired from a
        :class:`PdfReader<pypdf.PdfReader>` instance.

        Args:
            page: The page to add to the document.
            index: Position at which the page will be inserted.
            excluded_keys:

        Returns:
            The added PageObject.
        """
        pass

    def _get_page_number_by_indirect(self, indirect_reference: Union[None, int, NullObject, IndirectObject]) -> Optional[int]:
        """
        Generate _page_id2num.

        Args:
            indirect_reference:

        Returns:
            The page number or None
        """
        pass

    def add_blank_page(self, width: Optional[float]=None, height: Optional[float]=None) -> PageObject:
        """
        Append a blank page to this PDF file and return it.

        If no page size is specified, use the size of the last page.

        Args:
            width: The width of the new page expressed in default user
                space units.
            height: The height of the new page expressed in default
                user space units.

        Returns:
            The newly appended page.

        Raises:
            PageSizeNotDefinedError: if width and height are not defined
                and previous page does not exist.
        """
        pass

    def insert_blank_page(self, width: Optional[Union[float, decimal.Decimal]]=None, height: Optional[Union[float, decimal.Decimal]]=None, index: int=0) -> PageObject:
        """
        Insert a blank page to this PDF file and return it.

        If no page size is specified, use the size of the last page.

        Args:
            width: The width of the new page expressed in default user
                space units.
            height: The height of the new page expressed in default
                user space units.
            index: Position to add the page.

        Returns:
            The newly inserted page.

        Raises:
            PageSizeNotDefinedError: if width and height are not defined
                and previous page does not exist.
        """
        pass

    def add_js(self, javascript: str) -> None:
        """
        Add JavaScript which will launch upon opening this PDF.

        Args:
            javascript: Your Javascript.

        >>> output.add_js("this.print({bUI:true,bSilent:false,bShrinkToFit:true});")
        # Example: This will launch the print window when the PDF is opened.
        """
        pass

    def add_attachment(self, filename: str, data: Union[str, bytes]) -> None:
        """
        Embed a file inside the PDF.

        Reference:
        https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf
        Section 7.11.3

        Args:
            filename: The filename to display.
            data: The data in the file.
        """
        pass

    def append_pages_from_reader(self, reader: PdfReader, after_page_append: Optional[Callable[[PageObject], None]]=None) -> None:
        """
        Copy pages from reader to writer. Includes an optional callback
        parameter which is invoked after pages are appended to the writer.

        ``append`` should be preferred.

        Args:
            reader: a PdfReader object from which to copy page
                annotations to this writer object. The writer's annots
                will then be updated.
            after_page_append:
                Callback function that is invoked after each page is appended to
                the writer. Signature includes a reference to the appended page
                (delegates to append_pages_from_reader). The single parameter of
                the callback is a reference to the page just appended to the
                document.
        """
        pass
    FFBITS_NUL = FA.FfBits(0)

    def update_page_form_field_values(self, page: Union[PageObject, List[PageObject], None], fields: Dict[str, Any], flags: FA.FfBits=FFBITS_NUL, auto_regenerate: Optional[bool]=True) -> None:
        """
        Update the form field values for a given page from a fields dictionary.

        Copy field texts and values from fields to page.
        If the field links to a parent object, add the information to the parent.

        Args:
            page: `PageObject` - references **PDF writer's page** where the
                annotations and field data will be updated.
                `List[Pageobject]` - provides list of pages to be processed.
                `None` - all pages.
            fields: a Python dictionary of:

                * field names (/T) as keys and text values (/V) as value
                * field names (/T) as keys and list of text values (/V) for multiple choice list
                * field names (/T) as keys and tuple of:
                    * text values (/V)
                    * font id (e.g. /F1, the font id must exist)
                    * font size (0 for autosize)

            flags: A set of flags from :class:`~pypdf.constants.FieldDictionaryAttributes.FfBits`.

            auto_regenerate: Set/unset the need_appearances flag;
                the flag is unchanged if auto_regenerate is None.
        """
        pass

    def reattach_fields(self, page: Optional[PageObject]=None) -> List[DictionaryObject]:
        """
        Parse annotations within the page looking for orphan fields and
        reattach then into the Fields Structure.

        Args:
            page: page to analyze.
                  If none is provided, all pages will be analyzed.

        Returns:
            list of reattached fields.
        """
        pass

    def clone_reader_document_root(self, reader: PdfReader) -> None:
        """
        Copy the reader document root to the writer and all sub-elements,
        including pages, threads, outlines,... For partial insertion, ``append``
        should be considered.

        Args:
            reader: PdfReader from which the document root should be copied.
        """
        pass

    def clone_document_from_reader(self, reader: PdfReader, after_page_append: Optional[Callable[[PageObject], None]]=None) -> None:
        """
        Create a copy (clone) of a document from a PDF file reader cloning
        section '/Root' and '/Info' and '/ID' of the pdf.

        Args:
            reader: PDF file reader instance from which the clone
                should be created.
            after_page_append:
                Callback function that is invoked after each page is appended to
                the writer. Signature includes a reference to the appended page
                (delegates to append_pages_from_reader). The single parameter of
                the callback is a reference to the page just appended to the
                document.
        """
        pass

    def generate_file_identifiers(self) -> None:
        """
        Generate an identifier for the PDF that will be written.

        The only point of this is ensuring uniqueness. Reproducibility is not
        required.
        When a file is first written, both identifiers shall be set to the same value.
        If both identifiers match when a file reference is resolved, it is very
        likely that the correct and unchanged file has been found. If only the first
        identifier matches, a different version of the correct file has been found.
        see 14.4 "File Identifiers".
        """
        pass

    def encrypt(self, user_password: str, owner_password: Optional[str]=None, use_128bit: bool=True, permissions_flag: UserAccessPermissions=ALL_DOCUMENT_PERMISSIONS, *, algorithm: Optional[str]=None) -> None:
        """
        Encrypt this PDF file with the PDF Standard encryption handler.

        Args:
            user_password: The password which allows for opening
                and reading the PDF file with the restrictions provided.
            owner_password: The password which allows for
                opening the PDF files without any restrictions. By default,
                the owner password is the same as the user password.
            use_128bit: flag as to whether to use 128bit
                encryption. When false, 40bit encryption will be used.
                By default, this flag is on.
            permissions_flag: permissions as described in
                Table 3.20 of the PDF 1.7 specification. A bit value of 1 means
                the permission is granted.
                Hence an integer value of -1 will set all flags.
                Bit position 3 is for printing, 4 is for modifying content,
                5 and 6 control annotations, 9 for form fields,
                10 for extraction of text and graphics.
            algorithm: encrypt algorithm. Values may be one of "RC4-40", "RC4-128",
                "AES-128", "AES-256-R5", "AES-256". If it is valid,
                `use_128bit` will be ignored.
        """
        pass

    def write(self, stream: Union[Path, StrByteType]) -> Tuple[bool, IO[Any]]:
        """
        Write the collection of pages added to this object out as a PDF file.

        Args:
            stream: An object to write the file to. The object can support
                the write method and the tell method, similar to a file object, or
                be a file path, just like the fileobj, just named it stream to keep
                existing workflow.

        Returns:
            A tuple (bool, IO).
        """
        if isinstance(stream, (str, Path)):
            with open(stream, "wb") as fp:
                return self._write(fp)
        else:
            return self._write(stream)

    def _write(self, stream: IO[Any]) -> Tuple[bool, IO[Any]]:
        stream.write(self._header + b"\n")
        
        for obj in self._objects:
            obj.write_to_stream(stream)
        
        xref_location = stream.tell()
        stream.write(b"xref\n")
        stream.write(f"0 {len(self._objects) + 1}\n".encode())
        stream.write(b"0000000000 65535 f \n")
        
        for obj in self._objects:
            stream.write(f"{obj.offset:010d} 00000 n \n".encode())
        
        self._write_trailer(stream, xref_location)
        
        return (True, stream)

    def _write_trailer(self, stream: StreamType, xref_location: int) -> None:
        """
        Write the PDF trailer to the stream.

        To quote the PDF specification:
            [The] trailer [gives] the location of the cross-reference table and
            of certain special objects within the body of the file.
        """
        pass

    def add_metadata(self, infos: Dict[str, Any]) -> None:
        """
        Add custom metadata to the output.

        Args:
            infos: a Python dictionary where each key is a field
                and each value is your new metadata.
        """
        if not isinstance(self._info_obj, DictionaryObject):
            self._info_obj = DictionaryObject()

        for key, value in infos.items():
            if isinstance(value, (str, bool, int, float)):
                self._info_obj[NameObject('/' + key)] = create_string_object(str(value))
            elif isinstance(value, datetime):
                self._info_obj[NameObject('/' + key)] = create_string_object(value.strftime("D:%Y%m%d%H%M%S"))
            else:
                raise TypeError(f"Metadata value for {key} must be a string, bool, int, float, or datetime")

    def _sweep_indirect_references(self, root: Union[ArrayObject, BooleanObject, DictionaryObject, FloatObject, IndirectObject, NameObject, PdfObject, NumberObject, TextStringObject, NullObject]) -> None:
        """
        Resolving any circular references to Page objects.

        Circular references to Page objects can arise when objects such as
        annotations refer to their associated page. If these references are not
        properly handled, the PDF file will contain multiple copies of the same
        Page object. To address this problem, Page objects store their original
        object reference number. This method adds the reference number of any
        circularly referenced Page objects to an external reference map. This
        ensures that self-referencing trees reference the correct new object
        location, rather than copying in a new copy of the Page object.

        Args:
            root: The root of the PDF object tree to sweep.
        """
        pass

    def _resolve_indirect_object(self, data: IndirectObject) -> IndirectObject:
        """
        Resolves an indirect object to an indirect object in this PDF file.

        If the input indirect object already belongs to this PDF file, it is
        returned directly. Otherwise, the object is retrieved from the input
        object's PDF file using the object's ID number and generation number. If
        the object cannot be found, a warning is logged and a `NullObject` is
        returned.

        If the object is not already in this PDF file, it is added to the file's
        list of objects and assigned a new ID number and generation number of 0.
        The hash value of the object is then added to the `_idnum_hash`
        dictionary, with the corresponding `IndirectObject` reference as the
        value.

        Args:
            data: The `IndirectObject` to resolve.

        Returns:
            The resolved `IndirectObject` in this PDF file.

        Raises:
            ValueError: If the input stream is closed.
        """
        pass

    def get_threads_root(self) -> ArrayObject:
        """
        The list of threads.

        See §12.4.3 of the PDF 1.7 or PDF 2.0 specification.

        Returns:
            An array (possibly empty) of Dictionaries with ``/F`` and
            ``/I`` properties.
        """
        pass

    @property
    def threads(self) -> ArrayObject:
        """
        Read-only property for the list of threads.

        See §8.3.2 from PDF 1.7 spec.

        Each element is a dictionaries with ``/F`` and ``/I`` keys.
        """
        pass

    def add_outline_item(self, title: str, page_number: Union[None, PageObject, IndirectObject, int], parent: Union[None, TreeObject, IndirectObject]=None, before: Union[None, TreeObject, IndirectObject]=None, color: Optional[Union[Tuple[float, float, float], str]]=None, bold: bool=False, italic: bool=False, fit: Fit=PAGE_FIT, is_open: bool=True) -> IndirectObject:
        """
        Add an outline item (commonly referred to as a "Bookmark") to the PDF file.

        Args:
            title: Title to use for this outline item.
            page_number: Page number this outline item will point to.
            parent: A reference to a parent outline item to create nested
                outline items.
            before:
            color: Color of the outline item's font as a red, green, blue tuple
                from 0.0 to 1.0 or as a Hex String (#RRGGBB)
            bold: Outline item font is bold
            italic: Outline item font is italic
            fit: The fit of the destination page.

        Returns:
            The added outline item as an indirect object.
        """
        if isinstance(page_number, PageObject):
            page_number = self.get_page_number(page_number)
        elif isinstance(page_number, IndirectObject):
            page_number = self.get_page_number(page_number.get_object())

        if color is not None:
            if isinstance(color, str):
                color = hex_to_rgb(color)
            color = ArrayObject([FloatObject(c) for c in color])

        outline_item = TreeObject()
        outline_item.update({
            NameObject("/Title"): TextStringObject(title),
            NameObject("/Dest"): Destination(NameObject("/Fit"), NumberObject(page_number), fit).dest_array
        })

        if color:
            outline_item[NameObject("/C")] = color
        if bold or italic:
            format_flag = 0
            if bold:
                format_flag |= 2
            if italic:
                format_flag |= 1
            outline_item[NameObject("/F")] = NumberObject(format_flag)
        if is_open:
            outline_item[NameObject("/Count")] = NumberObject(1)

        if parent is None:
            parent = self._root_object.get("/Outlines", None)
            if parent is None:
                parent = TreeObject()
                self._root_object[NameObject("/Outlines")] = self._add_object(parent)

        parent = cast(TreeObject, parent)
        if "/Count" not in parent:
            parent[NameObject("/Count")] = NumberObject(0)
        parent[NameObject("/Count")] = NumberObject(parent[NameObject("/Count")] + 1)

        if before is None:
            parent[NameObject("/Last")] = outline_item
            if "/First" not in parent:
                parent[NameObject("/First")] = outline_item
        else:
            outline_item[NameObject("/Next")] = before
            outline_item[NameObject("/Prev")] = before.get("/Prev", None)
            if before.get("/Prev", None) is not None:
                before["/Prev"][NameObject("/Next")] = outline_item
            else:
                parent[NameObject("/First")] = outline_item
            before[NameObject("/Prev")] = outline_item

        outline_item[NameObject("/Parent")] = parent
        return self._add_object(outline_item)

    def remove_links(self) -> None:
        """Remove links and annotations from this output."""
        pass

    def remove_annotations(self, subtypes: Optional[Union[AnnotationSubtype, Iterable[AnnotationSubtype]]]) -> None:
        """
        Remove annotations by annotation subtype.

        Args:
            subtypes: subtype or list of subtypes to be removed.
                Examples are: "/Link", "/FileAttachment", "/Sound",
                "/Movie", "/Screen", ...
                If you want to remove all annotations, use subtypes=None.
        """
        pass

    def remove_objects_from_page(self, page: Union[PageObject, DictionaryObject], to_delete: Union[ObjectDeletionFlag, Iterable[ObjectDeletionFlag]]) -> None:
        """
        Remove objects specified by ``to_delete`` from the given page.

        Args:
            page: Page object to clean up.
            to_delete: Objects to be deleted; can be a ``ObjectDeletionFlag``
                or a list of ObjectDeletionFlag
        """
        pass

    def remove_images(self, to_delete: ImageType=ImageType.ALL) -> None:
        """
        Remove images from this output.

        Args:
            to_delete : The type of images to be deleted
                (default = all images types)
        """
        pass

    def remove_text(self) -> None:
        """Remove text from this output."""
        pass

    def add_uri(self, page_number: int, uri: str, rect: RectangleObject, border: Optional[ArrayObject]=None) -> None:
        """
        Add an URI from a rectangular area to the specified page.

        Args:
            page_number: index of the page on which to place the URI action.
            uri: URI of resource to link to.
            rect: :class:`RectangleObject<pypdf.generic.RectangleObject>` or
                array of four integers specifying the clickable rectangular area
                ``[xLL, yLL, xUR, yUR]``, or string in the form
                ``"[ xLL yLL xUR yUR ]"``.
            border: if provided, an array describing border-drawing
                properties. See the PDF spec for details. No border will be
                drawn if this argument is omitted.
        """
        pass
    _valid_layouts = ('/NoLayout', '/SinglePage', '/OneColumn', '/TwoColumnLeft', '/TwoColumnRight', '/TwoPageLeft', '/TwoPageRight')

    def _set_page_layout(self, layout: Union[NameObject, LayoutType]) -> None:
        """
        Set the page layout.

        Args:
            layout: The page layout to be used.

        .. list-table:: Valid ``layout`` arguments
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

    def set_page_layout(self, layout: LayoutType) -> None:
        """
        Set the page layout.

        Args:
            layout: The page layout to be used

        .. list-table:: Valid ``layout`` arguments
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
        if not isinstance(layout, NameObject):
            if layout not in self._valid_layouts:
                raise ValueError(f"Layout should be one of: {', '.join(self._valid_layouts)}")
            layout = NameObject(layout)
        self._root_object[NameObject("/PageLayout")] = layout

    @property
    def page_layout(self) -> Optional[LayoutType]:
        """
        Page layout property.

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
    _valid_modes = ('/UseNone', '/UseOutlines', '/UseThumbs', '/FullScreen', '/UseOC', '/UseAttachments')

    @property
    def page_mode(self) -> Optional[PagemodeType]:
        """
        Page mode property.

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
        return self._root_object.get("/PageMode", None)

    @page_mode.setter
    def page_mode(self, value: PagemodeType) -> None:
        self.set_page_mode(value)

    def add_annotation(self, page_number: Union[int, PageObject], annotation: Dict[str, Any]) -> DictionaryObject:
        """
        Add a single annotation to the page.
        The added annotation must be a new annotation.
        It cannot be recycled.

        Args:
            page_number: PageObject or page index.
            annotation: Annotation to be added (created with annotation).

        Returns:
            The inserted object.
            This can be used for popup creation, for example.
        """
        pass

    def clean_page(self, page: Union[PageObject, IndirectObject]) -> PageObject:
        """
        Perform some clean up in the page.
        Currently: convert NameObject named destination to TextStringObject
        (required for names/dests list)

        Args:
            page:

        Returns:
            The cleaned PageObject
        """
        pass

    def append(self, fileobj: Union[StrByteType, PdfReader, Path], outline_item: Union[str, None, PageRange, Tuple[int, int], Tuple[int, int, int], List[int]]=None, pages: Union[None, PageRange, Tuple[int, int], Tuple[int, int, int], List[int], List[PageObject]]=None, import_outline: bool=True, excluded_fields: Optional[Union[List[str], Tuple[str, ...]]]=None) -> None:
        """
        Identical to the :meth:`merge()<merge>` method, but assumes you want to
        concatenate all pages onto the end of the file instead of specifying a
        position.

        Args:
            fileobj: A File Object or an object that supports the standard
                read and seek methods similar to a File Object. Could also be a
                string representing a path to a PDF file.
            outline_item: Optionally, you may specify a string to build an
                outline (aka 'bookmark') to identify the beginning of the
                included file.
            pages: Can be a :class:`PageRange<pypdf.pagerange.PageRange>`
                or a ``(start, stop[, step])`` tuple
                or a list of pages to be processed
                to merge only the specified range of pages from the source
                document into the output document.
            import_outline: You may prevent the source document's
                outline (collection of outline items, previously referred to as
                'bookmarks') from being imported by specifying this as ``False``.
            excluded_fields: Provide the list of fields/keys to be ignored
                if ``/Annots`` is part of the list, the annotation will be ignored
                if ``/B`` is part of the list, the articles will be ignored
        """
        self.merge(None, fileobj, outline_item, pages, import_outline, excluded_fields)

    def merge(self, position: Optional[int], fileobj: Union[Path, StrByteType, PdfReader], outline_item: Optional[str]=None, pages: Optional[Union[PageRangeSpec, List[PageObject]]]=None, import_outline: bool=True, excluded_fields: Optional[Union[List[str], Tuple[str, ...]]]=()) -> None:
        """
        Merge the pages from the given file into the output file at the
        specified page number.

        Args:
            position: The *page number* to insert this file. File will
                be inserted after the given number.
            fileobj: A File Object or an object that supports the standard
                read and seek methods similar to a File Object. Could also be a
                string representing a path to a PDF file.
            outline_item: Optionally, you may specify a string to build an outline
                (aka 'bookmark') to identify the
                beginning of the included file.
            pages: can be a :class:`PageRange<pypdf.pagerange.PageRange>`
                or a ``(start, stop[, step])`` tuple
                or a list of pages to be processed
                to merge only the specified range of pages from the source
                document into the output document.
            import_outline: You may prevent the source document's
                outline (collection of outline items, previously referred to as
                'bookmarks') from being imported by specifying this as ``False``.
            excluded_fields: provide the list of fields/keys to be ignored
                if ``/Annots`` is part of the list, the annotation will be ignored
                if ``/B`` is part of the list, the articles will be ignored

        Raises:
            TypeError: The pages attribute is not configured properly
        """
        if not isinstance(fileobj, PdfReader):
            fileobj = PdfReader(fileobj)

        if pages is None:
            pages = list(range(len(fileobj.pages)))
        elif isinstance(pages, PageRange):
            pages = list(range(*pages.indices(len(fileobj.pages))))
        elif isinstance(pages, tuple):
            pages = list(range(*pages))
        elif not isinstance(pages, list):
            raise TypeError("pages must be a list, tuple, or PageRange object")

        if position is None:
            position = len(self.pages)

        for i, page in enumerate(pages):
            if isinstance(page, int):
                page_obj = fileobj.pages[page]
            else:
                page_obj = page

            self.insert_page(page_obj, position + i, excluded_fields=excluded_fields)

        if outline_item is not None:
            self.add_outline_item(outline_item, position + 1)

        if import_outline:
            outline = fileobj.outline
            if outline:
                self._add_outline_from_reader(outline, position)

    def _add_outline_from_reader(self, outline, position):
        for item in outline:
            if isinstance(item, list):
                self._add_outline_from_reader(item, position)
            else:
                page_number = item.page.page_number if item.page else None
                if page_number is not None:
                    new_page_number = position + page_number + 1
                    self.add_outline_item(item.title, new_page_number)

    def _add_articles_thread(self, thread: DictionaryObject, pages: Dict[int, PageObject], reader: PdfReader) -> IndirectObject:
        """
        Clone the thread with only the applicable articles.

        Args:
            thread:
            pages:
            reader:

        Returns:
            The added thread as an indirect reference
        """
        pass

    def add_filtered_articles(self, fltr: Union[Pattern[Any], str], pages: Dict[int, PageObject], reader: PdfReader) -> None:
        """
        Add articles matching the defined criteria.

        Args:
            fltr:
            pages:
            reader:
        """
        pass

    def _get_filtered_outline(self, node: Any, pages: Dict[int, PageObject], reader: PdfReader) -> List[Destination]:
        """
        Extract outline item entries that are part of the specified page set.

        Args:
            node:
            pages:
            reader:

        Returns:
            A list of destination objects.
        """
        pass

    def close(self) -> None:
        """Implemented for API harmonization."""
        # Since PdfWriter doesn't open any resources that need to be closed,
        # this method is essentially a no-op.
        pass

    def find_bookmark(self, outline_item: Dict[str, Any], root: Optional[OutlineType]=None) -> Optional[List[int]]:
        """
        .. deprecated:: 2.9.0
            Use :meth:`find_outline_item` instead.
        """
        pass

    def reset_translation(self, reader: Union[None, PdfReader, IndirectObject]=None) -> None:
        """
        Reset the translation table between reader and the writer object.

        Late cloning will create new independent objects.

        Args:
            reader: PdfReader or IndirectObject referencing a PdfReader object.
                if set to None or omitted, all tables will be reset.
        """
        pass

    def set_page_label(self, page_index_from: int, page_index_to: int, style: Optional[PageLabelStyle]=None, prefix: Optional[str]=None, start: Optional[int]=0) -> None:
        """
        Set a page label to a range of pages.

        Page indexes must be given starting from 0.
        Labels must have a style, a prefix or both.
        If to a range is not assigned any page label a decimal label starting from 1 is applied.

        Args:
            page_index_from: page index of the beginning of the range starting from 0
            page_index_to: page index of the beginning of the range starting from 0
            style: The numbering style to be used for the numeric portion of each page label:

                       * ``/D`` Decimal arabic numerals
                       * ``/R`` Uppercase roman numerals
                       * ``/r`` Lowercase roman numerals
                       * ``/A`` Uppercase letters (A to Z for the first 26 pages,
                         AA to ZZ for the next 26, and so on)
                       * ``/a`` Lowercase letters (a to z for the first 26 pages,
                         aa to zz for the next 26, and so on)

            prefix: The label prefix for page labels in this range.
            start:  The value of the numeric portion for the first page label
                    in the range.
                    Subsequent pages are numbered sequentially from this value,
                    which must be greater than or equal to 1.
                    Default value: 1.
        """
        pass

    def _set_page_label(self, page_index_from: int, page_index_to: int, style: Optional[PageLabelStyle]=None, prefix: Optional[str]=None, start: Optional[int]=0) -> None:
        """
        Set a page label to a range of pages.

        Page indexes must be given
        starting from 0. Labels must have a style, a prefix or both. If to a
        range is not assigned any page label a decimal label starting from 1 is
        applied.

        Args:
            page_index_from: page index of the beginning of the range starting from 0
            page_index_to: page index of the beginning of the range starting from 0
            style:  The numbering style to be used for the numeric portion of each page label:
                        /D Decimal arabic numerals
                        /R Uppercase roman numerals
                        /r Lowercase roman numerals
                        /A Uppercase letters (A to Z for the first 26 pages,
                           AA to ZZ for the next 26, and so on)
                        /a Lowercase letters (a to z for the first 26 pages,
                           aa to zz for the next 26, and so on)
            prefix: The label prefix for page labels in this range.
            start:  The value of the numeric portion for the first page label
                    in the range.
                    Subsequent pages are numbered sequentially from this value,
                    which must be greater than or equal to 1. Default value: 1.
        """
        pass
