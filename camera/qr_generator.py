"""Standard-compliant pure-Python QR Code generator and Pygame renderer for HANDSHOT (Phase 13).

Generates 100% standard ISO/IEC 18004 QR codes (Byte mode, Error Correction Level M/L)
with Galois Field GF(256) Reed-Solomon error correction for universal phone camera scanning.
"""

from __future__ import annotations

import pygame


# Galois Field GF(256) tables with primitive polynomial 0x11D (285)
_EXP = [0] * 512
_LOG = [0] * 256

def _init_gf():
    val = 1
    for i in range(255):
        _EXP[i] = val
        _EXP[i + 255] = val
        _LOG[val] = i
        val <<= 1
        if val & 0x100:
            val ^= 0x11D
    _LOG[0] = 0

_init_gf()

def _gf_mul(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return _EXP[_LOG[x] + _LOG[y]]

def _rs_poly(ec_len: int) -> list[int]:
    """Generate Reed-Solomon error correction generator polynomial."""
    g = [1]
    for i in range(ec_len):
        root = _EXP[i]
        new_g = [0] * (len(g) + 1)
        for j in range(len(g)):
            new_g[j] ^= _gf_mul(g[j], root)
            new_g[j + 1] ^= g[j]
        g = new_g
    return g

def _rs_encode(data: list[int], ec_len: int) -> list[int]:
    """Compute Reed-Solomon error correction codewords for data."""
    gen = _rs_poly(ec_len)
    msg = data + [0] * ec_len
    for i in range(len(data)):
        lead = msg[i]
        if lead != 0:
            for j in range(len(gen)):
                msg[i + j] ^= _gf_mul(gen[len(gen) - 1 - j], lead)
    return msg[len(data):]


# QR Specifications for Version 2 (25x25) and Version 3 (29x29), Level L and M
# V2-L: 34 total bytes (44 data bits), 10 EC bytes -> 44 total codewords, 1 alignment at (18, 18)
# V3-L: 55 total bytes (70 data bytes), 15 EC bytes -> 70 total codewords, 1 alignment at (22, 22)
# V4-L: 80 total bytes (100 data bytes), 20 EC bytes -> alignment at (26, 26)

class QRCode:
    """Standard-compliant QR Code generator for pairing URLs."""

    def __init__(self, data: str) -> None:
        self.data = data
        self.matrix: list[list[bool]] = self._generate_matrix(data)
        self.size = len(self.matrix)

    def to_surface(
        self,
        module_size: int = 7,
        bg_color: tuple[int, int, int] = (255, 255, 255),
        fg_color: tuple[int, int, int] = (0, 0, 0),
        quiet_zone: int = 4,
    ) -> pygame.Surface:
        """Render the QR matrix to a high-contrast Pygame surface with adequate quiet zone."""
        grid_dim = self.size + quiet_zone * 2
        pixel_dim = grid_dim * module_size

        surface = pygame.Surface((pixel_dim, pixel_dim))
        surface.fill(bg_color)

        for r in range(self.size):
            for c in range(self.size):
                if self.matrix[r][c]:
                    px = (c + quiet_zone) * module_size
                    py = (r + quiet_zone) * module_size
                    pygame.draw.rect(
                        surface,
                        fg_color,
                        (px, py, module_size, module_size),
                    )

        return surface

    def _generate_matrix(self, text: str) -> list[list[bool]]:
        data_bytes = list(text.encode("utf-8"))
        # Choose minimum version that fits data_bytes
        if len(data_bytes) <= 32:
            version = 2
            size = 25
            total_codewords = 44
            ec_len = 10
            alignments = [18]
        elif len(data_bytes) <= 53:
            version = 3
            size = 29
            total_codewords = 70
            ec_len = 15
            alignments = [22]
        else:
            version = 4
            size = 33
            total_codewords = 100
            ec_len = 20
            alignments = [26]

        data_capacity = total_codewords - ec_len

        # 1. Encode payload into bitstream
        bits: list[int] = []
        # Mode: Byte (0100)
        bits.extend([0, 1, 0, 0])

        # Character count (8 bits for versions 1-9)
        length = len(data_bytes)
        for i in range(7, -1, -1):
            bits.append((length >> i) & 1)

        # Data bytes
        for b in data_bytes:
            for i in range(7, -1, -1):
                bits.append((b >> i) & 1)

        # Terminator (up to 4 zeroes)
        rem = data_capacity * 8 - len(bits)
        term_len = min(4, max(0, rem))
        bits.extend([0] * term_len)

        # Pad to 8-bit boundary
        while len(bits) % 8 != 0:
            bits.append(0)

        # Convert bits to byte list
        raw_data: list[int] = []
        for i in range(0, len(bits), 8):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) | bits[i + j]
            raw_data.append(byte_val)

        # Fill with pad bytes (0xEC, 0x11)
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        while len(raw_data) < data_capacity:
            raw_data.append(pad_bytes[pad_idx % 2])
            pad_idx += 1

        # 2. Compute Reed-Solomon Error Correction Codewords
        ec_bytes = _rs_encode(raw_data, ec_len)
        final_codewords = raw_data + ec_bytes

        # 3. Construct Matrix
        grid = [[False] * size for _ in range(size)]
        reserved = [[False] * size for _ in range(size)]

        # Finder patterns & separators
        self._place_finder(grid, reserved, 0, 0, size)
        self._place_finder(grid, reserved, 0, size - 7, size)
        self._place_finder(grid, reserved, size - 7, 0, size)

        # Timing patterns
        for i in range(8, size - 8):
            grid[6][i] = (i % 2 == 0)
            grid[i][6] = (i % 2 == 0)
            reserved[6][i] = True
            reserved[i][6] = True

        # Alignment patterns
        for ax in alignments:
            self._place_alignment(grid, reserved, ax, ax)

        # Reserve format info areas
        for i in range(9):
            reserved[8][i] = True
            reserved[i][8] = True
        for i in range(8):
            reserved[8][size - 1 - i] = True
            reserved[size - 1 - i][8] = True
        # Dark module
        grid[size - 8][8] = True
        reserved[size - 8][8] = True

        # 4. Place Data Codewords (Zig-Zag)
        bit_stream: list[int] = []
        for byte_val in final_codewords:
            for i in range(7, -1, -1):
                bit_stream.append((byte_val >> i) & 1)

        b_idx = 0
        c = size - 1
        upward = True
        while c > 0:
            if c == 6:
                c -= 1
            rows = range(size - 1, -1, -1) if upward else range(size)
            for r in rows:
                for col in (c, c - 1):
                    if not reserved[r][col]:
                        val = bit_stream[b_idx] if b_idx < len(bit_stream) else 0
                        # Apply Mask 0: (r + col) % 2 == 0
                        masked = (val ^ (((r + col) % 2) == 0)) == 1
                        grid[r][col] = masked
                        b_idx += 1
            upward = not upward
            c -= 2

        # 5. Place Format Information (Level L, Mask 0 -> 0x77C4 with BCH 0b111011111000100)
        self._place_format(grid, size, 0b111011111000100)

        return grid

    def _place_finder(self, grid: list[list[bool]], res: list[list[bool]], r: int, c: int, size: int) -> None:
        for dr in range(7):
            for dc in range(7):
                is_black = (
                    dr in (0, 6)
                    or dc in (0, 6)
                    or (2 <= dr <= 4 and 2 <= dc <= 4)
                )
                grid[r + dr][c + dc] = is_black
                res[r + dr][c + dc] = True

        # Separator margin
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size:
                    res[nr][nc] = True

    def _place_alignment(self, grid: list[list[bool]], res: list[list[bool]], r: int, c: int) -> None:
        if res[r][c]:
            return
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                is_black = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                grid[r + dr][c + dc] = is_black
                res[r + dr][c + dc] = True

    def _place_format(self, grid: list[list[bool]], size: int, fmt: int) -> None:
        for i in range(15):
            bit = bool((fmt >> (14 - i)) & 1)
            # Top-left placement
            if i <= 5:
                grid[8][i] = bit
            elif i == 6:
                grid[8][7] = bit
            elif i == 7:
                grid[8][8] = bit
            elif i == 8:
                grid[7][8] = bit
            else:
                grid[14 - i][8] = bit

            # Bottom-left and top-right copies
            if i < 8:
                grid[size - 1 - i][8] = bit
            else:
                grid[8][size - 15 + i] = bit
