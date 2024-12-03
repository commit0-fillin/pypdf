__author__ = 'Mathieu Fenniak'
__author_email__ = 'biziqe@mathieu.fenniak.net'
import logging
import re
import sys
from io import BytesIO
from math import ceil
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union, cast
from .._protocols import PdfReaderProtocol, PdfWriterProtocol, XmpInformationProtocol
from .._utils import WHITESPACES, StreamType, b_, deprecate_no_replacement, deprecate_with_replacement, logger_warning, read_non_whitespace, read_until_regex, skip_over_comment
from ..constants import CheckboxRadioButtonAttributes, FieldDictionaryAttributes, OutlineFontFlag
from ..constants import FilterTypes as FT
from ..constants import StreamAttributes as SA
from ..constants import TypArguments as TA
from ..constants import TypFitArguments as TF
from ..errors import STREAM_TRUNCATED_PREMATURELY, PdfReadError, PdfStreamError
from ._base import BooleanObject, ByteStringObject, FloatObject, IndirectObject, NameObject, NullObject, NumberObject, PdfObject, TextStringObject
from ._fit import Fit
from ._image_inline import extract_inline_A85, extract_inline_AHx, extract_inline_DCT, extract_inline_default, extract_inline_RL
from ._utils import read_hex_string_from_stream, read_string_from_stream
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self
logger = logging.getLogger(__name__)
NumberSigns = b'+-'
IndirectPattern = re.compile(b'[+-]?(\\d+)\\s+(\\d+)\\s+R[^a-zA-Z]')

class ArrayObject(List[Any], PdfObject):

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'ArrayObject':
        """Clone object into pdf_dest."""
        cloned_array = ArrayObject()
        for item in self:
            if isinstance(item, PdfObject):
                cloned_item = item.clone(pdf_dest, force_duplicate, ignore_fields)
            else:
                cloned_item = item
            cloned_array.append(cloned_item)
        return cloned_array

    def items(self) -> Iterable[Any]:
        """Emulate DictionaryObject.items for a list (index, object)."""
        return enumerate(self)

    def __add__(self, lst: Any) -> 'ArrayObject':
        """
        Allow extension by adding list or add one element only

        Args:
            lst: any list, tuples are extended the list.
            other types(numbers,...) will be appended.
            if str is passed it will be converted into TextStringObject
            or NameObject (if starting with "/")
            if bytes is passed it will be converted into ByteStringObject

        Returns:
            ArrayObject with all elements
        """
        temp = ArrayObject(self)
        temp.extend(self._to_lst(lst))
        return temp

    def __iadd__(self, lst: Any) -> Self:
        """
         Allow extension by adding list or add one element only

        Args:
            lst: any list, tuples are extended the list.
            other types(numbers,...) will be appended.
            if str is passed it will be converted into TextStringObject
            or NameObject (if starting with "/")
            if bytes is passed it will be converted into ByteStringObject
        """
        self.extend(self._to_lst(lst))
        return self

    def __isub__(self, lst: Any) -> Self:
        """Allow to remove items"""
        to_remove = self._to_lst(lst)
        self[:] = [item for item in self if item not in to_remove]
        return self

