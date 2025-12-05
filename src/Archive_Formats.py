# Archive_Formats.py
"""
OTIK archive formats module
Формат заголовка и расположение секций

Структура:
0..15    Signature (16 bytes)         ASCII "OTIK" + zeros
16..19   Version (uint32)
20..23   Flags (uint32)
24..31   ArchiveSize (uint64)
32..35   DataCrc32 (uint32)           CRC32 по секции данных (Data section)
36..39   HeaderCrc32 (uint32)         CRC32 по заголовку (при вычислении - поле должно быть нулевым)
40       BytesOrder (uint8)           0 -> LE, !=0 -> BE
41       Align (uint8)                выравнивание (байт)
42..45   FileCount (uint32)
46..53   DataSectionOffset (uint64)
54..61   IndexSectionOffset (uint64)  (если нет - нули)
62..95   Reserved (34 bytes -> до 96 байт заголовка)
96..351  CodeTable (256 bytes)
352..    DataTable (variable)         таблица ссылок на файлы (заглушка)
...      DataSection (variable)
...      IndexSection (variable)

File header (DataTable) формат:
0    4   uint32  local file header signature (0x04034b50)
4    4   uint32  crc-32 по блоку данных (compressed bytes)
8    4   uint32  OriginalSize
12   4   uint32  CompressedSize
16   8   uint64  DataOffset (от начала архива) — 0, если нет содержимого
24   1   uint8   Flags
25   1           Align (padding)
26   2   uint16  file name length (в байтах, обязательно кратно 8 бит)
28   N   bytes   Name (utf-8)
-- далее запись выравнивается до следующего 8-байтного смещения перед следующим File header --

Примечания:
- Для файлов с CompressedSize == 0 DataOffset устанавливается в 0, и данных в DataSection нет.
- HeaderCrc32 считается по (header 96 bytes + code_table 256 bytes) при обнулённом поле HeaderCrc32.
"""
# =================================================================================================================

from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass
from typing import Optional

# =================================================================================================================

# Archive header constants
SIGNATURE_SIZE          = 16
SIGNATURE               = b"DBP-OTIK-HFHM" + b"\x00" * 3
VERSION                 = 1
HEADER_SIZE             = 96
CODE_TABLE_SIZE         = 256

# Offsets (for clarity)
_OFF_SIGNATURE          = 0
_OFF_VERSION            = 16
_OFF_FLAGS              = 20
_OFF_ARCHIVESIZE        = 24
_OFF_DATACRC32          = 32
_OFF_HEADERCRC32        = 36
_OFF_BYTESORDER         = 40 # uint8
_OFF_ALIGN              = 41 # uint8
_OFF_FILECOUNT          = 42 # uint32
_OFF_DATASECT_OFFSET    = 46 # uint64
_OFF_INDEXSECT_OFFSET   = 54 # uint64
_OFF_RESERVED           = 62 # up to 96
_OFF_CODETABLE          = 96
_OFF_DATATABLE          = _OFF_CODETABLE + CODE_TABLE_SIZE  # 352

# File header constants
FILE_HEADER_SIGNATURE = 0x04034b50
FILE_HEADER_FIXED_SIZE = 30  # bytes before Name
# Each file header starts at current offset; after Name, next header starts at next 8-byte aligned offset.
 
# =================================================================================================================

# Helpers for endian prefix
def _endian_prefix(bytes_order_flag: int) -> str:
    return "<" if bytes_order_flag == 0 else ">"

def _unpack(format, blob, offset):
    return struct.unpack_from(format, blob, offset)[0]

def _pack(format, blob, offset, data):
    struct.pack_into(format, blob, offset, data)
 
# =================================================================================================================

