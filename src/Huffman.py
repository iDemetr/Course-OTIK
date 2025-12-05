
from heapq import heappush, heappop
from typing import Dict, Tuple
from collections import Counter

from utils import *

"""Канонический кодек Хаффмана.

Поддерживает:
    - построение длины кодов для каждого символа по частотам
    - генерацию канонических кодов (canonical Huffman codes)
    - кодирование произвольного массива байтов
    - декодирование по переданной таблице длин

Атрибуты:
    freqs (Dict[int,int]): Частоты символов во входном будущем.
    lengths (Dict[int,int]): Длины кодов Хаффмана.
    canonical_codes (Dict[int, Tuple[int, int]]): Канонические коды (код, длина).

API:
    - Huffman(): класс с методами pack/unpack.
"""

class Huffman:
# -------------------------------------------------------------------------------------------------        
    
    def __init__(self):
        """Инициализирует локальные СД
        """        
        self.freqs: dict = dict()
        self.lengths : dict = dict()
        self.canonical_codes: dict[int, tuple[int,int]] = dict()

# -------------------------------------------------------------------------------------------------   

    def pack(self, data: bytes) -> tuple[bytes, bytes, int]:
        """Кодирует массив байтов с помощью канонического Хаффмана.

        Args:
            data (bytes): Входные данные.

        Returns:
            tuple:
            - packed (bytes): Кодированные данные.
            - lengths_codes (bytes): Сериализованные длины кодов (256 байт).
            - padding (int): Количество незначимых бит в packed.
        """
        
        self.freqs = Counter(data)
        
        self._build_huffman_lengths()
        self._canonical_codes_from_lengths()
        
        lengths_codes = lengths_to_bytes(self.lengths)
        
        packed, padding = self._encode_bytes(data)
        return packed, lengths_codes, padding
    
    def unpack(self, data_bytes: bytes, lengths_codes: bytes, padding: int) -> bytes:
        """Декодирует байты, закодированные каноническим кодом Хаффмана.

        Args:
            data_bytes (bytes): Поток с закодированными значениями.
            lengths_codes (bytes): Таблица длин кодов (256 байт).
            padding (int): Число незначимых бит.

        Returns:
            bytes: Декодированные исходные данные.
        """

        self.lengths = lengths_from_bytes(lengths_codes)
        self._canonical_codes_from_lengths()
        
        decode_table = self._build_decode_table_from_canonical()
        encoded_bits = bytes_to_bits(data_bytes)
        total_bits = len(encoded_bits) - padding
        
        return self._decode_bits_with_table(encoded_bits, decode_table, total_bits)
        
# -------------------------------------------------------------------------------------------------        

    def _build_huffman_lengths(self):
        """Строит классическое дерево Хаффмана и вычисляет длины кодов для всех символов.

        Использует минимальную кучу для построения дерева.  
        Символы, отсутствующие во входных данных, не включаются.
        """

        # Входной файл пуст
        if not self.freqs:
            return {}

        # Входной файл состоит из одного символа
        if len(self.freqs) == 1:
            sym, _ = self.freqs.popitem()
            return {sym:1} 

        # Формирование стека
        # элемент кучи — это узел дерева Хаффмана вида
        # (вес, уникальный_счётчик, символ_или_поддерево)
        heap = []
        uniq_id = 0

        for sym, w in self.freqs.items():
            heappush(heap, (w, uniq_id, sym))
            uniq_id += 1

        while len(heap) > 1:  # Построение классического дерева по Хаффману
            w1, _, n1 = heappop(heap)
            w2, _, n2 = heappop(heap)
                    
            heappush(heap, (w1 + w2, uniq_id, (n1, n2)))
            uniq_id += 1
    
        _, _, root = heap[0]

        def dfs(node, depth):
            '''Обход дерева в глубину'''
            if isinstance(node, int):   # если достингут лист дерева - базовый случай
                self.lengths[node] = depth
            else:                       # рекурсивный случай
                left, right = node
                dfs(left, depth + 1)
                dfs(right, depth + 1)

        dfs(root, 0)  # Каждый символ получает длину кода равный его глубине в дереве
    
    def _canonical_codes_from_lengths(self):
        """Генерирует канонические коды Хаффмана по таблице длин.

        Канонический код Хаффмана:
            - сортирует символы по (длина, символ)
            - на каждом уровне длины кодов ведётся счётчик
            - коды упорядочены лексикографически по длине и значению символа

        В результате получается компактное и предсказуемое отображение:
            symbol → (code, length)
        """

        # Переупаковка в {длина, символ}
        pairs = [(l, sym) for sym, l in self.lengths.items() if l > 0]
        if not pairs:
            return {}

        # Сортировка по возрастанию длины, а при равенстве — по значению символа
        pairs.sort(key=lambda x: (x[0], x[1]))
        maxbits = pairs[-1][0]

        # Подсчет кол-ва символов каждой длины
        chars_on_layers = [0] * (maxbits + 1)
        for l, _ in pairs:
            chars_on_layers[l] += 1

        # Генерация первого кода каждой длины
        code = 0
        all_codes_on_layers = {}
        
        # Проход в глубницу дерева по слоям для формирования уникальных кодов
        for layer in range(1, maxbits + 1):
            code = (code + chars_on_layers[layer - 1]) << 1
            all_codes_on_layers[layer] = code   # Сохранение стартового номера на слое
            # print(code)

        # Присвоение кодов символам
        for l, sym in pairs:
            code = all_codes_on_layers[l]
            self.canonical_codes[sym] = (code, l)
            all_codes_on_layers[l] += 1

