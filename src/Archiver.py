# Archiver.py

# =================================================================================================================

from __future__ import annotations
import os
import tempfile
import zlib
from typing import BinaryIO, List, Tuple, Iterator

from Archive_Formats import *

import Archive_Formats as otik

# =================================================================================================================

_MAX_FILES = 1000

# =================================================================================================================

def _align_up(value: int, align: int) -> int:
    return ((value + align - 1) // align) * align

def _pad_to8(n: int) -> int:
    return _align_up(n, 8)

# =================================================================================================================

class ArchiveWriter:
    """
    ArchiveWriter: записывает архив в файл по твоему формату.
    - entries: список записей вида (name: str, data: bytes, metadata: dict)
    - code_table: 256 bytes (заглушка, будет заменена после получения формата кодовой таблицы Хаффмана)
    """
    def __init__(self, args):
        self.path = args.output
        self._tmp_path = None
        
        self.header = ArchiveHeader(
            bytes_order     = args.bytes_order & 0xFFFFFFFF,
            flags           = args.mode & 0xFFFFFFFF
        )
        self._entries: List[tuple[HeaderFile, bytes]] = []

    # def set_code_table(self, lengths: bytes) -> None:
    #     """Установить canonical code table: 256 bytes (length per symbol)."""
    #     if len(lengths) != CODE_TABLE_SIZE:
    #         raise ValueError("code_table must be 256 bytes")
    #     self.header.code_table = lengths
        
    def add_file(self, name: str, meta_data: dict) -> None:
        """Добавляет файл в архив. compressed_bytes — уже закодированные (сжатые) данные.
           Для отсутствия содержимого передай compressed_bytes=b'' и compressed_size==0.
        """         
        
        if len(self._entries) > 1:
            raise NotImplementedError("Поддержа более 1 файла в архиве не поддерживается!")
                        
        if len(self._entries) > _MAX_FILES:
            raise RuntimeError(f"Превышен лимит максимального кол-ва архивируемых файлов. Максимум: {_MAX_FILES}")
                
        entry = HeaderFile(
            name            = name,
            lengths_codes   = meta_data["lengths_codes"],
            flags           = meta_data["flags"],
            padding_Huff    = meta_data["padding_huff"],
            control_bits    = meta_data["r"],
            padding_Hamm    = meta_data["padding_hamm"],
            original_size   = meta_data["raw_size"],
            compressed_size = meta_data["compressed_size"],
            crc32           = zlib.crc32(bytes(meta_data["data"])) & 0xFFFFFFFF,    
            # -------------------------------------------
            data_offset     = 0
        )
        
        self.header.code_table = meta_data["lengths_codes"]             #TODO: костыль, убрать в шапку файла
        self._entries.append((entry, meta_data["data"]))

    def finalize(self) -> None:
        """
        Собирает Archive Header + DataTable + DataSection и записывает весь архив атомарно.
        """
        
        if self.header is None:
            raise RuntimeError("Header not initialized")
        
        if len(self._entries) > _MAX_FILES:
            raise RuntimeError(f"Превышен лимит максимального кол-ва архивируемых файлов. Максимум: {_MAX_FILES}")
        
        if len(self.header.code_table) != CODE_TABLE_SIZE:
            raise RuntimeError("Кодовая таблица не установлена")
        
        # Build header (initial)
        self.header.file_count = len(self._entries)
        prefix = otik._endian_prefix(self.header.bytes_order)
        
        # =============================== STAGE 1. Вычисление размера таблицы файлов ================================
        
        datatable_size = 0
        for hdr, compressed in self._entries:
            # 8-byte align — смещение к следующей записи
            size = hdr.get_size()
            hdr.total_padd = _pad_to8(size) - size
            datatable_size += size + hdr.total_padd

        # ================================ STAGE 2. Разметка data_offset всех файлов ================================

        # Смещение начала DataSection
        data_section_offset =  otik.OFF_DATATABLE + datatable_size
        self.header.data_section_offset = data_section_offset

        real_data_offsets: list[int] = []

        cur_data_offset = 0
        for hdr, compressed in self._entries:
            if hdr.compressed_size == 0:
                hdr.data_offset = 0
                real_data_offsets.append(0)
                continue

            hdr.data_offset = data_section_offset + cur_data_offset
            real_data_offsets.append(cur_data_offset)            
            cur_data_offset += len(compressed)

        data_section_size = cur_data_offset 

        # ================================= STAGE 3. Cборка DataTable и DataSection =================================

        datatable_bin = bytearray()
        data_section_bin = bytearray()

        for hdr, compressed in self._entries:
            header_bin = hdr.to_bytes(prefix)
            
            datatable_bin.extend(header_bin)
            if hdr.total_padd  > 0:
                datatable_bin.extend(b"\x00" * hdr.total_padd )                
            
            if hdr.compressed_size != 0:
                data_section_bin.extend(compressed)
                
        data_section_bytes = bytes(data_section_bin)
        datatable_bytes = bytes(datatable_bin)

        # ====================== STAGE 4. CRC32 по DataSection и фиксация размера всего архива =======================

        self.header.data_crc32 = zlib.crc32(data_section_bytes) & 0xFFFFFFFF
        self.header.archive_size = otik.OFF_DATATABLE + datatable_size + data_section_size

        # ==================== STAGE 5. Финальная сборка Header с учётом header_crc32 + CodeTable ====================
        
        # Для вычисления header_crc32 поле header_crc32 должно быть 0
        self.header.header_crc32 = 0                    # дубль на всякий случай
        header_blob = self.header.to_bytes()
        # CRC только по header_blob
        self.header.header_crc32 = zlib.crc32(header_blob) & 0xFFFFFFFF

        # Теперь финальное дерево байтов заголовка
        header_blob = self.header.to_bytes()

        # ===================================== STAGE 6. Запись итогового архива =====================================
        
        # Atomic write to disk
        dir_path = os.path.dirname(self.path)           # Обрезка названия файла
        name = os.path.basename(self.path)              # Выделение названия файла
        os.makedirs(dir_path, exist_ok=True)            # Создать директорию, если нет.
        
        fd, tmp = tempfile.mkstemp(dir=dir_path, prefix=name+".tmp_")
        os.close(fd)
        with open(tmp, "wb") as f:
            # Header (96 bytes) with CodeTable (256 bytes)
            f.write(header_blob)
            
            f.write(datatable_bytes)
            
            # DataSection
            f.write(data_section_bytes)
        
        os.replace(tmp, self.path)

class ArchiveReader:
    """
    ArchiveReader: читает заголовок, code_table и позволяет итерировать по записям.
    Реализованы парсинг заголовка и заглушечный парсинг DataTable.
    """
    def __init__(self, path: str):
        self.path = path
        self.header: ArchiveHeader
        self._local_file_headers :List[HeaderFile] = []

    def open(self) -> ArchiveHeader:
        """Открывает файл с архивом
        Выполняет проверку crc32 для заголовка и для архивированных данных
        Вызывает парсер локального репозитория - DataTable 

        Returns:
            ArchiveHeader: возвращает заголовок всего архива
        """        
        with open(self.path, "rb") as f:
            # read header + code_table
            head = f.read(otik.META_SIZE)
            
            if head[:H_SIGNATURE_SIZE] != H_SIGNATURE:
                raise ImportError(f"File signature is differs from the archive")
            if len(head) < otik.META_SIZE:
                raise ImportError(f"File too small to be valid {H_SIGNATURE} archive")
            
            self.header = ArchiveHeader.from_bytes(head)
            # verify header CRC
            self.header.validate_crc32()
        
            if self.header.file_count > _MAX_FILES:
                raise RuntimeError(f"Превышен лимит максимального кол-ва файлов в архиве. Максимум: {_MAX_FILES}")
                    
            # parse file table (DataTable) lazily
            self._parse_datatable(f)
        
        return self.header

    def _parse_datatable(self, f: BinaryIO) -> None:
        """Парсит локальный репозиторий DataTable - массив заголовков архивированных файлов.

        Args:
            f (BinaryIO): Поток чтения текучего архива
        """        
        
        if self.header is None:
            raise RuntimeError("Header not loaded")
        f.seek(otik.OFF_DATATABLE)
        
        lengths_codes = self.header.code_table
        prefix = otik._endian_prefix(self.header.bytes_order)

        for i in range(self.header.file_count):
            hdr_blob = f.read(FH_FIXED_SIZE)
            if len(hdr_blob) < FH_FIXED_SIZE:
                raise EOFError("Unexpected EOF while reading file header")
            
            name_len = otik._unpack(f"{prefix}H", hdr_blob, 28)
            name_b = f.read(name_len)
            if len(name_b) < name_len:
                raise EOFError("Unexpected EOF while reading file name")
                       
            header = HeaderFile.from_bytes(hdr_blob, name_b, prefix)
            header.lengths_codes = lengths_codes
            self._local_file_headers.append(header)
                        
            # after name, move to next 8-byte aligned offset
            cur_pos = f.tell()
            next_aligned = _align_up(cur_pos, 8)
            if next_aligned > cur_pos:
                f.seek(next_aligned)
    
    def iter_files(self) -> Iterator[Tuple[HeaderFile, bytes]]:
        """Итератор по заголовкам из DataTable и упакованным данным. 
        Для файлов с compressed_size==0 возвращает empty bytes and data_offset==0.
                
        Raises:
            RuntimeError: _description_
            ValueError: _description_

        Yields:
            Iterator[Tuple[FileEntry, bytes]]: Итератор с заголовком файла и упакованными данными архива
        """        
        if self.header is None:
            self.open()
        
        if self.header is None:
            raise RuntimeError("Header not loaded")
                
        with open(self.path, "rb") as f:
            for hdr in self._local_file_headers:
                if hdr.compressed_size == 0 or hdr.data_offset == 0:
                    yield hdr, b""
                else:
                    f.seek(hdr.data_offset)
                    data = f.read(hdr.compressed_size)
                    
                    # optional: validate per-file crc32
                    if zlib.crc32(data) & 0xFFFFFFFF != hdr.crc32:
                        raise ValueError(f"CRC mismatch for file {hdr.name}")
                    
                    yield hdr, data

    def verify_data_crc(self) -> bool:
        """Проверка DataCrc32: вычисляет CRC32 по секции данных и сравнивает с полем в заголовке.

        Returns:
            bool: True - если вычисленный crc32 для секции данных едентичен хранимому в шапке архива
        """        
        
        # TODO: нужно тестироваать!
        
        with open(self.path, "rb") as f:
            start = self.header.data_section_offset
            end = self.header.archive_size
            
            if start == 0 or end <= start:
                # нет данных — CRC по пустому блоку == CRC32(b'') == 0?
                # CRC32(b'') == 0, так что сравниваем
                computed = zlib.crc32(b"") & 0xFFFFFFFF
                return computed == self.header.data_crc32
            
            f.seek(start)
            to_read = end - start
            crc = 0
            # read in chunks
            chunk_size = 2 << 16
            
            while to_read > 0:
                chunk = f.read(min(chunk_size, to_read))
                if not chunk:
                    break
                
                crc = zlib.crc32(chunk, crc)
                to_read -= len(chunk)
                
            crc &= 0xFFFFFFFF
            return crc == self.header.data_crc32

# End of module