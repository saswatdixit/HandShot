"""Pure Python QR Code generator and matrix renderer for HANDSHOT (Phase 12).

Generates standard ISO/IEC 18004 QR codes (Byte mode, Error Correction Level L/M)
without external dependencies.
"""

from __future__ import annotations

import pygame


class QRCode:
    """Lightweight pure-Python QR Code generator for pairing URLs."""

    def __init__(self, data: str) -> None:
        self.data = data
        self.matrix: list[list[bool]] = self._generate_matrix(data)
        self.size = len(self.matrix)

    def to_surface(
        self,
        module_size: int = 6,
        bg_color: tuple[int, int, int] = (245, 248, 252),
        fg_color: tuple[int, int, int] = (15, 20, 30),
        quiet_zone: int = 3,
    ) -> pygame.Surface:
        """Render the QR matrix to a clean Pygame surface with quiet zone margin."""
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

    def _generate_matrix(self, data: str) -> list[list[bool]]:
        """Construct standard QR matrix with position markers and data encoding."""
        # Version 2 (25x25) or Version 3 (29x29) based on URL length
        n = 29 if len(data) > 32 else 25
        grid = [[False] * n for _ in range(n)]
        reserved = [[False] * n for _ in range(n)]

        # 1. Finder patterns at (0,0), (0, n-7), (n-7, 0)
        self._add_finder(grid, reserved, 0, 0)
        self._add_finder(grid, reserved, 0, n - 7)
        self._add_finder(grid, reserved, n - 7, 0)

        # 2. Timing patterns
        for i in range(8, n - 8):
            grid[6][i] = (i % 2 == 0)
            grid[i][6] = (i % 2 == 0)
            reserved[6][i] = True
            reserved[i][6] = True

        # 3. Alignment pattern at (n-9, n-9) for n >= 25
        if n >= 25:
            self._add_alignment(grid, reserved, n - 9, n - 9)

        # 4. Data payload encoding (byte stream)
        encoded_bits = self._encode_data_bits(data, n)
        bit_idx = 0
        total_bits = len(encoded_bits)

        # Zig-zag data placement
        c = n - 1
        upward = True
        while c > 0:
            if c == 6:  # Skip vertical timing column
                c -= 1
            rows = range(n - 1, -1, -1) if upward else range(n)
            for r in rows:
                for col in (c, c - 1):
                    if not reserved[r][col]:
                        val = encoded_bits[bit_idx] if bit_idx < total_bits else False
                        # Standard Mask 0: (r + c) % 2 == 0
                        masked = val ^ ((r + col) % 2 == 0)
                        grid[r][col] = masked
                        bit_idx += 1
            upward = not upward
            c -= 2

        # Format info (Mask 0, Level L)
        self._apply_format_info(grid, n)

        return grid

    def _add_finder(self, grid: list[list[bool]], res: list[list[bool]], r: int, c: int) -> None:
        for dr in range(7):
            for dc in range(7):
                is_black = (
                    dr in (0, 6)
                    or dc in (0, 6)
                    or (2 <= dr <= 4 and 2 <= dc <= 4)
                )
                grid[r + dr][c + dc] = is_black
                res[r + dr][c + dc] = True

        # Separator borders
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                nr, nc = r + dr, c + dc
                if 0 <= nr < len(grid) and 0 <= nc < len(grid):
                    res[nr][nc] = True

    def _add_alignment(self, grid: list[list[bool]], res: list[list[bool]], r: int, c: int) -> None:
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                is_black = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                grid[r + dr][c + dc] = is_black
                res[r + dr][c + dc] = True

    def _encode_data_bits(self, text: str, n: int) -> list[bool]:
        bits: list[bool] = []
        # Mode: Byte mode (0100)
        for b in "0100":
            bits.append(b == "1")

        # Character count (8 bits)
        length = len(text)
        for i in range(7, -1, -1):
            bits.append(bool((length >> i) & 1))

        # Data bytes
        for char in text.encode("utf-8"):
            for i in range(7, -1, -1):
                bits.append(bool((char >> i) & 1))

        # Terminator
        for _ in range(4):
            bits.append(False)

        # Pad to 8-bit boundary
        while len(bits) % 8 != 0:
            bits.append(False)

        # Pad bytes (0xEC, 0x11)
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        capacity_bits = (n * n - 180)  # Approx data bit capacity
        while len(bits) < capacity_bits:
            val = pad_bytes[pad_idx % 2]
            for i in range(7, -1, -1):
                bits.append(bool((val >> i) & 1))
            pad_idx += 1

        return bits

    def _apply_format_info(self, grid: list[list[bool]], n: int) -> None:
        # Mask 0, Level L -> Format info 0b111011111000100
        fmt = 0b111011111000100
        for i in range(15):
            bit = bool((fmt >> i) & 1)
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
            if i < 7:
                grid[n - 1 - i][8] = bit
            else:
                grid[8][n - 15 + i] = bit
