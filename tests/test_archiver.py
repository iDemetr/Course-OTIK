#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для комбинации Huffman + Hamming.

Запуск:
    python -m unittest -v test_archiver.py
или (если запускаешь директорию tests/):
    python -m unittest discover -v

Тесты:
- test_roundtrip_random_bytes: проверяет, что данные после полного цикла
  (Хаффман -> Хэмминг -> Хэмминг -> Хаффман) совпадают с исходными.
- test_hamming_single_bit_correction: инвертирует 1 бит в закодированном потоке
  Хэмминга и проверяет, что обнаружена/исправлена одиночная ошибка и данные
  успешно восстановлены.
- test_canonical_codes_consistency: простая проверка, что для небольшого
  набора частот канонические коды сгенерированы (есть код и положительная длина).
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import random
import unittest

from src import Huffman as huffman_mod
from src import Hamming as hamming_mod

class TestArchiverPipeline(unittest.TestCase):
    """Набор тестов для проверки корректности работы кодировщика/декодировщика."""

    def test_roundtrip_random_bytes(self):
        """Roundtrip: Huffman -> Hamming -> Hamming -> Huffman (random data)."""
        random.seed(12345)
        data = bytes(random.getrandbits(8) for _ in range(1024))  # 1 KB случайных данных

        h = huffman_mod.Huffman()
        ham = hamming_mod.Hamming(4)

        # Кодируем Хаффманом
        lengths_bytes, encoded_data, _dummy, total_bits = h.pack(data)
        # Кодируем Хэммингом
        # Замечание: текущая версия Hamming.pack в исходном коде возвращает 3 значения:
        # (some_bytes, encoded_data, padding). Мы сохраняем lengths_bytes отдельно,
        # чтобы не потерять метаданные Хаффмана.
        hamming_bytes, padding = ham.pack(encoded_data)

        # Распаковываем Хэммингом
        decoded_data, corrected, uncorrectable = ham.unpack(hamming_bytes, padding)

        # Декодируем Хаффманом, используя исходные lengths_bytes и total_bits
        recovered = h.unpack(decoded_data, lengths_bytes, total_bits)
        self.assertEqual(recovered, data,
                         "Данные после полного цикла не совпадают с исходными")

    def test_hamming_single_bit_correction(self):
        """Проверяем, что Хэмминг исправляет одиночный бит ошибки и данные восстанавливаются."""
        random.seed(1)
        data = bytes(random.getrandbits(8) for _ in range(256))
        h = huffman_mod.Huffman()
        ham = hamming_mod.Hamming(4)

        lengths_bytes, encoded_data, _, total_bits = h.pack(data)
        hamming_bytes, padding = ham.pack(encoded_data)

        # Инвертируем 1 бит в середине потока
        ba = bytearray(hamming_bytes)
        if len(ba) == 0:
            self.skipTest("Hamming produced empty output, пропускаем тест")
        byte_idx = len(ba) // 2
        bit_idx = 3
        ba[byte_idx] ^= (1 << bit_idx)
        corrupted = bytes(ba)

        decoded_data, corrected, uncorrectable = ham.unpack(corrupted, padding)
        
        # Ожидаем, что хотя бы одна одиночная ошибка была исправлена
        self.assertGreaterEqual(corrected, 1, "Ожидалась исправленная одиночная ошибка")
        recovered = h.unpack(decoded_data, lengths_bytes, total_bits)
        self.assertEqual(recovered, data, "Данные не совпали после коррекции одиночной ошибки")

    def test_canonical_codes_consistency(self):
        """Проверка, что для простого набора частот канонические коды сгенерированы."""
        h = huffman_mod.Huffman()
        h.freqs = {i: (5 - i) for i in range(5)}  # частоты: 5,4,3,2,1
        h._build_huffman_lengths()
        h._canonical_codes_from_lengths()
        for sym in range(5):
            self.assertIn(sym, h.canonical_codes)
            code, length = h.canonical_codes[sym]
            self.assertGreater(length, 0)
            self.assertIsInstance(code, int)


if __name__ == "__main__":
    # Запуск тестов командой: python -m unittest -v test_archiver.py
    unittest.main(verbosity=2)


