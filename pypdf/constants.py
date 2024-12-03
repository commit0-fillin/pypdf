"""
PDF Specification Archive
https://pdfa.org/resource/pdf-specification-archive/

Portable Document Format Reference Manual, 1993. ISBN 0-201-62628-4
https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.0.pdf

ISO 32000-1:2008 (PDF 1.7)
https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf

ISO 32000-2:2020 (PDF 2.0)
"""
from enum import IntFlag, auto
from typing import Dict, Tuple
from ._utils import classproperty, deprecate_with_replacement

class Core:
    """Keywords that don't quite belong anywhere else."""
    OUTLINES = '/Outlines'
    THREADS = '/Threads'
    PAGE = '/Page'
    PAGES = '/Pages'
    CATALOG = '/Catalog'

class TrailerKeys:
    ROOT = '/Root'
    ENCRYPT = '/Encrypt'
    ID = '/ID'
    INFO = '/Info'
    SIZE = '/Size'

class CatalogAttributes:
    NAMES = '/Names'
    DESTS = '/Dests'

class EncryptionDictAttributes:
    """
    Additional encryption dictionary entries for the standard security handler.

    Table 3.19, Page 122.
    Table 21 of the 2.0 manual.
    """
    R = '/R'
    O = '/O'
    U = '/U'
    P = '/P'
    ENCRYPT_METADATA = '/EncryptMetadata'

class UserAccessPermissions(IntFlag):
    """
    Table 3.20 User access permissions.
    Table 22 of the 2.0 manual.
    """
    R1 = 1
    R2 = 2
    PRINT = 4
    MODIFY = 8
    EXTRACT = 16
    ADD_OR_MODIFY = 32
    R7 = 64
    R8 = 128
    FILL_FORM_FIELDS = 256
    EXTRACT_TEXT_AND_GRAPHICS = 512
    ASSEMBLE_DOC = 1024
    PRINT_TO_REPRESENTATION = 2048
    R13 = 2 ** 12
    R14 = 2 ** 13
    R15 = 2 ** 14
    R16 = 2 ** 15
    R17 = 2 ** 16
    R18 = 2 ** 17
    R19 = 2 ** 18
    R20 = 2 ** 19
    R21 = 2 ** 20
    R22 = 2 ** 21
    R23 = 2 ** 22
    R24 = 2 ** 23
    R25 = 2 ** 24
    R26 = 2 ** 25
    R27 = 2 ** 26
    R28 = 2 ** 27
    R29 = 2 ** 28
    R30 = 2 ** 29
    R31 = 2 ** 30
    R32 = 2 ** 31

    @classmethod
    def _is_reserved(cls, name: str) -> bool:
        """Check if the given name corresponds to a reserved flag entry."""
        return name.startswith('R') and name[1:].isdigit()

    @classmethod
    def _is_active(cls, name: str) -> bool:
        """Check if the given reserved name defaults to 1 = active."""
        return name in {'R1', 'R2', 'R7', 'R8', 'R13', 'R14', 'R15', 'R16', 'R17', 'R18', 'R19', 'R20', 'R21', 'R22', 'R23', 'R24', 'R25', 'R26', 'R27', 'R28', 'R29', 'R30', 'R31', 'R32'}

    def to_dict(self) -> Dict[str, bool]:
        """Convert the given flag value to a corresponding verbose name mapping."""
        return {name: bool(self & value) for name, value in self.__class__.__members__.items() if not self._is_reserved(name)}

    @classmethod
    def from_dict(cls, value: Dict[str, bool]) -> 'UserAccessPermissions':
        """Convert the verbose name mapping to the corresponding flag value."""
        flags = cls(0)
        for name, is_set in value.items():
            if is_set:
                flags |= cls[name]
        return flags

class Resources:
    """
    Table 3.30 Entries in a resource dictionary.
    Used to be Ressources (a misspelling).

    Table 34 in the 2.0 reference.
    """
    EXT_G_STATE = '/ExtGState'
    COLOR_SPACE = '/ColorSpace'
    PATTERN = '/Pattern'
    SHADING = '/Shading'
    XOBJECT = '/XObject'
    FONT = '/Font'
    PROC_SET = '/ProcSet'
    PROPERTIES = '/Properties'

