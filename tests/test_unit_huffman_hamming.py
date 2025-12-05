# tests/test_unit_huffman_hamming.py

import sys, os
# Добавляем src/ в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import random
import unittest

from Huffman import *
from Hamming import *
from utils import *

# ======================================================================
#                        UNIT TESTS FOR HUFFMAN
# ======================================================================

class TestHuffmanInternals(unittest.TestCase):

    def test_frequency_counting(self):
        h = Huffman()
        data = b"AAABBC"
        h.freqs = {}  # убедимся что не было старых данных
        h.freqs = dict()
        h.freqs = dict()
        # Просто вызываем pack(), там вызывается Counter
        lengths_bytes, packed, padding, total_bits = h.pack(data)
        self.assertEqual(h.freqs[65], 3)  # 'A'
        self.assertEqual(h.freqs[66], 2)  # 'B'
        self.assertEqual(h.freqs[67], 1)  # 'C'

    def test_build_huffman_lengths(self):
        h = Huffman()
        h.freqs = {0: 5, 1: 7, 2: 10}
        h._build_huffman_lengths()

        # длины должны быть > 0 для каждого символа
        for k, v in h.lengths.items():
            self.assertGreater(v, 0)

    def test_canonical_codes_generation(self):
        h = Huffman()
        h.lengths = {0: 3, 1: 2, 2: 2}
        h._canonical_codes_from_lengths()

        # должны быть (code, length)
        for sym in (0, 1, 2):
            self.assertIn(sym, h.canonical_codes)
            code, l = h.canonical_codes[sym]
            self.assertGreater(l, 0)
            self.assertIsInstance(code, int)

    def test_encode_decode_roundtrip(self):
        h = Huffman()
        data = b"AAAAABBBCCD"

        lengths_bytes, encoded, padding, total_bits = h.pack(data)
        decoded = h.unpack(encoded, lengths_bytes, total_bits)

        self.assertEqual(decoded, data)


# ======================================================================
#                        UNIT TESTS FOR HEMMING
# ======================================================================

class TestHammingInternals(unittest.TestCase):

    def test_syndrome_table(self):
        ham = Hamming(3)  # r=3 → n=7, k=4
        self.assertEqual(ham.n, 7)
        self.assertEqual(ham.k, 4)
        # control bits = [1, 2, 4]
        self.assertEqual(ham.control_bits, [1, 2, 4])
        # Проверим что синдромы созданы
        self.assertEqual(len(ham.col), ham.n)

    def test_encode_decode_single_block(self):
        ham = Hamming(3)  # 7,4 код
        data_bits = [1, 0, 1, 1]  # 4 бита

        encoded = ham.encode_block(data_bits)
        self.assertEqual(len(encoded), ham.n)

        decoded, corrected, pos, uncorrectable = ham.decode_block(encoded)
        self.assertEqual(decoded, data_bits)
        self.assertFalse(corrected)
        self.assertFalse(uncorrectable)

    def test_correct_single_bit_error(self):
        ham = Hamming(3)
        data = b"\xAF"  # произвольный байт

        encoded_bytes, padding = ham.pack(data)
        bits = bytes_to_bits(encoded_bytes)

        # вносим ошибку в кодовое слово
        bits[3] ^= 1

        corrupted = bits_to_bytes(bits)
        decoded, corrected, uncorrectable = ham.unpack(corrupted, padding)

        self.assertEqual(decoded, data)
        self.assertGreaterEqual(corrected, 1)
        self.assertEqual(uncorrectable, 0)

    def test_detect_uncorrectable(self):
        ham = Hamming(3)
        data = b"\xAA"

        encoded_bytes, padding = ham.pack(data)
        bits = bytes_to_bits(encoded_bytes)

        # 2 ошибки → должно быть uncorrectable
        bits[1] ^= 1
        bits[4] ^= 1

        corrupted = bits_to_bytes(bits)
        decoded, corrected, uncorrectable = ham.unpack(corrupted, padding)

        self.assertEqual(uncorrectable, 1)


# ======================================================================
#                        UNIT TESTS FOR UTILS
# ======================================================================

class TestUtils(unittest.TestCase):

    def test_lengths_to_from_bytes(self):
        lengths = {10: 3, 20: 5, 30: 8}
        b = lengths_to_bytes(lengths)
        restored = lengths_from_bytes(b)

        self.assertEqual(restored, lengths)

    def test_bit_conversion(self):
        bits = []
        byte_to_bits(bits, 0b10101100, 8)
        self.assertEqual(bits, [1,0,1,0,1,1,0,0])

        out = bits_to_bytes(bits)
        self.assertEqual(out, b'\xac')

        back = bytes_to_bits(out)
        self.assertEqual(back, bits)


if __name__ == "__main__":
    unittest.main()
