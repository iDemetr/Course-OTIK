
from typing import List, Tuple
from utils import *

"""
Расширенный cистематический код Хэмминга, схема Л. Бриллюэна, с добавленным битом глобальной четности (SECDED).

Структура кодового слова:
    [ информационные биты | контрольные биты | глобальный бит четности ]

Особенности:
    - Классическая схема код Хэмминга
        - Длина кодового слова: n = 2^r + 1
        - Количество информационных битов: k = n – r
    - Добавляется один общий проверочный бит (overall parity).
    - Возможности:
        * Исправление 1 ошибки.
        * Обнаружение всех двойных ошибок.
        * Отличение ошибки в основном коде от ошибки в общем бите.

При декодировании появляются четыре случая:
| Синдром | Глобальная чётность | Значение                                        |
| ------- | ------------------- | ----------------------------------------------- |
| 0       | 0                   | Нет ошибок                                      |
| ≠0      | 1                   | Одиночная ошибка даннных → исправляется         |
| ≠0      | 0                   | Ошибка в самом общем бите → исправляется        |
| 0       | 1                   | ДВОЙНАЯ ошибка → обнаружена, но не исправляется |

Структура кодового слова:
    [ информационные биты ] + [ контрольные биты ] + [ общий бит четности ]

Атрибуты:
    r (int): Количество проверочных битов.
    n (int): Длина кодового слова.
    k (int): Количество информационных бит соответственно.
    control_bits (List[int]): Позиции проверочных битов.
    col (Dict[int,int]): Синдромы для всех позиций кодового слова.
    syndrome2pos (Dict[int,int]): Отображение синдром → позиция ошибки.

API:
    Hamming(r).pack(data) → (encoded_bytes, padding)
    Hamming(r).unpack(encoded, padding) → (decoded_bytes, corrected, uncorrectable)
"""

class Hamming:
# -------------------------------------------------------------------------------------------------        

    def __init__(self, r: int):
        """Создаёт кодер/декодер Хэмминга с параметром r

        Args:
            r (int): Количество контрольных бит. Должно быть >= 2.

        Raises:
            ValueError: Если r < 2.
        """        
        
        if r < 2:
            raise ValueError("r must be >=2")

        self.r = r
        self.n = (1 << r)
        self.k = self.n - r - 1 
        
        # Формируем матрицу H для систематического кода: [P^T | I_r | g]
        # g — столбец глобальной четности (все единицы)
        self.H = self._build_parity_matrix()
        
# -------------------------------------------------------------------------------------------------   

    def pack(self, data: bytes) -> tuple[bytes, int]:
        """Упаковывает поток байт с помощью кода Хэмминга.

        Последовательность действий:
            1. Преобразуем входные байты в битовый массив.
            2. Разбиваем поток на блоки по k бит.
            3. Каждый блок кодируется в n бит.
            4. В конце добавляется padding, если поток не кратен k.

        Args:
            data (bytes): Данные для кодирования.

        Returns:
            tuple:
            - encoded_data (bytes): Закодированные байты.
            - padding (int): Количество добитых нулевых бит в конце.
        """      
        
        bits = bytes_to_bits(data)
        
        # Нарезка искодного массива данных на блоки размером k
        padding = (self.k - (len(bits) % self.k)) % self.k
        if padding:
            bits += [0]*padding
            
        encoded_blocks = []
        for i in range(0, len(bits), self.k):
            block = bits[i:i+self.k]
            encoded_blocks += self._encode_block(block)
                    
        encoded_data = bits_to_bytes(encoded_blocks)
        return encoded_data, padding
    
    def unpack(self, data: bytes, padding: int) -> tuple[bytes, int, int]:
        """Декодирует поток байт, закодированный Хэммингом.

        Args:
            data (bytes): Закодированные данные.
            padding (int): Количество добитых нулевых бит, добавленных при pack().

        Returns:
            tuple:
            - decoded_data (bytes): Раскодированные байты.
            - corrected (int): Число исправленных одиночных ошибок.
            - uncorrectable (int): Число необрабатываемых (двойных) ошибок
        """     
        
        bits = bytes_to_bits(data)
        
        # process n-bit codewords
        if len(bits) % self.n != 0:
            # allow trailing zeros
            pass
        
        decoded_bits = []
        corrected = 0
        uncorrectable = 0
        
        for i in range(0, len(bits), self.n):
            block = bits[i:i+self.n]
            
            if len(block) < self.n:
                break
            
            info_bits, was_corrected, pos, was_uncorrectable = self._decode_block(block)
            decoded_bits += info_bits
            
            if was_corrected:
                corrected += 1
            if was_uncorrectable:
                uncorrectable += 1
                
        # trim padding
        if padding:
            decoded_bits = decoded_bits[: -padding]
            
        decoded_data = bits_to_bytes(decoded_bits)
        return decoded_data, corrected, uncorrectable