@dataclass
class ArchiveHeader:
    version: int = VERSION
    flags: int = 0
    archive_size: int = 0
    data_crc32: int = 0
    header_crc32: int = 0
    bytes_order: int = 0  # 0 -> LE, else BE
    align: int = 0xFF
    file_count: int = 0
    data_section_offset: int = 0
    index_section_offset: int = 0
    reserved: bytes = b"\x00" * (HEADER_SIZE - 62)  # from offset 62..95 (inclusive)
    code_table: bytes = b"\x00" * CODE_TABLE_SIZE     # 256 bytes

    def to_bytes(self) -> bytes:
        """Сериализует заголовок в bytes длиной HEADER_SIZE + CODE_TABLE_SIZE (352 байта)"""
        prefix = _endian_prefix(self.bytes_order)
        # Build header 0..95
        buf = bytearray(HEADER_SIZE)

        # Signature (0..15)
        buf[_OFF_SIGNATURE:_OFF_SIGNATURE + SIGNATURE_SIZE] = SIGNATURE

        # version uint32 at 16
        _pack(f"{prefix}I", buf, _OFF_VERSION, self.version)
        # flags uint32 at 20
        _pack(f"{prefix}I", buf, _OFF_FLAGS, self.flags)
        # archive_size uint64 at 24
        _pack(f"{prefix}Q", buf, _OFF_ARCHIVESIZE, self.archive_size)
        # data_crc32 uint32 at 32
        _pack(f"{prefix}I", buf, _OFF_DATACRC32, self.data_crc32)
        # header_crc32 uint32 at 36 (we'll set to current value; typically 0 until computed)
        _pack(f"{prefix}I", buf, _OFF_HEADERCRC32, self.header_crc32)
        # bytes_order uint8 at 40
        _pack("B", buf, _OFF_BYTESORDER, self.bytes_order & 0xFF)
        # align uint8 at 41
        _pack("B", buf, _OFF_ALIGN, self.align & 0xFF) 
        # file_count uint32 at 42
        _pack(f"{prefix}I", buf, _OFF_FILECOUNT, self.file_count)
        # data_section_offset uint64 at 46
        _pack(f"{prefix}Q", buf, _OFF_DATASECT_OFFSET, self.data_section_offset)
        # index_section_offset uint64 at 54
        _pack(f"{prefix}Q", buf, _OFF_INDEXSECT_OFFSET, self.index_section_offset)
        
        # reserved (62..95) - copy up to len(reserved)
        buf[_OFF_RESERVED:_OFF_CODETABLE] = self.reserved
        
        # header done (96 bytes)
        # append code table (256 bytes)
        if len(self.code_table) != CODE_TABLE_SIZE:
            raise ValueError(f"Code table must be exactly {CODE_TABLE_SIZE} bytes")
        
        return bytes(buf) + self.code_table

    @classmethod
    def from_bytes(cls, data: bytes) -> "ArchiveHeader":
        """Парсит первые 352 байта (header + code_table) и возвращает ArchiveHeader."""
        if len(data) < HEADER_SIZE + CODE_TABLE_SIZE:
            raise ValueError("Not enough bytes to parse header+code_table")
        
        header_bytes = data[:HEADER_SIZE]
        code_table = data[HEADER_SIZE:HEADER_SIZE+CODE_TABLE_SIZE]
        
        # first read bytes_order to determine endianness (offset 40)
        bytes_order             = header_bytes[_OFF_BYTESORDER]
        prefix                  = _endian_prefix(bytes_order)
        version                 = _unpack(f"{prefix}I", header_bytes, _OFF_VERSION)
        flags                   = _unpack(f"{prefix}I", header_bytes, _OFF_FLAGS)
        archive_size            = _unpack(f"{prefix}Q", header_bytes, _OFF_ARCHIVESIZE)
        data_crc32              = _unpack(f"{prefix}I", header_bytes, _OFF_DATACRC32)
        header_crc32            = _unpack(f"{prefix}I", header_bytes, _OFF_HEADERCRC32)
        align                   = header_bytes[_OFF_ALIGN]
        file_count              = _unpack(f"{prefix}I", header_bytes, _OFF_FILECOUNT)
        data_section_offset     = _unpack(f"{prefix}Q", header_bytes, _OFF_DATASECT_OFFSET)
        index_section_offset    = _unpack(f"{prefix}Q", header_bytes, _OFF_INDEXSECT_OFFSET)
        reserved                = header_bytes[_OFF_RESERVED:HEADER_SIZE]
        
        return cls(
            version=version,
            flags=flags,
            archive_size=archive_size,
            data_crc32=data_crc32,
            header_crc32=header_crc32,
            bytes_order=bytes_order,
            align=align,
            file_count=file_count,
            data_section_offset=data_section_offset,
            index_section_offset=index_section_offset,
            reserved=reserved,
            code_table=code_table
        )

    def compute_header_crc32(self) -> int:
        """Вычисляет CRC32 по заголовку (поля HeaderCrc32 = 0 при вычислении)."""
        b = bytearray(self.to_bytes())
        # Zero the HeaderCrc32 field (offset 36..39)
        # Note: ensure we zero the bytes that represent header_crc32
        b[_OFF_HEADERCRC32:_OFF_HEADERCRC32 + 4] = b"\x00\x00\x00\x00"
        crc = zlib.crc32(bytes(b[:HEADER_SIZE+CODE_TABLE_SIZE])) & 0xFFFFFFFF
        return crc

    def validate_crc32(self) -> bool:
        # verify header CRC
        stored = self.header_crc32
        computed = self.compute_header_crc32()
        if stored != computed:
            raise ValueError(f"Header CRC mismatch: stored={stored:#010x}, computed={computed:#010x}")
        return True

