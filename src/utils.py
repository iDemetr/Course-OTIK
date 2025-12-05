from typing import List, Dict

def lengths_to_bytes(lengths: Dict[int,int]) -> bytes:
    """Сериализует таблицу длин кодов в компактный байтовый формат.
    Используем массив из 256 байт, где индекс = символ, значение = длина кода.
    Длина 0 означает, что символ отсутствует в таблице.

    Args:
        lengths (Dict[int,int]): Словарь длин кодов {символ: длина_кода}

    Returns:
        bytes: Массив размера 256, где i-тый байт — длина символа i.

    Пример:
        Вход: {65: 3, 66: 4, 67: 2}
        Выход: байты где [65]=3, [66]=4, [67]=2, остальные 0
    """
    # Создаем массив из 256 нулей (по одному байту на каждый возможный символ 0-255)
    byte_array = bytearray(256)
    # Заполняем массив: для каждого символа записываем его длину кода
    for symbol, length in lengths.items():
        # Ограничиваем длину 1 байтом (0-255) с помощью маски 0xFF
        byte_array[symbol] = length & 0xFF
    return bytes(byte_array)

def lengths_from_bytes(data: bytes) -> Dict[int,int]:
    """Десериализует таблицу длин кодов из байтового представления.
    
    Обратная операция к lengths_to_bytes - преобразует массив байт обратно в словарь длин кодов.

    Args:
        data (bytes): Последовательность из 256 байт.

    Returns:
        Dict[int,int]: {символ: длина кода}

    Пример:
        Вход: байты где [65]=3, [66]=4, [67]=2, остальные 0
        Выход: {65: 3, 66: 4, 67: 2}
    """
    result = {}
    # Проходим по всем 256 возможным символам (индексам 0-255)
    for symbol_index, length_value in enumerate(data[:256]):
        # Если длина не равна 0, значит символ присутствует в таблице
        if length_value != 0:
            # Добавляем в результат: символ -> длина кода
            result[symbol_index] = length_value
    return result

def byte_to_bits(bits: List[int], byte: int, length: int):
    """Добавляет в битовый буфер двоичное представление числа фиксированной длины.

    Args:
        bitbuf (List[int]): Целевой буфер битов.
        bits (int): Число, из которого извлекаются биты.
        length (int): Количество записываемых бит (старшие первыми).
    """
    for i in range(length - 1, -1, -1):
        bits.append((byte >> i)&1)        # захват i-того бита

def bits_to_bytes(bits: List[int]) -> bytes:
    """Преобразует массив битов в массив байтов (big-endian внутри байта).

    Args:
        bit_list (List[int]): Список битов 0/1.

    Returns:
        bytes: Упакованные байты.
    """
    out = bytearray((len(bits)+7)//8)       # буфер с целым числом байт в большую сторону
    for i, bit in enumerate(bits):
        if bit:
            byte_id = i // 8                # счетчик байтов
            bit_id = 7 - (i % 8)            # счетчик битов
            out[byte_id] |= (1 << bit_id)
            
    return bytes(out)

def bytes_to_bits(b: bytes) -> List[int]:
    """Преобразует байты в последовательность битов.

    Args:
        b (bytes): Входные данные.

    Returns:
        List[int]: Список битов (0/1).
    """
    bits = []
    for byte in b:
        byte_to_bits(bits, byte, 8)
    return bits