# -------------------------------------------------------------------------------------------------     

    def _encode_block(self, data_bits: List[int]) -> List[int]:
        """Кодирует один блок длиной k бит в n бит.

        Args:
            data_bits (List[int]): Информационные биты (длина k).

        Returns:
            List[int]: Кодовое слово длиной n (список 0/1).

        Raises:
            ValueError: Если длина входа не равна k.
        """     
        if len(data_bits) != self.k:
            raise ValueError("data_bits length must equal k")
        
        parity_bits, g = self._calc_parity_bits(data_bits)
        return data_bits + parity_bits + [g]
                    
# -------------------------------------------------------------------------------------------------  

    def _decode_block(self, encoded_bits: List[int]) -> Tuple[List[int], bool, int, bool]:
        """Декодирует кодовое слово Хэмминга длиной n бит.

        Args:
            encoded_bits (List[int]): Полученное кодовое слово.

        Returns:
            tuple:
            - data_bits (List[int]): Информационные биты (k шт.).
            - corrected (bool): Исправлена ли одиночная ошибка.
            - corrected_pos (int): Позиция исправленного бита (1-based) или 0.
            - uncorrectable (bool): Обнаружена ли необрабатываемая ошибка (двойная).
        """   

        if len(encoded_bits) != self.n:
            raise ValueError("recv_bits length must equal n")
                
        s, syndrome_val, double_error = self._check_errors_block(encoded_bits)
            
        # ---- Обработка ошибок ----
        return self._handler_decoded_errors(encoded_bits, double_error, syndrome_val)

# -------------------------------------------------------------------------------------------------  

    def _calc_parity_bits(self, data_bits: List[int]) -> Tuple[List[int], int]:
        """Вычисляет r контрольных бит и 1 глобальный.

        Args:
            data_bits (List[int]): _description_

        Raises:
            ValueError: _description_

        Returns:
            Tuple[List[int], int]: _description_
        """        

        if len(data_bits) != self.k:
            raise ValueError("Expected k data bits")

        # Контрольные биты
        parity_bits = []
        for row in self.H:
            s = 0
            for i in range(self.k):
                s ^= data_bits[i] & row[i]
            parity_bits.append(s)

        # Глобальная четность по всему слову: d + p
        global_parity = sum(data_bits) ^ sum(parity_bits)
        global_parity &= 1

        return parity_bits, global_parity

    def _check_errors_block(self, encoded_bits: List[int]) -> tuple[List[int], int, bool]:
        """Проверяет кодовое слово на ошибки при декодировании

        Args:
            encoded_bits (List[int]): Проверяемое кодовое слово

        Returns:
            tuple[List[int], int, bool]: _description_
        """        
        
        # ---- синдром r бит ----
        syndrome = []
        for row in self.H:
            s = 0
            for i in range(self.n):
                s ^= encoded_bits[i] & row[i]
            syndrome.append(s)

        syndrome_val = 0
        for i, b in enumerate(syndrome):
            syndrome_val |= (b << i)
        
        g_recv = encoded_bits[-1]
        # ---- проверка глобальной четности ----
        global_parity_calc = sum(encoded_bits[:-1]) & 1
        double_error = (global_parity_calc != g_recv)
        
        return syndrome, syndrome_val, double_error
    
    def _handler_decoded_errors(self, encoded_bits: List[int], double_error: bool, syndrome_val: int) -> Tuple[List[int], bool, int, bool]:
        """Обработчик ошибок, возникших при декодировании кодового слова

        Args:
            encoded_bits (List[int]): _description_
            double_error (bool): _description_
            syndrome_val (int): _description_

        Returns:
            Tuple[List[int], bool, int, bool]: _description_
        """        
        
        data = encoded_bits[:self.k]
        
        # ---- случаи обработки ----
        # 1) Нет ошибок: синдром 0, глобальная четность верна
        if syndrome_val == 0 and not double_error:
            return data, False, -1, False

        # 2) Двойная ошибка: синдром != 0 и глобальная четность неверна
        if syndrome_val != 0 and double_error:
            return data, False, -1, True

        # 3) Одиночная ошибка: синдром указывает позицию (1-based)
        # Позиции соответствуют столбцам H: 1..n
        if not (1 <= syndrome_val <= self.k):
            # Неверный синдром — двойная ошибка
            return data, False,  -1, True

        # Исправляем
        encoded_bits[syndrome_val - 1] ^= 1

        # После исправления извлекаем данные
        corrected_data = encoded_bits[:self.k]

        return corrected_data, True, syndrome_val, False  

    def _build_parity_matrix(self) -> List[List[int]]:
        """
        Строит матрицу проверок H размером r x n:

              d-bits | p-bits | g
           [   P^T   |   I_r  | 1 ]

        Где:
            P — произвольная матрица, удовлетворяющая 2^r >= k + r + 1.
            В данной реализации P строится как столбцы бинарных номеров.

        Возвращает матрицу H: список строк, каждая строка — r-я проверка.
        """

        H = []

        # Строим r строк
        for parity_row in range(self.r):
            row = []

            # Информационные биты: бинарный номер позиции
            for pos in range(1, self.k + 1):
                row.append((pos >> parity_row) & 1)

            # Контрольные биты: единичная диагональ
            for i in range(self.r):
                row.append(1 if i == parity_row else 0)

            # Глобальная четность: всегда 1
            row.append(1)

            H.append(row)

        return H
    
# -------------------------------------------------------------------------------------------------  