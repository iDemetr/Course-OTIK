# Archive_Formats.py
"""
OTIK archive formats module
Формат заголовка и расположение секций

Структура:
0..15    Signature (16 bytes)         ASCII "OTIK" + zeros
96..351  CodeTable (256 bytes)
352..    DataTable (variable)         таблица ссылок на файлы
...      DataSection (variable)
...      IndexSection (variable)

Примечания:
- Для файлов с OriginalSize == 0 DataOffset устанавливается в 0, и данных в DataSection нет.
- HeaderCrc32 считается по (header 96 bytes + code_table 256 bytes) при обнулённом поле HeaderCrc32.
"""
# =================================================================================================================

from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass
from typing import Optional

# =================================================================================================================

# lims
MAX_FILES               = 10000
MAX_PADDING             = 7
MAX_CONTROL_BITS        = 10
MAX_FILE_NAME_LEN       = 0x111
MAX_FILE_SIZE           = 2 << 30   # file size lim 4GB

# =================================================================================================

# Archive header constants
H_SIGNATURE_SIZE        = 16
H_SIGNATURE             = b"DBP-OTIK-HFHM" + b"\x00" * 3
VERSION                 = 5
HEADER_SIZE             = 96
CODE_TABLE_SIZE         = 256
META_SIZE               = HEADER_SIZE + CODE_TABLE_SIZE
OFF_CODETABLE           = HEADER_SIZE
OFF_DATATABLE           = OFF_CODETABLE + CODE_TABLE_SIZE  # 352

# Offsets
H_OFF_SIGNATURE         = 0 # char[16]
H_OFF_VERSION           = 16 # uint16
H_OFF_FLAGS             = 18 # uint32
H_OFF_ARCHIVESIZE       = 22 # uint64
H_OFF_DATACRC32         = 30 # uint32
H_OFF_HEADERCRC32       = 34 # uint32
H_OFF_BYTESORDER        = 38 # uint8
H_OFF_ALIGN             = 39 # uint8
H_OFF_FILECOUNT         = 40 # uint32
H_OFF_DATASECT_OFFSET   = 44 # uint64
H_OFF_INDEXSECT_OFFSET  = 52 # uint64
H_OFF_RESERVED          = 60 # up to 96

# =================================================================================================

# File header constants
FH_SIGNATURE_SIZE       = 4
FH_SIGNATURE            = b"DPFH"
FH_FIXED_SIZE           = 30  # bytes before Name
# Each file header starts at current offset; after Name, next header starts at next 8-byte aligned offset.