class Ressources:
    """
    Use :class: `Resources` instead.

    .. deprecated:: 5.0.0
    """

class PagesAttributes:
    """§7.7.3.2 of the 1.7 and 2.0 reference."""
    TYPE = '/Type'
    PARENT = '/Parent'
    KIDS = '/Kids'
    COUNT = '/Count'

class PageAttributes:
    """§7.7.3.3 of the 1.7 and 2.0 reference."""
    TYPE = '/Type'
    PARENT = '/Parent'
    LAST_MODIFIED = '/LastModified'
    RESOURCES = '/Resources'
    MEDIABOX = '/MediaBox'
    CROPBOX = '/CropBox'
    BLEEDBOX = '/BleedBox'
    TRIMBOX = '/TrimBox'
    ARTBOX = '/ArtBox'
    BOX_COLOR_INFO = '/BoxColorInfo'
    CONTENTS = '/Contents'
    ROTATE = '/Rotate'
    GROUP = '/Group'
    THUMB = '/Thumb'
    B = '/B'
    DUR = '/Dur'
    TRANS = '/Trans'
    ANNOTS = '/Annots'
    AA = '/AA'
    METADATA = '/Metadata'
    PIECE_INFO = '/PieceInfo'
    STRUCT_PARENTS = '/StructParents'
    ID = '/ID'
    PZ = '/PZ'
    SEPARATION_INFO = '/SeparationInfo'
    TABS = '/Tabs'
    TEMPLATE_INSTANTIATED = '/TemplateInstantiated'
    PRES_STEPS = '/PresSteps'
    USER_UNIT = '/UserUnit'
    VP = '/VP'
    AF = '/AF'
    OUTPUT_INTENTS = '/OutputIntents'
    D_PART = '/DPart'

class FileSpecificationDictionaryEntries:
    """Table 3.41 Entries in a file specification dictionary."""
    Type = '/Type'
    FS = '/FS'
    F = '/F'
    UF = '/UF'
    DOS = '/DOS'
    Mac = '/Mac'
    Unix = '/Unix'
    ID = '/ID'
    V = '/V'
    EF = '/EF'
    RF = '/RF'
    DESC = '/Desc'
    Cl = '/Cl'

class StreamAttributes:
    """
    Table 4.2.
    Table 5 in the 2.0 reference.
    """
    LENGTH = '/Length'
    FILTER = '/Filter'
    DECODE_PARMS = '/DecodeParms'

class FilterTypes:
    """§7.4 of the 1.7 and 2.0 references."""
    ASCII_HEX_DECODE = '/ASCIIHexDecode'
    ASCII_85_DECODE = '/ASCII85Decode'
    LZW_DECODE = '/LZWDecode'
    FLATE_DECODE = '/FlateDecode'
    RUN_LENGTH_DECODE = '/RunLengthDecode'
    CCITT_FAX_DECODE = '/CCITTFaxDecode'
    DCT_DECODE = '/DCTDecode'
    JPX_DECODE = '/JPXDecode'

class FilterTypeAbbreviations:
    """§8.9.7 of the 1.7 and 2.0 references."""
    AHx = '/AHx'
    A85 = '/A85'
    LZW = '/LZW'
    FL = '/Fl'
    RL = '/RL'
    CCF = '/CCF'
    DCT = '/DCT'

class LzwFilterParameters:
    """
    Table 4.4.
    Table 8 in the 2.0 reference.
    """
    PREDICTOR = '/Predictor'
    COLORS = '/Colors'
    BITS_PER_COMPONENT = '/BitsPerComponent'
    COLUMNS = '/Columns'
    EARLY_CHANGE = '/EarlyChange'

