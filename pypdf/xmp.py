"""
Anything related to Extensible Metadata Platform (XMP) metadata.

https://en.wikipedia.org/wiki/Extensible_Metadata_Platform
"""
import datetime
import decimal
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, Union
from xml.dom.minidom import Document, parseString
from xml.dom.minidom import Element as XmlElement
from xml.parsers.expat import ExpatError
from ._utils import StreamType, deprecate_no_replacement
from .errors import PdfReadError
from .generic import ContentStream, PdfObject
RDF_NAMESPACE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
DC_NAMESPACE = 'http://purl.org/dc/elements/1.1/'
XMP_NAMESPACE = 'http://ns.adobe.com/xap/1.0/'
PDF_NAMESPACE = 'http://ns.adobe.com/pdf/1.3/'
XMPMM_NAMESPACE = 'http://ns.adobe.com/xap/1.0/mm/'
PDFX_NAMESPACE = 'http://ns.adobe.com/pdfx/1.3/'
iso8601 = re.compile('\n        (?P<year>[0-9]{4})\n        (-\n            (?P<month>[0-9]{2})\n            (-\n                (?P<day>[0-9]+)\n                (T\n                    (?P<hour>[0-9]{2}):\n                    (?P<minute>[0-9]{2})\n                    (:(?P<second>[0-9]{2}(.[0-9]+)?))?\n                    (?P<tzd>Z|[-+][0-9]{2}:[0-9]{2})\n                )?\n            )?\n        )?\n        ', re.VERBOSE)
K = TypeVar('K')

class XmpInformation(PdfObject):
    """
    An object that represents Extensible Metadata Platform (XMP) metadata.
    Usually accessed by :py:attr:`xmp_metadata()<pypdf.PdfReader.xmp_metadata>`.

    Raises:
      PdfReadError: if XML is invalid
    """

    def __init__(self, stream: ContentStream) -> None:
        self.stream = stream
        try:
            data = self.stream.get_data()
            doc_root: Document = parseString(data)
        except ExpatError as e:
            raise PdfReadError(f'XML in XmpInformation was invalid: {e}')
        self.rdf_root: XmlElement = doc_root.getElementsByTagNameNS(RDF_NAMESPACE, 'RDF')[0]
        self.cache: Dict[Any, Any] = {}
    dc_contributor = property(_getter_bag(DC_NAMESPACE, 'contributor'))
    '\n    Contributors to the resource (other than the authors).\n\n    An unsorted array of names.\n    '
    dc_coverage = property(_getter_single(DC_NAMESPACE, 'coverage'))
    'Text describing the extent or scope of the resource.'
    dc_creator = property(_getter_seq(DC_NAMESPACE, 'creator'))
    'A sorted array of names of the authors of the resource, listed in order\n    of precedence.'
    dc_date = property(_getter_seq(DC_NAMESPACE, 'date', _converter_date))
    '\n    A sorted array of dates (datetime.datetime instances) of significance to\n    the resource.\n\n    The dates and times are in UTC.\n    '
    dc_description = property(_getter_langalt(DC_NAMESPACE, 'description'))
    'A language-keyed dictionary of textual descriptions of the content of the\n    resource.'
    dc_format = property(_getter_single(DC_NAMESPACE, 'format'))
    'The mime-type of the resource.'
    dc_identifier = property(_getter_single(DC_NAMESPACE, 'identifier'))
    'Unique identifier of the resource.'
    dc_language = property(_getter_bag(DC_NAMESPACE, 'language'))
    'An unordered array specifying the languages used in the resource.'
    dc_publisher = property(_getter_bag(DC_NAMESPACE, 'publisher'))
    'An unordered array of publisher names.'
    dc_relation = property(_getter_bag(DC_NAMESPACE, 'relation'))
    'An unordered array of text descriptions of relationships to other\n    documents.'
    dc_rights = property(_getter_langalt(DC_NAMESPACE, 'rights'))
    'A language-keyed dictionary of textual descriptions of the rights the\n    user has to this resource.'
    dc_source = property(_getter_single(DC_NAMESPACE, 'source'))
    'Unique identifier of the work from which this resource was derived.'
    dc_subject = property(_getter_bag(DC_NAMESPACE, 'subject'))
    'An unordered array of descriptive phrases or keywrods that specify the\n    topic of the content of the resource.'
    dc_title = property(_getter_langalt(DC_NAMESPACE, 'title'))
    'A language-keyed dictionary of the title of the resource.'
    dc_type = property(_getter_bag(DC_NAMESPACE, 'type'))
    'An unordered array of textual descriptions of the document type.'
    pdf_keywords = property(_getter_single(PDF_NAMESPACE, 'Keywords'))
    'An unformatted text string representing document keywords.'
    pdf_pdfversion = property(_getter_single(PDF_NAMESPACE, 'PDFVersion'))
    'The PDF file version, for example 1.0 or 1.3.'
    pdf_producer = property(_getter_single(PDF_NAMESPACE, 'Producer'))
    'The name of the tool that created the PDF document.'
    xmp_create_date = property(_getter_single(XMP_NAMESPACE, 'CreateDate', _converter_date))
    '\n    The date and time the resource was originally created.\n\n    The date and time are returned as a UTC datetime.datetime object.\n    '
    xmp_modify_date = property(_getter_single(XMP_NAMESPACE, 'ModifyDate', _converter_date))
    '\n    The date and time the resource was last modified.\n\n    The date and time are returned as a UTC datetime.datetime object.\n    '
    xmp_metadata_date = property(_getter_single(XMP_NAMESPACE, 'MetadataDate', _converter_date))
    '\n    The date and time that any metadata for this resource was last changed.\n\n    The date and time are returned as a UTC datetime.datetime object.\n    '
    xmp_creator_tool = property(_getter_single(XMP_NAMESPACE, 'CreatorTool'))
    'The name of the first known tool used to create the resource.'
    xmpmm_document_id = property(_getter_single(XMPMM_NAMESPACE, 'DocumentID'))
    'The common identifier for all versions and renditions of this resource.'
    xmpmm_instance_id = property(_getter_single(XMPMM_NAMESPACE, 'InstanceID'))
    'An identifier for a specific incarnation of a document, updated each\n    time a file is saved.'

    @property
    def custom_properties(self) -> Dict[Any, Any]:
        """
        Retrieve custom metadata properties defined in the undocumented pdfx
        metadata schema.

        Returns:
            A dictionary of key/value items for custom metadata properties.
        """
        if "/pdfx:pdfx" not in self.cache:
            self.cache["/pdfx:pdfx"] = {}
            for element in self.rdf_root.getElementsByTagNameNS(PDFX_NAMESPACE, "pdfx"):
                for child in element.childNodes:
                    if child.nodeType == child.ELEMENT_NODE:
                        key = child.localName
                        value = child.firstChild.nodeValue if child.firstChild else None
                        self.cache["/pdfx:pdfx"][key] = value
        return self.cache["/pdfx:pdfx"]
