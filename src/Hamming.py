
from typing import List, Tuple
from utils import *

"""Реализация систематического кода Хэмминга для произвольного параметра r.

Код Хэмминга исправляет одиночные ошибки и обнаруживает некоторые двойные.
Используется классическая схема:
    - Длина кодового слова: n = 2^r – 1
    - Количество информационных битов: k = n – r
    - Контрольные биты находятся в позициях степеней двойки (1,2,4,8,...).

Атрибуты:
    r (int): Количество проверочных битов.
    n (int): Длина кодового слова.
    k (int): Количество информационных бит соответственно.
    control_bits (List[int]): Позиции проверочных битов.
    col (Dict[int,int]): Синдромы для всех позиций кодового слова.
    syndrome2pos (Dict[int,int]): Отображение синдром → позиция ошибки.


API:
    - Hamming(r): класс с методами pack/unpack.
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
        self.n = (1 << r) - 1
        self.k = self.n - r

        self.calc_syndrome()
        
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
            encoded_blocks += self.encode_block(block)
                    
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
            - uncorrectable (int): Число блоков с необнаружимыми ошибками.
        """     
        
        bits = bytes_to_bits(data)
        
        # process n-bit codewords
        if len(bits) % self.n != 0:
            # allow trailing zeros
            pass
        
        info_bits = []
        corrected = 0
        uncorrectable = 0
        for i in range(0, len(bits), self.n):
            block = bits[i:i+self.n]
            
            if len(block) < self.n:
                break
            
            data_block, was_corrected, pos, uncorrect = self.decode_block(block)
            info_bits += data_block
            
            if was_corrected:
                corrected += 1
            if uncorrect:
                uncorrectable += 1
                
        # trim padding
        if padding:
            info_bits = info_bits[: -padding]
            
        decoded_data = bits_to_bytes(info_bits)
        return decoded_data, corrected, uncorrectable

# -------------------------------------------------------------------------------------------------     

    def calc_syndrome(self):
        """Предварительно вычисляет синдромы для всех позиций кода.

        Используется классическая формула: позиция кодового слова p представляется в двоичном
        виде, и эта двоичная маска определяет влияние бита на каждый контрольный бит.

        Создаёт:
            - col[p] = синдром позиции p
            - syndrome2pos[s] = позиция, где ошибка вызывает синдром s
        """
        
        # parity positions: pow(r) (1-based)
        self.control_bits = [1 << i for i in range(self.r)]    # 0,1,4 ...
        
        # постройте H столбцов матрицы (векторов синдрома) для позиций 1..n (на основе 1)
        # каждый столбец представляет собой r-разрядное целое число, где бит i - это четность для control_bits[i]
        self.col = {}
        
        # цикл по информационным битам
        for pos in range(1, self.n + 1):
            v = 0
            # цикл по контрольным битам            
            for i in range(self.r):
                if ((pos >> i) & 1):    # "бинарный поиск"
                    v |= (1 << i)       # установка флагов подконтроля битов
                    
            self.col[pos] = v
            
        # map syndrome -> position (if nonzero)
        self.syndrome2pos = {v: pos for pos, v in self.col.items() if v != 0}   

# -------------------------------------------------------------------------------------------------     

    def encode_block(self, data_bits: List[int]) -> List[int]:
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
        
        # Резерв кодового слова 1..n для удобного итерирования
        codeword = [0] * (self.n + 1)
        # Размещение бит данных в информационные биты
        di = 0
        for pos in range(1, self.n + 1):
            if pos in self.control_bits:
                continue
            codeword[pos] = data_bits[di] & 1
            di += 1
            
        # вычисление четности подконтрольных бит
        for cb in self.control_bits:                 # 0,1,4 ...
            parity = 0            
            # обход подконтрольных информационных бит
            for pos in range(1, self.n + 1):
                if (pos & cb) != 0:
                    parity ^= codeword[pos] # XOR для нахождения четности
            codeword[cb] = parity  # parity chosen to make parity over set = s (so overall parity zero)
            
        return codeword[1:]
            
# -------------------------------------------------------------------------------------------------  

    def decode_block(self, encoded_bits: List[int]) -> Tuple[List[int], bool, int, bool]:
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
        
        # Расширение кодового слова 1..n для удобного итерирования
        codeword = [-1] + encoded_bits
        
        # Вычисление ошибки - сравнение синдромов
        syndrom = 0
        for cb in self.control_bits:                 # 0,1,4 ...
            parity = 0
            for pos in range(1, self.n + 1):
                if (pos & cb) != 0: 
                    parity ^= codeword[pos] # XOR для нахождения четности
            if parity:
                syndrom |= cb  # отметка синдрома
                
        # Если ошибок нет - вытягиваем информационные биты
        if syndrom == 0:
            data = []
            for pos in range(1, self.n + 1):
                if pos in self.control_bits:
                    continue
                data.append(codeword[pos])
            return data, False, 0, False
        
        # Иначе ошибка: syndrom указывает на положение однобитовой ошибки, если в пределах 1..n
        pos = self.syndrome2pos.get(syndrom, None)
        is_error = pos is not None
        # Коррекция
        if is_error:
            codeword[pos] ^= 1
        
        data = []
        for pos2 in range(1, self.n + 1):
            if pos2 in self.control_bits:
                continue
            data.append(codeword[pos2])
        return data, is_error, pos or 0, not is_error

# -------------------------------------------------------------------------------------------------  