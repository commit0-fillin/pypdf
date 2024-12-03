from pypdf._crypt_providers._base import CryptBase
from pypdf.errors import DependencyError
_DEPENDENCY_ERROR_STR = 'cryptography>=3.1 is required for AES algorithm'
crypt_provider = ('local_crypt_fallback', '0.0.0')

class CryptRC4(CryptBase):

    def __init__(self, key: bytes) -> None:
        super().__init__()
        self.set_key(key)
        self.s = bytearray(range(256))
        j = 0
        for i in range(256):
            j = (j + self.s[i] + self.key[i % len(self.key)]) % 256
            self.s[i], self.s[j] = (self.s[j], self.s[i])

class CryptAES(CryptBase):

    def __init__(self, key: bytes) -> None:
        pass
