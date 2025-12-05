
import argparse

from main import pack_archive, unpack_archive
from Archiver import ArchiveReader

# =================================================================================================================

def init() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Custom Archiver with Huffman + Hamming"
    )
    sub = parser.add_subparsers(dest="cmd")

    # ------------------------------------------------------------
    # pack
    # ------------------------------------------------------------
    p = sub.add_parser("pack", help="Создать архив")
    p.add_argument("-i", "--input", nargs="+", required=True)
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--bytes-order", default="little", choices=["little", "big"])
    p.add_argument("--huffman", action="store_true")
    p.add_argument("--hamming", action="store_true")
    p.add_argument("--r", type=int, default=4, help="r for Hamming (n=2^r-1). Default 4 => n=15,k=11")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--crc32", action="store_true")
    p.add_argument("--sha256", action="store_true")
    p.add_argument("--index-table", action="store_true")

    # Упрощённая передача в encode_file
    p.set_defaults(
        func=pack_archive,
    )

    # ------------------------------------------------------------
    # unpack
    # ------------------------------------------------------------
    u = sub.add_parser("unpack", help="Распаковать архив")
    u.add_argument("-i", "--input", required=True)
    u.add_argument("-o", "--output", required=True)
    u.add_argument("--verbose", action="store_true")
    u.set_defaults(func=unpack_archive)

    # ------------------------------------------------------------
    # info
    # ------------------------------------------------------------
    t = sub.add_parser("info", help="Показать информацию об архиве")
    t.add_argument("-i", "--input", required=True)
    t.set_defaults(func=info_mode)

    # ------------------------------------------------------------
    # verify
    # ------------------------------------------------------------
    v = sub.add_parser("verify", help="Проверить CRC")
    v.add_argument("-i", "--input", required=True)
    v.set_defaults(func=verify_mode)

    # ------------------------------------------------------------
    # cli
    # ------------------------------------------------------------
    d = sub.add_parser("cli", help="Интерактивный режим")
    d.set_defaults(func=cli_mode)
    
    return parser


# =================================================================================================================

def info_mode(args):
    """Печатает заголовок и информацию об архиве."""
    print("[info] Analyzing:", args.input)
    reader = ArchiveReader(args.input)
    hdr = reader.open()

    print("Archive header:")
    print(reader.header)

    print("\nFiles:")
    for header, _ in reader.iter_files():
        print(f" • {header.name}")
        print(f"   Original size: {header.original_size}")
        print(f"   Compressed:    {header.compressed_size}")
        print(f"   Flags:         {header.flags}")
        print(f"   Hamming r:     {header.control_bits}")

def verify_mode(args):
    """Проверяет архив без распаковки."""
    print("[verify]", args.input)
    reader = ArchiveReader(args.input)
    hdr = reader.open()
    print("CRC:", reader.verify_data_crc())

# =================================================================================================================

def cli_mode():
    """Консольный режим."""
    print("=== Archiver Interactive Mode ===")
        
    inpt = input("Введите файлы через пробел: ").split()
    out = input("Имя архива: ")

    use_huff = input("Использовать Хаффмана? (y/n): ").lower() == "y"
    use_hamm = input("Использовать Хэмминга? (y/n): ").lower() == "y"
    
    control_bits = 4
    #if use_hamm:
    #    control_bits = int(input("Введите r (обычно 4): "))

    class A:
        input = inpt
        output = out
        mode = (use_huff, use_hamm)
        r = control_bits
        bytes_order = 0
        verbose = True
        stats = True

    pack_archive(A)
    
# =================================================================================================================

def prepare_pack_args(args):
    """Подготавливает аргументы для pack"""
    
    if args.cmd != "pack":
        return args
    
    # Преобразуем mode
    args.mode = build_flags(args)
        
    # Преобразуем bytes_order
    if hasattr(args, "bytes_order"):
        args.bytes_order = bytes_order_to_flag(args.bytes_order)
    
    return args

# ==========================================
# Конвертация параметров в bitmask
# ==========================================

def build_flags(args):
    
    crc = args.crc32
    sha = args.sha256
    idx = args.index_table

    return (
        (1 if args.huffman else 0) |
        ((1 if args.hamming else 0) << 1) |
        ((1 if crc else 0) << 2) |
        ((1 if sha else 0) << 3) |
        ((1 if idx else 0) << 4)
    )

# ==========================================
# Конвертация little/big → 0/1
# ==========================================

def bytes_order_to_flag(order: str) -> int:
    return 0 if order == "little" else 1