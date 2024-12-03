import hashlib
import secrets
import struct
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Tuple, Union, cast
from pypdf._crypt_providers import CryptAES, CryptBase, CryptIdentity, CryptRC4, aes_cbc_decrypt, aes_cbc_encrypt, aes_ecb_decrypt, aes_ecb_encrypt, rc4_decrypt, rc4_encrypt
from ._utils import b_, logger_warning
from .generic import ArrayObject, ByteStringObject, DictionaryObject, NameObject, NumberObject, PdfObject, StreamObject, TextStringObject, create_string_object

class CryptFilter:

    def __init__(self, stm_crypt: CryptBase, str_crypt: CryptBase, ef_crypt: CryptBase) -> None:
        self.stm_crypt = stm_crypt
        self.str_crypt = str_crypt
        self.ef_crypt = ef_crypt
_PADDING = b'(\xbfN^Nu\x8aAd\x00NV\xff\xfa\x01\x08..\x00\xb6\xd0h>\x80/\x0c\xa9\xfedSiz'

class AlgV4:

    @staticmethod
    def compute_key(password: bytes, rev: int, key_size: int, o_entry: bytes, P: int, id1_entry: bytes, metadata_encrypted: bool) -> bytes:
        """
        Algorithm 2: Computing an encryption key.

        a) Pad or truncate the password string to exactly 32 bytes. If the
           password string is more than 32 bytes long,
           use only its first 32 bytes; if it is less than 32 bytes long, pad it
           by appending the required number of
           additional bytes from the beginning of the following padding string:
                < 28 BF 4E 5E 4E 75 8A 41 64 00 4E 56 FF FA 01 08
                2E 2E 00 B6 D0 68 3E 80 2F 0C A9 FE 64 53 69 7A >
           That is, if the password string is n bytes long, append
           the first 32 - n bytes of the padding string to the end
           of the password string. If the password string is empty
           (zero-length), meaning there is no user password,
           substitute the entire padding string in its place.

        b) Initialize the MD5 hash function and pass the result of step (a)
           as input to this function.
        c) Pass the value of the encryption dictionary’s O entry to the
           MD5 hash function. ("Algorithm 3: Computing
           the encryption dictionary’s O (owner password) value" shows how the
           O value is computed.)
        d) Convert the integer value of the P entry to a 32-bit unsigned binary
           number and pass these bytes to the
           MD5 hash function, low-order byte first.
        e) Pass the first element of the file’s file identifier array (the value
           of the ID entry in the document’s trailer
           dictionary; see Table 15) to the MD5 hash function.
        f) (Security handlers of revision 4 or greater) If document metadata is
           not being encrypted, pass 4 bytes with
           the value 0xFFFFFFFF to the MD5 hash function.
        g) Finish the hash.
        h) (Security handlers of revision 3 or greater) Do the following
           50 times: Take the output from the previous
           MD5 hash and pass the first n bytes of the output as input into a new
           MD5 hash, where n is the number of
           bytes of the encryption key as defined by the value of the encryption
           dictionary’s Length entry.
        i) Set the encryption key to the first n bytes of the output from the
           final MD5 hash, where n shall always be 5
           for security handlers of revision 2 but, for security handlers of
           revision 3 or greater, shall depend on the
           value of the encryption dictionary’s Length entry.

        Args:
            password: The encryption secret as a bytes-string
            rev: The encryption revision (see PDF standard)
            key_size: The size of the key in bytes
            o_entry: The owner entry
            P: A set of flags specifying which operations shall be permitted
                when the document is opened with user access. If bit 2 is set to 1,
                all other bits are ignored and all operations are permitted.
                If bit 2 is set to 0, permission for operations are based on the
                values of the remaining flags defined in Table 24.
            id1_entry:
            metadata_encrypted: A boolean indicating if the metadata is encrypted.

        Returns:
            The u_hash digest of length key_size
        """
        pass

    @staticmethod
    def compute_O_value_key(owner_password: bytes, rev: int, key_size: int) -> bytes:
        """
        Algorithm 3: Computing the encryption dictionary’s O (owner password) value.

        a) Pad or truncate the owner password string as described in step (a)
           of "Algorithm 2: Computing an encryption key".
           If there is no owner password, use the user password instead.
        b) Initialize the MD5 hash function and pass the result of step (a) as
           input to this function.
        c) (Security handlers of revision 3 or greater) Do the following 50 times:
           Take the output from the previous
           MD5 hash and pass it as input into a new MD5 hash.
        d) Create an RC4 encryption key using the first n bytes of the output
           from the final MD5 hash, where n shall
           always be 5 for security handlers of revision 2 but, for security
           handlers of revision 3 or greater, shall
           depend on the value of the encryption dictionary’s Length entry.
        e) Pad or truncate the user password string as described in step (a) of
           "Algorithm 2: Computing an encryption key".
        f) Encrypt the result of step (e), using an RC4 encryption function with
           the encryption key obtained in step (d).
        g) (Security handlers of revision 3 or greater) Do the following 19 times:
           Take the output from the previous
           invocation of the RC4 function and pass it as input to a new
           invocation of the function; use an encryption
           key generated by taking each byte of the encryption key obtained in
           step (d) and performing an XOR
           (exclusive or) operation between that byte and the single-byte value
           of the iteration counter (from 1 to 19).
        h) Store the output from the final invocation of the RC4 function as
           the value of the O entry in the encryption dictionary.

        Args:
            owner_password:
            rev: The encryption revision (see PDF standard)
            key_size: The size of the key in bytes

        Returns:
            The RC4 key
        """
        pass

    @staticmethod
    def compute_O_value(rc4_key: bytes, user_password: bytes, rev: int) -> bytes:
        """
        See :func:`compute_O_value_key`.

        Args:
            rc4_key:
            user_password:
            rev: The encryption revision (see PDF standard)

        Returns:
            The RC4 encrypted
        """
        # Step e: Pad or truncate the user password
        padded_user_password = user_password[:32] + _PADDING[:max(0, 32 - len(user_password))]

        # Step f: Encrypt the result of step (e) using RC4
        o_value = rc4_encrypt(rc4_key, padded_user_password)

        # Step g: For rev 3 or greater, perform 19 additional iterations
        if rev >= 3:
            for i in range(1, 20):
                new_key = bytes(b ^ i for b in rc4_key)
                o_value = rc4_encrypt(new_key, o_value)

        # Step h: The final o_value is stored as the O entry
        return o_value

    @staticmethod
    def compute_U_value(key: bytes, rev: int, id1_entry: bytes) -> bytes:
        """
        Algorithm 4: Computing the encryption dictionary’s U (user password) value.

        (Security handlers of revision 2)

        a) Create an encryption key based on the user password string, as
           described in "Algorithm 2: Computing an encryption key".
        b) Encrypt the 32-byte padding string shown in step (a) of
           "Algorithm 2: Computing an encryption key", using an RC4 encryption
           function with the encryption key from the preceding step.
        c) Store the result of step (b) as the value of the U entry in the
           encryption dictionary.

        Args:
            key:
            rev: The encryption revision (see PDF standard)
            id1_entry:

        Returns:
            The value
        """
        pass

    @staticmethod
    def verify_user_password(user_password: bytes, rev: int, key_size: int, o_entry: bytes, u_entry: bytes, P: int, id1_entry: bytes, metadata_encrypted: bool) -> bytes:
        """
        Algorithm 6: Authenticating the user password.

        a) Perform all but the last step of "Algorithm 4: Computing the
           encryption dictionary’s U (user password) value (Security handlers of
           revision 2)" or "Algorithm 5: Computing the encryption dictionary’s U
           (user password) value (Security handlers of revision 3 or greater)"
           using the supplied password string.
        b) If the result of step (a) is equal to the value of the encryption
           dictionary’s U entry (comparing on the first 16 bytes in the case of
           security handlers of revision 3 or greater), the password supplied is
           the correct user password. The key obtained in step (a) (that is, in
           the first step of "Algorithm 4: Computing the encryption
           dictionary’s U (user password) value
           (Security handlers of revision 2)" or
           "Algorithm 5: Computing the encryption dictionary’s U (user password)
           value (Security handlers of revision 3 or greater)") shall be used
           to decrypt the document.

        Args:
            user_password: The user password as a bytes stream
            rev: The encryption revision (see PDF standard)
            key_size: The size of the key in bytes
            o_entry: The owner entry
            u_entry: The user entry
            P: A set of flags specifying which operations shall be permitted
                when the document is opened with user access. If bit 2 is set to 1,
                all other bits are ignored and all operations are permitted.
                If bit 2 is set to 0, permission for operations are based on the
                values of the remaining flags defined in Table 24.
            id1_entry:
            metadata_encrypted: A boolean indicating if the metadata is encrypted.

        Returns:
            The key
        """
        pass

    @staticmethod
    def verify_owner_password(owner_password: bytes, rev: int, key_size: int, o_entry: bytes, u_entry: bytes, P: int, id1_entry: bytes, metadata_encrypted: bool) -> bytes:
        """
        Algorithm 7: Authenticating the owner password.

        a) Compute an encryption key from the supplied password string, as
           described in steps (a) to (d) of
           "Algorithm 3: Computing the encryption dictionary’s O (owner password)
           value".
        b) (Security handlers of revision 2 only) Decrypt the value of the
           encryption dictionary’s O entry, using an RC4
           encryption function with the encryption key computed in step (a).
           (Security handlers of revision 3 or greater) Do the following 20 times:
           Decrypt the value of the encryption dictionary’s O entry (first iteration)
           or the output from the previous iteration (all subsequent iterations),
           using an RC4 encryption function with a different encryption key at
           each iteration. The key shall be generated by taking the original key
           (obtained in step (a)) and performing an XOR (exclusive or) operation
           between each byte of the key and the single-byte value of the
           iteration counter (from 19 to 0).
        c) The result of step (b) purports to be the user password.
           Authenticate this user password using
           "Algorithm 6: Authenticating the user password".
           If it is correct, the password supplied is the correct owner password.

        Args:
            owner_password:
            rev: The encryption revision (see PDF standard)
            key_size: The size of the key in bytes
            o_entry: The owner entry
            u_entry: The user entry
            P: A set of flags specifying which operations shall be permitted
                when the document is opened with user access. If bit 2 is set to 1,
                all other bits are ignored and all operations are permitted.
                If bit 2 is set to 0, permission for operations are based on the
                values of the remaining flags defined in Table 24.
            id1_entry:
            metadata_encrypted: A boolean indicating if the metadata is encrypted.

        Returns:
            bytes
        """
        pass

