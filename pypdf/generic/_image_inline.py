import logging
from io import BytesIO
from .._utils import WHITESPACES, StreamType, read_non_whitespace
from ..errors import PdfReadError
logger = logging.getLogger(__name__)
BUFFER_SIZE = 8192

def extract_inline_AHx(stream: StreamType) -> bytes:
    """
    Extract HexEncoded Stream from Inline Image.
    the stream will be moved onto the EI
    """
    data = b""
    while True:
        char = stream.read(1)
        if char == b'>':
            # Check if it's the end of the hex data
            next_char = stream.read(1)
            if next_char == b'>':
                break
            else:
                data += char + next_char
        elif char in WHITESPACES:
            continue
        else:
            data += char
    
    # Convert hex to bytes
    return bytes.fromhex(data.decode('ascii'))

def extract_inline_A85(stream: StreamType) -> bytes:
    """
    Extract A85 Stream from Inline Image.
    the stream will be moved onto the EI
    """
    data = b""
    while True:
        char = stream.read(1)
        if char == b'~':
            next_char = stream.read(1)
            if next_char == b'>':
                break
            else:
                data += char + next_char
        else:
            data += char
    
    # Decode ASCII85
    from .filters import ASCII85Decode
    return ASCII85Decode.decode(data)

def extract_inline_RL(stream: StreamType) -> bytes:
    """
    Extract RL Stream from Inline Image.
    the stream will be moved onto the EI
    """
    data = BytesIO()
    while True:
        byte = stream.read(1)
        if byte == b'E':
            next_byte = stream.read(1)
            if next_byte == b'I':
                stream.seek(-2, SEEK_CUR)  # Move back before 'EI'
                break
            else:
                data.write(byte + next_byte)
        else:
            data.write(byte)
    
    # Decode RunLength
    from .filters import RunLengthDecode
    return RunLengthDecode.decode(data.getvalue())

def extract_inline_DCT(stream: StreamType) -> bytes:
    """
    Extract DCT (JPEG) Stream from Inline Image.
    the stream will be moved onto the EI
    """
    data = BytesIO()
    while True:
        chunk = stream.read(BUFFER_SIZE)
        if not chunk:
            raise PdfReadError("Inline DCT image is truncated")
        data.write(chunk)
        if b'EI' in chunk:
            break
    
    jpeg_data = data.getvalue()
    ei_pos = jpeg_data.rfind(b'EI')
    if ei_pos == -1:
        raise PdfReadError("Could not find end of inline DCT image")
    
    stream.seek(-(len(jpeg_data) - ei_pos), SEEK_CUR)
    return jpeg_data[:ei_pos]

def extract_inline_default(stream: StreamType) -> bytes:
    """
    Legacy method
    used by default
    """
    data = BytesIO()
    while True:
        byte = stream.read(1)
        if byte == b'E':
            next_byte = stream.read(1)
            if next_byte == b'I':
                stream.seek(-2, SEEK_CUR)  # Move back before 'EI'
                break
            else:
                data.write(byte + next_byte)
        else:
            data.write(byte)
    return data.getvalue()
