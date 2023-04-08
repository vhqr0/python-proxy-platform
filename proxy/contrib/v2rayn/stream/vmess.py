import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from proxy.common import override
from proxy.stream import Stream


class VmessCounteredAESGCM:
    aesgcm: AESGCM
    iv: bytes
    count: int

    def __init__(self, key: bytes, iv: bytes, count: int = 0):
        self.aesgcm = AESGCM(key)
        self.iv = iv
        self.count = count

    def encrypt(self, buf: bytes) -> bytes:
        iv = struct.pack('!H', self.count) + self.iv
        buf = self.aesgcm.encrypt(iv, buf, b'')
        self.count = (self.count + 1) & 0xffff
        return buf

    def decrypt(self, buf: bytes) -> bytes:
        iv = struct.pack('!H', self.count) + self.iv
        buf = self.aesgcm.decrypt(iv, buf, b'')
        self.count = (self.count + 1) & 0xffff
        return buf


class VmessStream(Stream):
    write_encryptor: VmessCounteredAESGCM
    read_decryptor: VmessCounteredAESGCM

    def __init__(self, write_encryptor: VmessCounteredAESGCM,
                 read_decryptor: VmessCounteredAESGCM, **kwargs):
        super().__init__(**kwargs)
        self.write_encryptor = write_encryptor
        self.read_decryptor = read_decryptor

    @override(Stream)
    def write_primitive(self, buf: bytes):
        assert self.next_layer is not None
        buf = self.write_encryptor.encrypt(buf)
        buf = struct.pack('!H', len(buf)) + buf
        self.next_layer.write(buf)

    @override(Stream)
    async def read_primitive(self) -> bytes:
        assert self.next_layer is not None
        buf = await self.next_layer.peek()
        if len(buf) == 0:
            return b''
        buf = await self.next_layer.readexactly(2)
        blen, = struct.unpack('!H', buf)
        buf = await self.next_layer.readexactly(blen)
        buf = self.read_decryptor.decrypt(buf)
        return buf