class DictionaryObject(Dict[Any, Any], PdfObject):

    def clone(self, pdf_dest: PdfWriterProtocol, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'DictionaryObject':
        """Clone object into pdf_dest."""
        cloned_dict = DictionaryObject()
        for key, value in self.items():
            if key not in ignore_fields:
                if isinstance(value, PdfObject):
                    cloned_value = value.clone(pdf_dest, force_duplicate, ignore_fields)
                else:
                    cloned_value = value
                cloned_dict[key] = cloned_value
        return cloned_dict

    def _clone(self, src: 'DictionaryObject', pdf_dest: PdfWriterProtocol, force_duplicate: bool, ignore_fields: Optional[Sequence[Union[str, int]]], visited: Set[Tuple[int, int]]) -> None:
        """
        Update the object from src.

        Args:
            src: "DictionaryObject":
            pdf_dest:
            force_duplicate:
            ignore_fields:
        """
        pass

    def get_inherited(self, key: str, default: Any=None) -> Any:
        """
        Returns the value of a key or from the parent if not found.
        If not found returns default.

        Args:
            key: string identifying the field to return

            default: default value to return

        Returns:
            Current key or inherited one, otherwise default value.
        """
        try:
            return self[key]
        except KeyError:
            if "/Parent" in self:
                parent = self["/Parent"]
                if isinstance(parent, DictionaryObject):
                    return parent.get_inherited(key, default)
        return default

    def __setitem__(self, key: Any, value: Any) -> Any:
        if not isinstance(key, PdfObject):
            raise ValueError('key must be PdfObject')
        if not isinstance(value, PdfObject):
            raise ValueError('value must be PdfObject')
        return dict.__setitem__(self, key, value)

    def __getitem__(self, key: Any) -> PdfObject:
        return dict.__getitem__(self, key).get_object()

    @property
    def xmp_metadata(self) -> Optional[XmpInformationProtocol]:
        """
        Retrieve XMP (Extensible Metadata Platform) data relevant to the this
        object, if available.

        See Table 347 — Additional entries in a metadata stream dictionary.

        Returns:
          Returns a :class:`~pypdf.xmp.XmpInformation` instance
          that can be used to access XMP metadata from the document. Can also
          return None if no metadata was found on the document root.
        """
        from ..xmp import XmpInformation

        metadata = self.get("/Metadata", None)
        if metadata is None:
            return None
        metadata = metadata.get_object()

        if not isinstance(metadata, XmpInformation):
            metadata = XmpInformation(metadata)
            self[NameObject("/Metadata")] = metadata
        return metadata

class TreeObject(DictionaryObject):

    def __init__(self, dct: Optional[DictionaryObject]=None) -> None:
        DictionaryObject.__init__(self)
        if dct:
            self.update(dct)

    def __iter__(self) -> Any:
        return self.children()

    def _remove_node_from_tree(self, prev: Any, prev_ref: Any, cur: Any, last: Any) -> None:
        """
        Adjust the pointers of the linked list and tree node count.

        Args:
            prev:
            prev_ref:
            cur:
            last:
        """
        if prev is None:
            if last == cur:
                self[NameObject("/First")] = None
                self[NameObject("/Last")] = None
            else:
                self[NameObject("/First")] = cur[NameObject("/Next")]
            cur[NameObject("/Next")][NameObject("/Prev")] = None
        elif last == cur:
            self[NameObject("/Last")] = prev
            prev[NameObject("/Next")] = None
        else:
            prev[NameObject("/Next")] = cur[NameObject("/Next")]
            cur[NameObject("/Next")][NameObject("/Prev")] = prev_ref

        self[NameObject("/Count")] = NumberObject(self[NameObject("/Count")] - 1)

    def remove_from_tree(self) -> None:
        """Remove the object from the tree it is in."""
        if "/Parent" not in self:
            return
        parent = self["/Parent"]
        prev = None
        prev_ref = None
        cur = parent["/First"]
        last = parent["/Last"]
        while cur is not None:
            if cur.indirect_reference == self.indirect_reference:
                parent._remove_node_from_tree(prev, prev_ref, cur, last)
                break
            prev = cur
            prev_ref = cur.indirect_reference
            cur = cur["/Next"]
        _reset_node_tree_relationship(self)

def _reset_node_tree_relationship(child_obj: Any) -> None:
    """
    Call this after a node has been removed from a tree.

    This resets the nodes attributes in respect to that tree.

    Args:
        child_obj:
    """
    del child_obj["/Parent"]
    if "/Next" in child_obj:
        del child_obj["/Next"]
    if "/Prev" in child_obj:
        del child_obj["/Prev"]

class StreamObject(DictionaryObject):

    def __init__(self) -> None:
        self._data: Union[bytes, str] = b''
        self.decoded_self: Optional[DecodedStreamObject] = None

    def _clone(self, src: DictionaryObject, pdf_dest: PdfWriterProtocol, force_duplicate: bool, ignore_fields: Optional[Sequence[Union[str, int]]], visited: Set[Tuple[int, int]]) -> None:
        """
        Update the object from src.

        Args:
            src:
            pdf_dest:
            force_duplicate:
            ignore_fields:
        """
        super()._clone(src, pdf_dest, force_duplicate, ignore_fields, visited)
        self._data = src._data
        if hasattr(src, 'decoded_self'):
            self.decoded_self = src.decoded_self

    def decode_as_image(self) -> Any:
        """
        Try to decode the stream object as an image

        Returns:
            a PIL image if proper decoding has been found
        Raises:
            Exception: (any)during decoding to to invalid object or
                errors during decoding will be reported
                It is recommended to catch exceptions to prevent
                stops in your program.
        """
        from PIL import Image
        import io

        if '/Filter' in self:
            data = self.get_data()
            if self['/Filter'] == '/FlateDecode':
                img = Image.open(io.BytesIO(data))
                return img
            elif self['/Filter'] == '/DCTDecode':
                img = Image.open(io.BytesIO(data))
                return img
            else:
                raise NotImplementedError(f"Decoding filter {self['/Filter']} is not supported")
        else:
            raise ValueError("No filter found in stream object")

class DecodedStreamObject(StreamObject):
    pass

class EncodedStreamObject(StreamObject):

    def __init__(self) -> None:
        self.decoded_self: Optional[DecodedStreamObject] = None

class ContentStream(DecodedStreamObject):
    """
    In order to be fast, this data structure can contain either:

    * raw data in ._data
    * parsed stream operations in ._operations.

    At any time, ContentStream object can either have both of those fields defined,
    or one field defined and the other set to None.

    These fields are "rebuilt" lazily, when accessed:

    * when .get_data() is called, if ._data is None, it is rebuilt from ._operations.
    * when .operations is called, if ._operations is None, it is rebuilt from ._data.

    Conversely, these fields can be invalidated:

    * when .set_data() is called, ._operations is set to None.
    * when .operations is set, ._data is set to None.
    """

    def __init__(self, stream: Any, pdf: Any, forced_encoding: Union[None, str, List[str], Dict[int, str]]=None) -> None:
        self.pdf = pdf
        self._operations: List[Tuple[Any, Any]] = []
        if stream is None:
            super().set_data(b'')
        else:
            stream = stream.get_object()
            if isinstance(stream, ArrayObject):
                data = b''
                for s in stream:
                    data += b_(s.get_object().get_data())
                    if len(data) == 0 or data[-1] != b'\n':
                        data += b'\n'
                super().set_data(bytes(data))
            else:
                stream_data = stream.get_data()
                assert stream_data is not None
                super().set_data(b_(stream_data))
            self.forced_encoding = forced_encoding

    def clone(self, pdf_dest: Any, force_duplicate: bool=False, ignore_fields: Optional[Sequence[Union[str, int]]]=()) -> 'ContentStream':
        """
        Clone object into pdf_dest.

        Args:
            pdf_dest:
            force_duplicate:
            ignore_fields:

        Returns:
            The cloned ContentStream
        """
        cloned = ContentStream(self, pdf_dest)
        cloned._operations = [op.clone() for op in self._operations]
        cloned.forced_encoding = self.forced_encoding
        return cloned

    def _clone(self, src: DictionaryObject, pdf_dest: PdfWriterProtocol, force_duplicate: bool, ignore_fields: Optional[Sequence[Union[str, int]]], visited: Set[Tuple[int, int]]) -> None:
        """
        Update the object from src.

        Args:
            src:
            pdf_dest:
            force_duplicate:
            ignore_fields:
        """
        super()._clone(src, pdf_dest, force_duplicate, ignore_fields, visited)
        if isinstance(src, ContentStream):
            self._operations = [op.clone() for op in src._operations]
            self.forced_encoding = src.forced_encoding

class Field(TreeObject):
    """
    A class representing a field dictionary.

    This class is accessed through
    :meth:`get_fields()<pypdf.PdfReader.get_fields>`
    """

    def __init__(self, data: DictionaryObject) -> None:
        DictionaryObject.__init__(self)
        field_attributes = FieldDictionaryAttributes.attributes() + CheckboxRadioButtonAttributes.attributes()
        self.indirect_reference = data.indirect_reference
        for attr in field_attributes:
            try:
                self[NameObject(attr)] = data[attr]
            except KeyError:
                pass
        if isinstance(self.get('/V'), EncodedStreamObject):
            d = cast(EncodedStreamObject, self[NameObject('/V')]).get_data()
            if isinstance(d, bytes):
                d_str = d.decode('utf-8', errors='replace')
            elif d is None:
                d_str = ''
            else:
                raise ValueError(f'Unexpected type for /V: {type(d)}')
            self[NameObject('/V')] = TextStringObject(d_str)

    @property
    def field_type(self) -> Optional[NameObject]:
        """Read-only property accessing the type of this field."""
        return self.get("/FT")

    @property
    def parent(self) -> Optional[DictionaryObject]:
        """Read-only property accessing the parent of this field."""
        return self.get("/Parent")

    @property
    def kids(self) -> Optional['ArrayObject']:
        """Read-only property accessing the kids of this field."""
        return self.get("/Kids")

    @property
    def name(self) -> Optional[str]:
        """Read-only property accessing the name of this field."""
        return self.get("/T")

    @property
    def alternate_name(self) -> Optional[str]:
        """Read-only property accessing the alternate name of this field."""
        return self.get("/TU")

    @property
    def mapping_name(self) -> Optional[str]:
        """
        Read-only property accessing the mapping name of this field.

        This name is used by pypdf as a key in the dictionary returned by
        :meth:`get_fields()<pypdf.PdfReader.get_fields>`
        """
        return self.get("/TM")

    @property
    def flags(self) -> Optional[int]:
        """
        Read-only property accessing the field flags, specifying various
        characteristics of the field (see Table 8.70 of the PDF 1.7 reference).
        """
        return self.get("/Ff")

    @property
    def value(self) -> Optional[Any]:
        """
        Read-only property accessing the value of this field.

        Format varies based on field type.
        """
        return self.get("/V")

    @property
    def default_value(self) -> Optional[Any]:
        """Read-only property accessing the default value of this field."""
        return self.get("/DV")

    @property
    def additional_actions(self) -> Optional[DictionaryObject]:
        """
        Read-only property accessing the additional actions dictionary.

        This dictionary defines the field's behavior in response to trigger
        events. See Section 8.5.2 of the PDF 1.7 reference.
        """
        return self.get("/AA")

class Destination(TreeObject):
    """
    A class representing a destination within a PDF file.

    See section 12.3.2 of the PDF 2.0 reference.

    Args:
        title: Title of this destination.
        page: Reference to the page of this destination. Should
            be an instance of :class:`IndirectObject<pypdf.generic.IndirectObject>`.
        fit: How the destination is displayed.

    Raises:
        PdfReadError: If destination type is invalid.
    """
    node: Optional[DictionaryObject] = None

    def __init__(self, title: str, page: Union[NumberObject, IndirectObject, NullObject, DictionaryObject], fit: Fit) -> None:
        self._filtered_children: List[Any] = []
        typ = fit.fit_type
        args = fit.fit_args
        DictionaryObject.__init__(self)
        self[NameObject('/Title')] = TextStringObject(title)
        self[NameObject('/Page')] = page
        self[NameObject('/Type')] = typ
        if typ == '/XYZ':
            if len(args) < 1:
                args.append(NumberObject(0.0))
            if len(args) < 2:
                args.append(NumberObject(0.0))
            if len(args) < 3:
                args.append(NumberObject(0.0))
            self[NameObject(TA.LEFT)], self[NameObject(TA.TOP)], self[NameObject('/Zoom')] = args
        elif len(args) == 0:
            pass
        elif typ == TF.FIT_R:
            self[NameObject(TA.LEFT)], self[NameObject(TA.BOTTOM)], self[NameObject(TA.RIGHT)], self[NameObject(TA.TOP)] = args
        elif typ in [TF.FIT_H, TF.FIT_BH]:
            try:
                self[NameObject(TA.TOP)], = args
            except Exception:
                self[NameObject(TA.TOP)], = (NullObject(),)
        elif typ in [TF.FIT_V, TF.FIT_BV]:
            try:
                self[NameObject(TA.LEFT)], = args
            except Exception:
                self[NameObject(TA.LEFT)], = (NullObject(),)
        elif typ in [TF.FIT, TF.FIT_B]:
            pass
        else:
            raise PdfReadError(f'Unknown Destination Type: {typ!r}')

    @property
    def title(self) -> Optional[str]:
        """Read-only property accessing the destination title."""
        return self.get("/Title")

    @property
    def page(self) -> Optional[int]:
        """Read-only property accessing the destination page number."""
        page = self.get("/Page")
        if isinstance(page, IndirectObject):
            return page.idnum
        return None

    @property
    def typ(self) -> Optional[str]:
        """Read-only property accessing the destination type."""
        return self.get("/Type")

    @property
    def zoom(self) -> Optional[int]:
        """Read-only property accessing the zoom factor."""
        return self.get("/Zoom")

    @property
    def left(self) -> Optional[FloatObject]:
        """Read-only property accessing the left horizontal coordinate."""
        return self.get("/Left")

    @property
    def right(self) -> Optional[FloatObject]:
        """Read-only property accessing the right horizontal coordinate."""
        return self.get("/Right")

    @property
    def top(self) -> Optional[FloatObject]:
        """Read-only property accessing the top vertical coordinate."""
        return self.get("/Top")

    @property
    def bottom(self) -> Optional[FloatObject]:
        """Read-only property accessing the bottom vertical coordinate."""
        return self.get("/Bottom")

    @property
    def color(self) -> Optional['ArrayObject']:
        """Read-only property accessing the color in (R, G, B) with values 0.0-1.0."""
        return self.get("/C")

    @property
    def font_format(self) -> Optional[OutlineFontFlag]:
        """
        Read-only property accessing the font type.

        1=italic, 2=bold, 3=both
        """
        return OutlineFontFlag(self.get("/F", 0))

    @property
    def outline_count(self) -> Optional[int]:
        """
        Read-only property accessing the outline count.

        positive = expanded
        negative = collapsed
        absolute value = number of visible descendants at all levels
        """
        return self.get("/Count")