# -------------------------------------------------------------------------------------------------

    def _encode_bytes(self, data: bytes) -> Tuple[bytes, int]:
        """Кодирует массив байтов, заменяя каждый символ его битовым кодом.

        Args:
           data (bytes): Входные данные.

        Returns:
            tuple:
            - bytes: Упакованные данные.
            - int: padding bits to bytes.
        """

        bitbuf = []
        for b in data:
            new_code, l = self.canonical_codes[b]
            byte_to_bits(bitbuf, new_code, l)

        # собираем из бит байты, заполняя старшие биты первыми
        out = bits_to_bytes(bitbuf)
        return out, 8 - len(bitbuf) % 8
        
# -------------------------------------------------------------------------------------------------

    def _build_decode_table_from_canonical(self) -> Dict[int, Dict[int, int]]:
        """Создаёт таблицу для быстрого декодирования канонических кодов.

        Таблица строится в формате:
            length → {code → symbol}
            
        Returns:
            Dict[int, Dict[int, int]]: Cловарь таблицы декодирования {длина_кода: {битовый_код: символ}}
        
        Пример:
            Вход: {65: (0b00, 2), 66: (0b01, 2), 67: (0b110, 3)}
            Выход: {2: {0: 65, 1: 66}, 3: {6: 67}}
        """
        
        # Создаем пустую таблицу декодирования
        table = {}

        # Проходим по всем символам и их кодам
        for sym, (code, code_length) in self.canonical_codes.items():
            # Для каждой длины кода создаем подтаблицу, если её еще нет
            # setdefault(l, {}) возвращает словарь для длины l, создает пустой если нет
            subtable_for_length = table.setdefault(code_length, {})

            # Добавляем в подтаблицу соответствие: битовый_код -> символ
            subtable_for_length[code] = sym

        return table

    def _decode_bits_with_table(self, encoded_bits, decode_table_by_length, total_bits: int):
        """Декодирование битового потока по таблице по длине.

        Args:
            encoded_bits:
            decode_table_by_length: dict length -> dict(code_bits -> symbol)
            total_bits: количество декодируемых бит
            
        Returns:
            byteArray: раскодированный массив байт
        """
        out = bytearray()
        cur = 0
        cur_len = 0

        bits_consumed = 0
        
        for bit in encoded_bits:        
            cur = (cur << 1) | bit
            cur_len += 1
            bits_consumed += 1
            
            if bits_consumed > total_bits:
                break
            
            table = decode_table_by_length.get(cur_len, None)
            if table and cur in table:
                out.append(table[cur])
                cur = 0
                cur_len = 0
                
        return bytes(out)