# =================================================================================================================

@dataclass
class HeaderFile:
    crc32: int
    original_size: int
    compressed_size: int
    data_offset: int  # 0 if no data
    flags: int
    control_bits: int  # 0 if no Hamming code
    padding_Huff: int
    padding_Hamm: int
    name: str
    lengths_codes: bytes = b"\x00" * CODE_TABLE_SIZE     # 256 bytes
    
    def to_bytes(self, prefix: str) -> bytes:
        """
        Собирает локальный заголовок.
        Возвращает bytes, готовые к вставке в DataTable.
        """
        name_b = self.name.encode("utf-8")
        name_len = len(name_b)
        if name_len > 0xFFFF:
            raise ValueError("file name too long for uint16")

        # fixed layout size 30
        blob = bytearray(FILE_HEADER_FIXED_SIZE)
        # signature
        _pack(f"{prefix}I", blob, 0, FILE_HEADER_SIGNATURE)
        # crc32
        _pack(f"{prefix}I", blob, 4, int(self.crc32) & 0xFFFFFFFF)
        # original_size
        _pack(f"{prefix}I", blob, 8, int(self.original_size) & 0xFFFFFFFF)
        # compressed_size
        _pack(f"{prefix}I", blob, 12, int(self.compressed_size) & 0xFFFFFFFF)
        # data_offset (uint64)
        _pack(f"{prefix}Q", blob, 16, int(self.data_offset) & 0xFFFFFFFFFFFFFFFF)
        # flags (uint8)
        _pack("B", blob, 24, int(self.flags) & 0xFF)
        # control_bits (uint8)
        _pack("B", blob, 25, int(self.control_bits) & 0xFF)
        # padding_Huff (uint8)
        _pack("B", blob, 26, int(self.padding_Huff) & 0xFF)
        # padding_Hamm (uint8)
        _pack("B", blob, 27, int(self.padding_Hamm) & 0xFF)
        # name_len (uint16) at offset 28
        _pack(f"{prefix}H", blob, 28, name_len)

        return bytes(blob) + name_b
    
    @classmethod
    def from_bytes(cls, data: bytes, name_b:bytes, prefix: str) -> "HeaderFile":
        if len(data) < FILE_HEADER_FIXED_SIZE:
            raise EOFError("Unexpected EOF while reading file header")
            
        sig = _unpack(f"{prefix}I", data, 0)
        if sig != FILE_HEADER_SIGNATURE:
            raise ValueError(f"Invalid file header signature at entry: {sig:#010x}")
            
        return cls(
            crc32           = _unpack(f"{prefix}I", data, 4),
            original_size   = _unpack(f"{prefix}I", data, 8),
            compressed_size = _unpack(f"{prefix}I", data, 12),
            data_offset     = _unpack(f"{prefix}Q", data, 16),
            flags           = data[24],
            control_bits    = data[25],
            padding_Huff    = data[26],
            padding_Hamm    = data[27],
            name            = name_b.decode("utf-8")
        )
    
    def compute_header_crc32(self, prefix:str) -> int:
        """
        Вычисляет CRC32 по bytes заголовка (fixed + name).
        Это вспомогательная функция — не путать с CRC по самим данным файла.
        Возвращает 32-bit unsigned CRC.
        """
        blob = self.to_bytes(prefix)
        # compute CRC32 over the header blob (fixed + name), not over the file data
        return zlib.crc32(blob) & 0xFFFFFFFF
    
    def validate_crc32(self, compressed_bytes: Optional[bytes] = None) -> bool:
        """
        Проверяет поле crc32 в заголовке с переданными compressed_bytes.
        Если compressed_bytes is None — ничего не делает и возвращает True.
        Иначе — сравнивает stored crc32 с zlib.crc32(compressed_bytes).
        """
        if compressed_bytes is None:
            return True
        
        computed = zlib.crc32(compressed_bytes) & 0xFFFFFFFF
        return (computed == (self.crc32 & 0xFFFFFFFF))
 
# =================================================================================================================
