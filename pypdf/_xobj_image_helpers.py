"""Code in here is only used by pypdf.filters._xobj_to_image"""
import sys
from io import BytesIO
from typing import Any, List, Tuple, Union, cast
from ._utils import check_if_whitespace_only, logger_warning
from .constants import ColorSpaces
from .errors import PdfReadError
from .generic import ArrayObject, DecodedStreamObject, EncodedStreamObject, IndirectObject, NullObject
if sys.version_info[:2] >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
if sys.version_info[:2] >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias
try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    raise ImportError("pillow is required to do image extraction. It can be installed via 'pip install pypdf[image]'")
mode_str_type: TypeAlias = Literal['', '1', 'RGB', '2bits', '4bits', 'P', 'L', 'RGBA', 'CMYK']
MAX_IMAGE_MODE_NESTING_DEPTH: int = 10

def _get_imagemode(color_space: Union[str, List[Any], Any], color_components: int, prev_mode: mode_str_type, depth: int=0) -> Tuple[mode_str_type, bool]:
    """
    Returns
        Image mode not taking into account mask(transparency)
        ColorInversion is required (like for some DeviceCMYK)
    """
    if depth > MAX_IMAGE_MODE_NESTING_DEPTH:
        return prev_mode, False

    if isinstance(color_space, str):
        if color_space == ColorSpaces.DEVICE_RGB:
            return 'RGB', False
        elif color_space == ColorSpaces.DEVICE_CMYK:
            return 'CMYK', True
        elif color_space == ColorSpaces.DEVICE_GRAY:
            return 'L', False
    elif isinstance(color_space, list) and len(color_space) > 0:
        if color_space[0] == '/ICCBased' and len(color_space) > 1:
            return _get_imagemode(color_space[1], color_components, prev_mode, depth + 1)
        elif color_space[0] == '/Indexed' and len(color_space) > 1:
            return _get_imagemode(color_space[1], color_components, prev_mode, depth + 1)

    if color_components == 1:
        return 'L', False
    elif color_components == 3:
        return 'RGB', False
    elif color_components == 4:
        return 'CMYK', True

    return prev_mode, False

def _handle_flate(size: Tuple[int, int], data: bytes, mode: mode_str_type, color_space: str, colors: int, obj_as_text: str) -> Tuple[Image.Image, str, str, bool]:
    """
    Process image encoded in flateEncode
    Returns img, image_format, extension, color inversion
    """
    try:
        img = Image.frombytes(mode, size, data)
        return img, 'PNG', '.png', mode == 'CMYK'
    except Exception as e:
        logger_warning(f"Error processing FlateDecode image: {e}", __name__)
        try:
            # Fallback to raw mode
            img = Image.frombytes('RAW', size, data)
            return img, 'PNG', '.png', False
        except Exception as e2:
            logger_warning(f"Error processing FlateDecode image in raw mode: {e2}", __name__)
            raise PdfReadError(f"Failed to process FlateDecode image: {e2}")

def _handle_jpx(size: Tuple[int, int], data: bytes, mode: mode_str_type, color_space: str, colors: int) -> Tuple[Image.Image, str, str, bool]:
    """
    Process image encoded in JPXDecode
    Returns img, image_format, extension, inversion
    """
    try:
        img = Image.open(BytesIO(data))
        if img.mode != mode:
            img = img.convert(mode)
        return img, 'JPEG2000', '.jp2', mode == 'CMYK'
    except Exception as e:
        logger_warning(f"Error processing JPXDecode image: {e}", __name__)
        raise PdfReadError(f"Failed to process JPXDecode image: {e}")
