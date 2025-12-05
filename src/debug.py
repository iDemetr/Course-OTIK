from heapq import heappush, heappop
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Iterable

from Huffman import *
from Hamming import *
from utils import *

f = open("docs/chess16.jpg", 'rb').read()
print(f, type(f))

huffman = Huffman()

lenght_bytes, encoded_data, _, total_bits = huffman.pack(f)

# print("-"*20)

# print(f'{lenght_bytes=}')
# bits = bytes_to_bits(encoded_data);
# print(f'{bits=}')
# print(f'{total_bits=}')

# print("-"*20)

decoded_bytes = huffman.unpack(encoded_data, lenght_bytes, total_bits)

print("-"*20)
print(decoded_bytes)
print(len(f), len(encoded_data))
#print(f)
print(f == decoded_bytes)
print("-"*20)

print("="*40)

hamming = Hamming(4)

# lengths_bytes, data_bytes, padding = hamming.pack(f)

# print("-"*20)

# print(f'{lengths_bytes=}')
# print(f'{padding=}')
# print(f'{data_bytes=}')

# print("-"*20)

# decoded_data, corrected, uncorrectable = hamming.unpack(data_bytes, padding)

# print("-"*20)
# print(f"corrected blocks={corrected}, uncorrectable={uncorrectable}")
# print(decoded_data)
# print(f)
# print(f == decoded_data)
# print("-"*20)

# print("="*40)




# lenght_bytes, encoded_data, _, total_bits = huffman.pack(f)
# protected_bytes, padding = hamming.pack(encoded_data)

# recovered_bytes, corrected, uncorrectable = hamming.unpack(protected_bytes, padding)
# decoded_data = huffman.unpack(recovered_bytes, lenght_bytes, total_bits)

# print("-"*20)
# print(f"corrected blocks={corrected}, uncorrectable={uncorrectable}")
# #print(decoded_bytes)
# #print(f)
# print(f == decoded_data)
# print(len(f), len(decoded_data), len(protected_bytes), len(encoded_data))
# print("-"*20)

# print("="*40)













# print("cnter: ", Counter(f))

# lens = huffman._build_huffman_lengths(Counter(f))
# print("lens: ", lens)

# canon_codes = huffman._canonical_codes_from_lengths(lens)
# print("canon codes: ", canon_codes)

# encoded_data = huffman._encode_bytes(f, canon_codes)
# print("encoded data: ", encoded_data)

# decode_table = huffman._build_decode_table_from_canonical(canon_codes)
# print(decode_table)

# bits = bytes_to_bits(encoded_data[0])
# total_bits = len(bits)

# it = iter(bits)
# def reader():
#     tmp = next(it)
#     return tmp

# restored_data = huffman._decode_bits_with_table(reader, decode_table, total_bits, len(f))

# print(restored_data)
# print(restored_data == f)