class CcittFaxDecodeParameters:
    """
    Table 4.5.
    Table 11 in the 2.0 reference.
    """
    K = '/K'
    END_OF_LINE = '/EndOfLine'
    ENCODED_BYTE_ALIGN = '/EncodedByteAlign'
    COLUMNS = '/Columns'
    ROWS = '/Rows'
    END_OF_BLOCK = '/EndOfBlock'
    BLACK_IS_1 = '/BlackIs1'
    DAMAGED_ROWS_BEFORE_ERROR = '/DamagedRowsBeforeError'

class ImageAttributes:
    """§11.6.5 of the 1.7 and 2.0 references."""
    TYPE = '/Type'
    SUBTYPE = '/Subtype'
    NAME = '/Name'
    WIDTH = '/Width'
    HEIGHT = '/Height'
    BITS_PER_COMPONENT = '/BitsPerComponent'
    COLOR_SPACE = '/ColorSpace'
    DECODE = '/Decode'
    INTENT = '/Intent'
    INTERPOLATE = '/Interpolate'
    IMAGE_MASK = '/ImageMask'
    MASK = '/Mask'
    S_MASK = '/SMask'

class ColorSpaces:
    DEVICE_RGB = '/DeviceRGB'
    DEVICE_CMYK = '/DeviceCMYK'
    DEVICE_GRAY = '/DeviceGray'

class TypArguments:
    """Table 8.2 of the PDF 1.7 reference."""
    LEFT = '/Left'
    RIGHT = '/Right'
    BOTTOM = '/Bottom'
    TOP = '/Top'

class TypFitArguments:
    """Table 8.2 of the PDF 1.7 reference."""
    FIT = '/Fit'
    FIT_V = '/FitV'
    FIT_BV = '/FitBV'
    FIT_B = '/FitB'
    FIT_H = '/FitH'
    FIT_BH = '/FitBH'
    FIT_R = '/FitR'
    XYZ = '/XYZ'

class GoToActionArguments:
    S = '/S'
    D = '/D'

class AnnotationDictionaryAttributes:
    """Table 8.15 Entries common to all annotation dictionaries."""
    Type = '/Type'
    Subtype = '/Subtype'
    Rect = '/Rect'
    Contents = '/Contents'
    P = '/P'
    NM = '/NM'
    M = '/M'
    F = '/F'
    AP = '/AP'
    AS = '/AS'
    DA = '/DA'
    Border = '/Border'
    C = '/C'
    StructParent = '/StructParent'
    OC = '/OC'

class InteractiveFormDictEntries:
    Fields = '/Fields'
    NeedAppearances = '/NeedAppearances'
    SigFlags = '/SigFlags'
    CO = '/CO'
    DR = '/DR'
    DA = '/DA'
    Q = '/Q'
    XFA = '/XFA'

