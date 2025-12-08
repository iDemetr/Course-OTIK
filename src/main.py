"""
CLI encoder:
Usage example:
  py src/main.py pack -i file1.bin file2.jpg -o data.arc --stats --verbose
  py src/main.py unpack -i data.arc -o out/
  py src/main.py info -i data.arc
  py src/main.py verify -i data.arc
  py src/main.py cli

mode: two-char string: bit0=huffman, bit1=hamming, e.g. "11" both.
r: parameter r for Hamming (default 4 -> n=15,k=11)
"""

# =================================================================================================================

import cli

from Huffman import *
from Hamming import *
from Archiver import *

# =================================================================================================================

def pack_archive(args):
    """Архивирует файлы в контейнер."""
    if args.verbose:
        print("[pack] preparing archive:", args.output)
        print("[pack] input files:", args.input)
        
    writer = ArchiveWriter(args)
    
    for f in args.input:
        if not os.path.exists(f):
            print(f"[ERROR] File not found: {f}")
            continue
        
        name = os.path.basename(f)
        if args.verbose:
            print(f"[pack] Encoding file: {name}")
        
        res = encode_file(f, args)
        writer.add_file(name, res)
        
    writer.finalize()
    
    if args.stats:
        print("\n=== Statistics ===")
        for f in args.input:
            size = os.path.getsize(f)
            print(f"• {os.path.basename(f)}: {size} bytes → compressed")
        print("Archive saved to:", args.output)

def unpack_archive(args):
    """Распаковывает архив."""
    print("[unpack] Reading archive:", args.input)
    
    reader = ArchiveReader(args.input)
    hdr = reader.open()
    if args.verbose:
        print("Header:", reader.header)
    
    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)
    
    for header, data in reader.iter_files():
        if args.verbose:
            print(f"[unpack] Entry: {header.name} ({len(data)} bytes)")
        
        raw_data = decode_file(data, header)
        outpath = os.path.join(out_dir, header.name)
        
        with open(outpath, "wb") as f:
            f.write(raw_data)
            print(" → Saved to", outpath)
        
    print("CRC ok:", reader.verify_data_crc())

# =================================================================================================================

def encode_file (file:str, args) -> dict:
    """Выполняет кодирование с указанными параметрами

    Args:
        file (str): путь к архивируемому файлу
        args (_type_): параметры для архивации

    Returns:
        dict:
        - data (bytes): упаковынный массив байт 
        - lengths_codes (bytes): массив длин кодов Хаффмана
        - flags (int): режим кодировки файла
        - paddingHuff (int): количество дополнительных нулей в последнем байте Хаффмана
        - r (int): количество контрольных бит Хэмминга
        - paddingHamm (int): количество дополнительных нулей в блоке Хэмминга
    """    
    with open(file, "rb") as f:
        raw_data = f.read()
            
    tmp_data = raw_data
    lengths_codes = bytes([0]*256)
    paddingHamm = 0
    paddingHuff = 0
    r = 0
    
    if args.huffman:
        huffman = Huffman()
        tmp_data, lengths_codes, paddingHuff = huffman.pack(tmp_data)
    
    if args.hamming:
        r = args.r
        hamming = Hamming(r)
        tmp_data, paddingHamm = hamming.pack(tmp_data)
            
    # definition earlier: bit0 (LSB) = huffman used, bit1 = hamming used
    print(f"Encoded {len(tmp_data)} bytes -> archive {args.output}, mode {bin(args.mode)}")
    
    return {
        "data": tmp_data,
        "lengths_codes": lengths_codes,
        "flags": args.mode & 0xFFFFFFFF,                 # Huffman, Hamming, crc32, SHA256, isIndexTable
        "padding_huff": paddingHuff,
        "r": r,
        "padding_hamm": paddingHamm,
        "raw_size": len(raw_data),
        "compressed_size": len(tmp_data)
    }

def decode_file (data: bytes, header: HeaderFile) -> bytes:
    """Автоматически определяет режим из заголовка и выполняет декодирование

    Args:
        data (bytes): _description_
        header (HdrFile): _description_

    Returns:
        bytes: _description_
    """    
    
    lengths_codes = header.lengths_codes
    raw_size = header.original_size
    mode = header.flags 
        
    huffman_used = bool(mode & 0x1)
    hamming_used = bool(mode & 0x2)
    
    if hamming_used:
        hamming = Hamming(header.control_bits)
        data, corrected, uncorrectable = hamming.unpack(data, header.padding_Hamm)
        print(f"corrected blocks={corrected}, uncorrectable={uncorrectable}")
                
        if not huffman_used:
            return data[:raw_size]
    
    if huffman_used:
        huffman = Huffman()        
        data = huffman.unpack(data, lengths_codes, header.padding_Huff)
        return data[:raw_size]
              
    if not hamming_used and not huffman_used:
        # raw copy
        return data[:raw_size]   
    
    raise  

# =================================================================================================================

def main():
    
    parser = cli.init()
    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return
    
    args.func(cli.prepare_pack_args(args))

# =================================================================================================================

if __name__ == "__main__":
    main()
