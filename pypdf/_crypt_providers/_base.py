class CryptBase:
    def __init__(self):
        self.key = None

    def encrypt(self, data):
        raise NotImplementedError("Subclasses must implement the encrypt method")

    def decrypt(self, data):
        raise NotImplementedError("Subclasses must implement the decrypt method")

    def set_key(self, key):
        self.key = key

class CryptIdentity(CryptBase):
    def __init__(self):
        super().__init__()

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data