class FieldDictionaryAttributes:
    """
    Entries common to all field dictionaries (Table 8.69 PDF 1.7 reference)
    (*very partially documented here*).

    FFBits provides the constants used for `/Ff` from Table 8.70/8.75/8.77/8.79
    """
    FT = '/FT'
    Parent = '/Parent'
    Kids = '/Kids'
    T = '/T'
    TU = '/TU'
    TM = '/TM'
    Ff = '/Ff'
    V = '/V'
    DV = '/DV'
    AA = '/AA'
    Opt = '/Opt'

    class FfBits(IntFlag):
        """
        Ease building /Ff flags
        Some entries may be specific to:

        * Text(Tx) (Table 8.75 PDF 1.7 reference)
        * Buttons(Btn) (Table 8.77 PDF 1.7 reference)
        * List(Ch) (Table 8.79 PDF 1.7 reference)
        """
        ReadOnly = 1 << 0
        'common to Tx/Btn/Ch in Table 8.70'
        Required = 1 << 1
        'common to Tx/Btn/Ch in Table 8.70'
        NoExport = 1 << 2
        'common to Tx/Btn/Ch in Table 8.70'
        Multiline = 1 << 12
        'Tx'
        Password = 1 << 13
        'Tx'
        NoToggleToOff = 1 << 14
        'Btn'
        Radio = 1 << 15
        'Btn'
        Pushbutton = 1 << 16
        'Btn'
        Combo = 1 << 17
        'Ch'
        Edit = 1 << 18
        'Ch'
        Sort = 1 << 19
        'Ch'
        FileSelect = 1 << 20
        'Tx'
        MultiSelect = 1 << 21
        'Tx'
        DoNotSpellCheck = 1 << 22
        'Tx/Ch'
        DoNotScroll = 1 << 23
        'Tx'
        Comb = 1 << 24
        'Tx'
        RadiosInUnison = 1 << 25
        'Btn'
        RichText = 1 << 25
        'Tx'
        CommitOnSelChange = 1 << 26
        'Ch'

    @classmethod
    def attributes(cls) -> Tuple[str, ...]:
        """
        Get a tuple of all the attributes present in a Field Dictionary.

        This method returns a tuple of all the attribute constants defined in
        the FieldDictionaryAttributes class. These attributes correspond to the
        entries that are common to all field dictionaries as specified in the
        PDF 1.7 reference.

        Returns:
            A tuple containing all the attribute constants.
        """
        return tuple(attr for attr in cls.__dict__.keys() if not attr.startswith('_') and isinstance(getattr(cls, attr), str))

    @classmethod
    def attributes_dict(cls) -> Dict[str, str]:
        """
        Get a dictionary of attribute keys and their human-readable names.

        This method returns a dictionary where the keys are the attribute
        constants defined in the FieldDictionaryAttributes class and the values
        are their corresponding human-readable names. These attributes
        correspond to the entries that are common to all field dictionaries as
        specified in the PDF 1.7 reference.

        Returns:
            A dictionary containing attribute keys and their names.
        """
        return {attr: attr.lstrip('/') for attr in cls.attributes()}

class CheckboxRadioButtonAttributes:
    """Table 8.76 Field flags common to all field types."""
    Opt = '/Opt'

    @classmethod
    def attributes(cls) -> Tuple[str, ...]:
        """
        Get a tuple of all the attributes present in a Field Dictionary.

        This method returns a tuple of all the attribute constants defined in
        the CheckboxRadioButtonAttributes class. These attributes correspond to
        the entries that are common to all field dictionaries as specified in
        the PDF 1.7 reference.

        Returns:
            A tuple containing all the attribute constants.
        """
        return tuple(attr for attr in cls.__dict__.keys() if not attr.startswith('_') and isinstance(getattr(cls, attr), str))

    @classmethod
    def attributes_dict(cls) -> Dict[str, str]:
        """
        Get a dictionary of attribute keys and their human-readable names.

        This method returns a dictionary where the keys are the attribute
        constants defined in the CheckboxRadioButtonAttributes class and the
        values are their corresponding human-readable names. These attributes
        correspond to the entries that are common to all field dictionaries as
        specified in the PDF 1.7 reference.

        Returns:
            A dictionary containing attribute keys and their names.
        """
        return {attr: attr.lstrip('/') for attr in cls.attributes()}

class FieldFlag(IntFlag):
    """Table 8.70 Field flags common to all field types."""
    READ_ONLY = 1
    REQUIRED = 2
    NO_EXPORT = 4

class DocumentInformationAttributes:
    """Table 10.2 Entries in the document information dictionary."""
    TITLE = '/Title'
    AUTHOR = '/Author'
    SUBJECT = '/Subject'
    KEYWORDS = '/Keywords'
    CREATOR = '/Creator'
    PRODUCER = '/Producer'
    CREATION_DATE = '/CreationDate'
    MOD_DATE = '/ModDate'
    TRAPPED = '/Trapped'

class PageLayouts:
    """
    Page 84, PDF 1.4 reference.
    Page 115, PDF 2.0 reference.
    """
    SINGLE_PAGE = '/SinglePage'
    ONE_COLUMN = '/OneColumn'
    TWO_COLUMN_LEFT = '/TwoColumnLeft'
    TWO_COLUMN_RIGHT = '/TwoColumnRight'
    TWO_PAGE_LEFT = '/TwoPageLeft'
    TWO_PAGE_RIGHT = '/TwoPageRight'