# Offsets
FH_OFF_SIGNATURE        = 0 # char[4]
FH_OFF_HEADERCRC32      = 4 # uint32
#FH_OFF_DATACRC32        = 8 # uint32
FH_OFF_ORIGINAL_SIZE    = 8 # uint32
FH_OFF_COMPRESSED_SIZE  = 12 # uint32
FH_OFF_DATA_OFFSET      = 16 # uint64
FH_OFF_FLAGS            = 24 # uint8
FH_OFF_CONTROL_BITS     = 25 # uint8
FH_OFF_PADDING_HUFF     = 26 # uint8
FH_OFF_PADDING_HAMM     = 27 # uint8
FH_OFF_NAME_LEN         = 28 # uint16
 
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
    version: int                = VERSION
    flags: int                  = 0
    archive_size: int           = 0
    data_crc32: int             = 0
    header_crc32: int           = 0
    bytes_order: int            = 0  # 0 -> LE, else BE
    align: int                  = 0xFF
    file_count: int             = 0
    data_section_offset: int    = 0
    index_section_offset: int   = 0
    reserved: bytes             = b"\x00" * (HEADER_SIZE - H_OFF_RESERVED)  # from offset 60..95 (inclusive)
    code_table: bytes           = b"\x00" * CODE_TABLE_SIZE     # 256 bytes

    def to_bytes(self) -> bytes:
        """Сериализует заголовок в bytes длиной HEADER_SIZE + CODE_TABLE_SIZE (352 байта)"""
        
        self.validate_header(RuntimeError)
        
        if len(self.code_table) != CODE_TABLE_SIZE:
            raise ValueError(f"Code table must be exactly {CODE_TABLE_SIZE} bytes")
        
        # Build header 0..95
        buf = bytearray(HEADER_SIZE)
        # Signature (0..15)
        buf[H_OFF_SIGNATURE:H_OFF_SIGNATURE + H_SIGNATURE_SIZE] = H_SIGNATURE

        prefix = _endian_prefix(self.bytes_order)
        
        # version uint32 at 16
        _pack(f"{prefix}I", buf, H_OFF_VERSION, self.version)
        # flags uint32 at 20
        _pack(f"{prefix}I", buf, H_OFF_FLAGS, self.flags)
        # archive_size uint64 at 24
        _pack(f"{prefix}Q", buf, H_OFF_ARCHIVESIZE, self.archive_size)
        # data_crc32 uint32 at 32
        _pack(f"{prefix}I", buf, H_OFF_DATACRC32, self.data_crc32)
        # header_crc32 uint32 at 36 (we'll set to current value; typically 0 until computed)
        _pack(f"{prefix}I", buf, H_OFF_HEADERCRC32, self.header_crc32)
        # bytes_order uint8 at 40
        _pack("B", buf, H_OFF_BYTESORDER, self.bytes_order & 0xFF)
        # align uint8 at 41
        _pack("B", buf, H_OFF_ALIGN, self.align & 0xFF) 
        # file_count uint32 at 42
        _pack(f"{prefix}I", buf, H_OFF_FILECOUNT, self.file_count)
        # data_section_offset uint64 at 46
        _pack(f"{prefix}Q", buf, H_OFF_DATASECT_OFFSET, self.data_section_offset)
        # index_section_offset uint64 at 54
        _pack(f"{prefix}Q", buf, H_OFF_INDEXSECT_OFFSET, self.index_section_offset)
        
        # reserved (62..95) - copy up to len(reserved)
        buf[H_OFF_RESERVED:OFF_CODETABLE] = self.reserved
        
        # header done (96 bytes)
        # append code table (256 bytes)
        return bytes(buf) + self.code_table

    @classmethod
    def from_bytes(cls, data: bytes) -> "ArchiveHeader":
        """Парсит первые 352 байта (header + code_table) и возвращает ArchiveHeader."""

        if len(data) < META_SIZE:
            raise ValueError(f"File too small to be valid {H_SIGNATURE} archive")
            
        header = data[:HEADER_SIZE]
        code_table = data[HEADER_SIZE:HEADER_SIZE+CODE_TABLE_SIZE]
        
        # first read bytes_order to determine endianness
        bytes_order             = header[H_OFF_BYTESORDER]
        prefix                  = _endian_prefix(bytes_order)
        
        H = cls(
            version                 = _unpack(f"{prefix}I", header, H_OFF_VERSION),
            flags                   = _unpack(f"{prefix}I", header, H_OFF_FLAGS),
            archive_size            = _unpack(f"{prefix}Q", header, H_OFF_ARCHIVESIZE),
            data_crc32              = _unpack(f"{prefix}I", header, H_OFF_DATACRC32),
            header_crc32            = _unpack(f"{prefix}I", header, H_OFF_HEADERCRC32),
            bytes_order             = bytes_order,
            #align                   = header_bytes[H_OFF_ALIGN],
            file_count              = _unpack(f"{prefix}I", header, H_OFF_FILECOUNT),
            data_section_offset     = _unpack(f"{prefix}Q", header, H_OFF_DATASECT_OFFSET),
            index_section_offset    = _unpack(f"{prefix}Q", header, H_OFF_INDEXSECT_OFFSET),
            reserved                = header[H_OFF_RESERVED:HEADER_SIZE],
            code_table              = code_table
        )
        H.validate_header(ImportError)                

        return H

    def validate_header(self, type):            
        if int(self.data_crc32) < 1:                        # int(self.header_crc32) < 1 or
            raise type("Ошибка чтения CRC32 архива")
        
        if self.data_section_offset < META_SIZE:
            raise type("Ошибка ссылки на секцию файлов")
        
        if self.version != VERSION:
            raise type("Неподдерживаемая версия")
        
        if self.file_count > MAX_FILES:
            raise type(f"Превышен лимит максимального кол-ва файлов в архиве. Максимум: {MAX_FILES}")
        
        if self.index_section_offset != 0 and self.index_section_offset < self.data_section_offset:
            raise type("Неправильная ссылка на индексную таблицу")
        
        if self.reserved != b"\x00" * (HEADER_SIZE - H_OFF_RESERVED):
            raise ImportWarning("Обнаружен мусор в зарезервированной зоне")
        
        if len(self.code_table) < CODE_TABLE_SIZE:
            raise type("Неправильный размер кодовой таблицы")
        
        # Потенциально наибольший размер файла - сумма мета данных, репозитория и секции данных
        max_size = META_SIZE + self.file_count * (MAX_FILE_NAME_LEN+FH_FIXED_SIZE) + self.file_count * MAX_FILE_SIZE 
        
        if self.archive_size < META_SIZE or self.archive_size > max_size:
            raise type
    
    def compute_header_crc32(self) -> int:
        """Вычисляет CRC32 по заголовку (поля HeaderCrc32 = 0 при вычислении)."""
        b = bytearray(self.to_bytes())
        # Zero the HeaderCrc32 field (offset 36..39)
        # Note: ensure we zero the bytes that represent header_crc32
        b[H_OFF_HEADERCRC32:H_OFF_HEADERCRC32 + 4] = b"\x00\x00\x00\x00"
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
    crc32: int                  = 0
    #data_crc32: int             = 0
    original_size: int          = 0
    compressed_size: int        = 0
    data_offset: int            = 0 # 0 if no data
    flags: int                  = 0
    control_bits: int           = 0 # 0 if no Hamming code
    padding_Huff: int           = 0
    padding_Hamm: int           = 0
    name: str                   = ""
    lengths_codes: bytes        = b"\x00" * CODE_TABLE_SIZE     # 256 bytes
    #----------------------
    total_padd : int            = 0 # Вспомогательная переменная при записи
    
    def to_bytes(self, prefix: str) -> bytes:
        """
        Собирает локальный заголовок.
        Возвращает bytes, готовые к вставке в DataTable.
        """
        
        self.validate_header(RuntimeError)
        
        name_b = self.name.encode("utf-8")
        name_len = len(name_b)
        
        # fixed layout size 30
        blob = bytearray(FH_FIXED_SIZE)
        # Signature (0..4)
        blob[FH_OFF_SIGNATURE:FH_OFF_SIGNATURE + FH_SIGNATURE_SIZE] = FH_SIGNATURE
        
        # header_crc32
        _pack(f"{prefix}I", blob, FH_OFF_HEADERCRC32, self.crc32)
        # data_crc32
        #_pack(f"{prefix}I", blob, FH_OFF_DATACRC32, self.data_crc32)
        # original_size
        _pack(f"{prefix}I", blob, FH_OFF_ORIGINAL_SIZE, self.original_size)
        # compressed_size
        _pack(f"{prefix}I", blob, FH_OFF_COMPRESSED_SIZE, self.compressed_size)
        # data_offset (uint64)
        _pack(f"{prefix}Q", blob, FH_OFF_DATA_OFFSET, self.data_offset)
        # flags (uint8)
        _pack("B", blob, FH_OFF_FLAGS, self.flags & 0xFF)
        # control_bits (uint8)
        _pack("B", blob, FH_OFF_CONTROL_BITS, self.control_bits & 0xFF)
        # padding_Huff (uint8)
        _pack("B", blob, FH_OFF_PADDING_HUFF, self.padding_Huff & 0xFF)
        # padding_Hamm (uint8)
        _pack("B", blob, FH_OFF_PADDING_HAMM, self.padding_Hamm & 0xFF)
        # name_len (uint16) at offset 28
        _pack(f"{prefix}H", blob, FH_OFF_NAME_LEN, name_len)

        return bytes(blob) + name_b
    
    @classmethod
    def from_bytes(cls, data: bytes, name_b:bytes, prefix: str) -> "HeaderFile":
        
        if len(data) < FH_FIXED_SIZE:
            raise EOFError("Unexpected EOF while reading file header")
            
        if data[FH_OFF_SIGNATURE:FH_SIGNATURE_SIZE] != FH_SIGNATURE:
            raise ValueError("Invalid file header signature at entry")
                
        H = cls(
            crc32           = _unpack(f"{prefix}I", data, FH_OFF_HEADERCRC32),
            #data_crc32      = _unpack(f"{prefix}I", data, FH_OFF_DATACRC32),
            original_size   = _unpack(f"{prefix}I", data, FH_OFF_ORIGINAL_SIZE),
            compressed_size = _unpack(f"{prefix}I", data, FH_OFF_COMPRESSED_SIZE),
            data_offset     = _unpack(f"{prefix}Q", data, FH_OFF_DATA_OFFSET),
            flags           = data[FH_OFF_FLAGS],
            control_bits    = data[FH_OFF_CONTROL_BITS],
            padding_Huff    = data[FH_OFF_PADDING_HUFF],
            padding_Hamm    = data[FH_OFF_PADDING_HAMM],
            name            = name_b.decode("utf-8")
        )
                
        H.validate_header(ImportError)
        
        return H
    
    def validate_header(self, type):            
        
        name_b = self.name.encode("utf-8")
        name_len = len(name_b)
        if name_len > MAX_FILE_NAME_LEN:
            raise ValueError("file name too long for uint16")
        
        if self.data_offset < META_SIZE:
            raise type("Ошибка ссылки на секцию данных")
        
        if self.compressed_size != 0 and self.original_size != 0:
            compression_ratio = self.original_size / self.compressed_size
            if 1000 > compression_ratio < 0:
                raise type("Zip bomb: коэффициента сжатия недопустимо большой")
        
        if self.compressed_size > MAX_FILE_SIZE or self.original_size > MAX_FILE_SIZE and self.compressed_size == 0:
            raise type("Превышен максимально допустимый размер файла архива")
        
        if self.control_bits > MAX_CONTROL_BITS:
            raise type(f"Превышено максимальное количество контрольных бит для Хэмминга: {MAX_CONTROL_BITS}")
        
        if self.padding_Huff > MAX_PADDING or self.padding_Hamm > MAX_PADDING:
            raise type(f"Превышен максимальный padding блоков данных: {MAX_PADDING}")
    
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
        
        computed = zlib.crc32(compressed_bytes)
        return (computed & 0xFFFFFFFF == self.crc32 & 0xFFFFFFFF)
    
    def get_size(self):
        name_b = self.name.encode("utf-8")
        return FH_FIXED_SIZE +  len(name_b)
    
# =================================================================================================================