class AlgV5:

    @staticmethod
    def verify_owner_password(R: int, password: bytes, o_value: bytes, oe_value: bytes, u_value: bytes) -> bytes:
        """
        Algorithm 3.2a Computing an encryption key.

        To understand the algorithm below, it is necessary to treat the O and U
        strings in the Encrypt dictionary as made up of three sections.
        The first 32 bytes are a hash value (explained below). The next 8 bytes
        are called the Validation Salt. The final 8 bytes are called the Key Salt.

        1. The password string is generated from Unicode input by processing the
           input string with the SASLprep (IETF RFC 4013) profile of
           stringprep (IETF RFC 3454), and then converting to a UTF-8
           representation.
        2. Truncate the UTF-8 representation to 127 bytes if it is longer than
           127 bytes.
        3. Test the password against the owner key by computing the SHA-256 hash
           of the UTF-8 password concatenated with the 8 bytes of owner
           Validation Salt, concatenated with the 48-byte U string. If the
           32-byte result matches the first 32 bytes of the O string, this is
           the owner password.
           Compute an intermediate owner key by computing the SHA-256 hash of
           the UTF-8 password concatenated with the 8 bytes of owner Key Salt,
           concatenated with the 48-byte U string. The 32-byte result is the
           key used to decrypt the 32-byte OE string using AES-256 in CBC mode
           with no padding and an initialization vector of zero.
           The 32-byte result is the file encryption key.
        4. Test the password against the user key by computing the SHA-256 hash
           of the UTF-8 password concatenated with the 8 bytes of user
           Validation Salt. If the 32 byte result matches the first 32 bytes of
           the U string, this is the user password.
           Compute an intermediate user key by computing the SHA-256 hash of the
           UTF-8 password concatenated with the 8 bytes of user Key Salt.
           The 32-byte result is the key used to decrypt the 32-byte
           UE string using AES-256 in CBC mode with no padding and an
           initialization vector of zero. The 32-byte result is the file
           encryption key.
        5. Decrypt the 16-byte Perms string using AES-256 in ECB mode with an
           initialization vector of zero and the file encryption key as the key.
           Verify that bytes 9-11 of the result are the characters ‘a’, ‘d’, ‘b’.
           Bytes 0-3 of the decrypted Perms entry, treated as a little-endian
           integer, are the user permissions.
           They should match the value in the P key.

        Args:
            R: A number specifying which revision of the standard security
                handler shall be used to interpret this dictionary
            password: The owner password
            o_value: A 32-byte string, based on both the owner and user passwords,
                that shall be used in computing the encryption key and in
                determining whether a valid owner password was entered
            oe_value:
            u_value: A 32-byte string, based on the user password, that shall be
                used in determining whether to prompt the user for a password and,
                if so, whether a valid user or owner password was entered.

        Returns:
            The key
        """
        pass

    @staticmethod
    def verify_user_password(R: int, password: bytes, u_value: bytes, ue_value: bytes) -> bytes:
        """
        See :func:`verify_owner_password`.

        Args:
            R: A number specifying which revision of the standard security
                handler shall be used to interpret this dictionary
            password: The user password
            u_value: A 32-byte string, based on the user password, that shall be
                used in determining whether to prompt the user for a password
                and, if so, whether a valid user or owner password was entered.
            ue_value:

        Returns:
            bytes
        """
        pass

    @staticmethod
    def verify_perms(key: bytes, perms: bytes, p: int, metadata_encrypted: bool) -> bool:
        """
        See :func:`verify_owner_password` and :func:`compute_perms_value`.

        Args:
            key: The owner password
            perms:
            p: A set of flags specifying which operations shall be permitted
                when the document is opened with user access.
                If bit 2 is set to 1, all other bits are ignored and all
                operations are permitted.
                If bit 2 is set to 0, permission for operations are based on
                the values of the remaining flags defined in Table 24.
            metadata_encrypted:

        Returns:
            A boolean
        """
        pass

    @staticmethod
    def compute_U_value(R: int, password: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """
        Algorithm 3.8 Computing the encryption dictionary’s U (user password)
        and UE (user encryption key) values.

        1. Generate 16 random bytes of data using a strong random number generator.
           The first 8 bytes are the User Validation Salt. The second 8 bytes
           are the User Key Salt. Compute the 32-byte SHA-256 hash of the
           password concatenated with the User Validation Salt. The 48-byte
           string consisting of the 32-byte hash followed by the User
           Validation Salt followed by the User Key Salt is stored as the U key.
        2. Compute the 32-byte SHA-256 hash of the password concatenated with
           the User Key Salt. Using this hash as the key, encrypt the file
           encryption key using AES-256 in CBC mode with no padding and an
           initialization vector of zero. The resulting 32-byte string is stored
           as the UE key.

        Args:
            R:
            password:
            key:

        Returns:
            A tuple (u-value, ue value)
        """
        pass

    @staticmethod
    def compute_O_value(R: int, password: bytes, key: bytes, u_value: bytes) -> Tuple[bytes, bytes]:
        """
        Algorithm 3.9 Computing the encryption dictionary’s O (owner password)
        and OE (owner encryption key) values.

        1. Generate 16 random bytes of data using a strong random number
           generator. The first 8 bytes are the Owner Validation Salt. The
           second 8 bytes are the Owner Key Salt. Compute the 32-byte SHA-256
           hash of the password concatenated with the Owner Validation Salt and
           then concatenated with the 48-byte U string as generated in
           Algorithm 3.8. The 48-byte string consisting of the 32-byte hash
           followed by the Owner Validation Salt followed by the Owner Key Salt
           is stored as the O key.
        2. Compute the 32-byte SHA-256 hash of the password concatenated with
           the Owner Key Salt and then concatenated with the 48-byte U string as
           generated in Algorithm 3.8. Using this hash as the key,
           encrypt the file encryption key using AES-256 in CBC mode with
           no padding and an initialization vector of zero.
           The resulting 32-byte string is stored as the OE key.

        Args:
            R:
            password:
            key:
            u_value: A 32-byte string, based on the user password, that shall be
                used in determining whether to prompt the user for a password
                and, if so, whether a valid user or owner password was entered.

        Returns:
            A tuple (O value, OE value)
        """
        pass

    @staticmethod
    def compute_Perms_value(key: bytes, p: int, metadata_encrypted: bool) -> bytes:
        """
        Algorithm 3.10 Computing the encryption dictionary’s Perms
        (permissions) value.

        1. Extend the permissions (contents of the P integer) to 64 bits by
           setting the upper 32 bits to all 1’s.
           (This allows for future extension without changing the format.)
        2. Record the 8 bytes of permission in the bytes 0-7 of the block,
           low order byte first.
        3. Set byte 8 to the ASCII value ' T ' or ' F ' according to the
           EncryptMetadata Boolean.
        4. Set bytes 9-11 to the ASCII characters ' a ', ' d ', ' b '.
        5. Set bytes 12-15 to 4 bytes of random data, which will be ignored.
        6. Encrypt the 16-byte block using AES-256 in ECB mode with an
           initialization vector of zero, using the file encryption key as the
           key. The result (16 bytes) is stored as the Perms string, and checked
           for validity when the file is opened.

        Args:
            key:
            p: A set of flags specifying which operations shall be permitted
                when the document is opened with user access. If bit 2 is set to 1,
                all other bits are ignored and all operations are permitted.
                If bit 2 is set to 0, permission for operations are based on the
                values of the remaining flags defined in Table 24.
            metadata_encrypted: A boolean indicating if the metadata is encrypted.

        Returns:
            The perms value
        """
        pass

class PasswordType(IntEnum):
    NOT_DECRYPTED = 0
    USER_PASSWORD = 1
    OWNER_PASSWORD = 2

class EncryptAlgorithm(tuple, Enum):
    RC4_40 = (1, 2, 40)
    RC4_128 = (2, 3, 128)
    AES_128 = (4, 4, 128)
    AES_256_R5 = (5, 5, 256)
    AES_256 = (5, 6, 256)

class EncryptionValues:
    O: bytes
    U: bytes
    OE: bytes
    UE: bytes
    Perms: bytes

class Encryption:
    """
    Collects and manages parameters for PDF document encryption and decryption.

    Args:
        V: A code specifying the algorithm to be used in encrypting and
           decrypting the document.
        R: The revision of the standard security handler.
        Length: The length of the encryption key in bits.
        P: A set of flags specifying which operations shall be permitted
           when the document is opened with user access
        entry: The encryption dictionary object.
        EncryptMetadata: Whether to encrypt metadata in the document.
        first_id_entry: The first 16 bytes of the file's original ID.
        StmF: The name of the crypt filter that shall be used by default
              when decrypting streams.
        StrF: The name of the crypt filter that shall be used when decrypting
              all strings in the document.
        EFF: The name of the crypt filter that shall be used when
             encrypting embedded file streams that do not have their own
             crypt filter specifier.
        values: Additional encryption parameters.
    """

    def __init__(self, V: int, R: int, Length: int, P: int, entry: DictionaryObject, EncryptMetadata: bool, first_id_entry: bytes, StmF: str, StrF: str, EFF: str, values: Optional[EncryptionValues]) -> None:
        self.V = V
        self.R = R
        self.Length = Length
        self.P = (P + 4294967296) % 4294967296
        self.EncryptMetadata = EncryptMetadata
        self.id1_entry = first_id_entry
        self.StmF = StmF
        self.StrF = StrF
        self.EFF = EFF
        self.values: EncryptionValues = values if values else EncryptionValues()
        self._password_type = PasswordType.NOT_DECRYPTED
        self._key: Optional[bytes] = None

    def _make_crypt_filter(self, idnum: int, generation: int) -> CryptFilter:
        """
        Algorithm 1: Encryption of data using the RC4 or AES algorithms.

        a) Obtain the object number and generation number from the object
           identifier of the string or stream to be encrypted
           (see 7.3.10, "Indirect Objects"). If the string is a direct object,
           use the identifier of the indirect object containing it.
        b) For all strings and streams without crypt filter specifier; treating
           the object number and generation number as binary integers, extend
           the original n-byte encryption key to n + 5 bytes by appending the
           low-order 3 bytes of the object number and the low-order 2 bytes of
           the generation number in that order, low-order byte first.
           (n is 5 unless the value of V in the encryption dictionary is greater
           than 1, in which case n is the value of Length divided by 8.)
           If using the AES algorithm, extend the encryption key an additional
           4 bytes by adding the value “sAlT”, which corresponds to the
           hexadecimal values 0x73, 0x41, 0x6C, 0x54. (This addition is done for
           backward compatibility and is not intended to provide additional
           security.)
        c) Initialize the MD5 hash function and pass the result of step (b) as
           input to this function.
        d) Use the first (n + 5) bytes, up to a maximum of 16, of the output
           from the MD5 hash as the key for the RC4 or AES symmetric key
           algorithms, along with the string or stream data to be encrypted.
           If using the AES algorithm, the Cipher Block Chaining (CBC) mode,
           which requires an initialization vector, is used. The block size
           parameter is set to 16 bytes, and the initialization vector is a
           16-byte random number that is stored as the first 16 bytes of the
           encrypted stream or string.

        Algorithm 3.1a Encryption of data using the AES algorithm
        1. Use the 32-byte file encryption key for the AES-256 symmetric key
           algorithm, along with the string or stream data to be encrypted.
           Use the AES algorithm in Cipher Block Chaining (CBC) mode, which
           requires an initialization vector. The block size parameter is set to
           16 bytes, and the initialization vector is a 16-byte random number
           that is stored as the first 16 bytes of the encrypted stream or string.
           The output is the encrypted data to be stored in the PDF file.
        """
        pass