class GraphicsStateParameters:
    """Table 58 – Entries in a Graphics State Parameter Dictionary"""
    TYPE = '/Type'
    LW = '/LW'
    LC = '/LC'
    LJ = '/LJ'
    ML = '/ML'
    D = '/D'
    RI = '/RI'
    OP = '/OP'
    op = '/op'
    OPM = '/OPM'
    FONT = '/Font'
    BG = '/BG'
    BG2 = '/BG2'
    UCR = '/UCR'
    UCR2 = '/UCR2'
    TR = '/TR'
    TR2 = '/TR2'
    HT = '/HT'
    FL = '/FL'
    SM = '/SM'
    SA = '/SA'
    BM = '/BM'
    S_MASK = '/SMask'
    CA = '/CA'
    ca = '/ca'
    AIS = '/AIS'
    TK = '/TK'

class CatalogDictionary:
    """§7.7.2 of the 1.7 and 2.0 references."""
    TYPE = '/Type'
    VERSION = '/Version'
    EXTENSIONS = '/Extensions'
    PAGES = '/Pages'
    PAGE_LABELS = '/PageLabels'
    NAMES = '/Names'
    DESTS = '/Dests'
    VIEWER_PREFERENCES = '/ViewerPreferences'
    PAGE_LAYOUT = '/PageLayout'
    PAGE_MODE = '/PageMode'
    OUTLINES = '/Outlines'
    THREADS = '/Threads'
    OPEN_ACTION = '/OpenAction'
    AA = '/AA'
    URI = '/URI'
    ACRO_FORM = '/AcroForm'
    METADATA = '/Metadata'
    STRUCT_TREE_ROOT = '/StructTreeRoot'
    MARK_INFO = '/MarkInfo'
    LANG = '/Lang'
    SPIDER_INFO = '/SpiderInfo'
    OUTPUT_INTENTS = '/OutputIntents'
    PIECE_INFO = '/PieceInfo'
    OC_PROPERTIES = '/OCProperties'
    PERMS = '/Perms'
    LEGAL = '/Legal'
    REQUIREMENTS = '/Requirements'
    COLLECTION = '/Collection'
    NEEDS_RENDERING = '/NeedsRendering'
    DSS = '/DSS'
    AF = '/AF'
    D_PART_ROOT = '/DPartRoot'

class OutlineFontFlag(IntFlag):
    """A class used as an enumerable flag for formatting an outline font."""
    italic = 1
    bold = 2

class PageLabelStyle:
    """
    Table 8.10 in the 1.7 reference.
    Table 161 in the 2.0 reference.
    """
    DECIMAL = '/D'
    UPPERCASE_ROMAN = '/R'
    LOWERCASE_ROMAN = '/r'
    UPPERCASE_LETTER = '/A'
    LOWERCASE_LETTER = '/a'

class AnnotationFlag(IntFlag):
    """See §12.5.3 "Annotation Flags"."""
    INVISIBLE = 1
    HIDDEN = 2
    PRINT = 4
    NO_ZOOM = 8
    NO_ROTATE = 16
    NO_VIEW = 32
    READ_ONLY = 64
    LOCKED = 128
    TOGGLE_NO_VIEW = 256
    LOCKED_CONTENTS = 512
PDF_KEYS = (AnnotationDictionaryAttributes, CatalogAttributes, CatalogDictionary, CcittFaxDecodeParameters, CheckboxRadioButtonAttributes, ColorSpaces, Core, DocumentInformationAttributes, EncryptionDictAttributes, FieldDictionaryAttributes, FilterTypeAbbreviations, FilterTypes, GoToActionArguments, GraphicsStateParameters, ImageAttributes, FileSpecificationDictionaryEntries, LzwFilterParameters, PageAttributes, PageLayouts, PagesAttributes, Resources, StreamAttributes, TrailerKeys, TypArguments, TypFitArguments)

class ImageType(IntFlag):
    NONE = 0
    XOBJECT_IMAGES = auto()
    INLINE_IMAGES = auto()
    DRAWING_IMAGES = auto()
    ALL = XOBJECT_IMAGES | INLINE_IMAGES | DRAWING_IMAGES
    IMAGES = ALL
