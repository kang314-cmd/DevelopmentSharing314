"""계산기 창만 캡처해 데모 이미지를 저장합니다."""

import ctypes
import struct
import time
import tkinter as tk
import zlib
from ctypes import wintypes

from calculator import Calculator

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def capture_window_bmp(title: str, output_path: str) -> tuple[bytearray, int, int]:
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        raise SystemExit(f"'{title}' 창을 찾지 못했습니다.")

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)
    user32.PrintWindow(hwnd, mem_dc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buffer_size = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_size)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)

    bgr = bytearray()
    for i in range(0, len(buffer), 4):
        bgr.extend(buffer[i + 2 : i + 3])
        bgr.extend(buffer[i + 1 : i + 2])
        bgr.extend(buffer[i : i + 1])

    row_stride = ((width * 3 + 3) // 4) * 4
    padded = bytearray()
    for y in range(height):
        row_start = y * width * 3
        row = bgr[row_start : row_start + width * 3]
        padded.extend(row)
        padded.extend(b"\x00" * (row_stride - len(row)))

    file_header_size = 14
    info_header_size = 40
    pixel_offset = file_header_size + info_header_size
    file_size = pixel_offset + len(padded)

    with open(output_path, "wb") as file:
        file.write(b"BM")
        file.write(struct.pack("<IHHI", file_size, 0, 0, pixel_offset))
        file.write(
            struct.pack(
                "<IIIHHIIIIII",
                info_header_size,
                width,
                height,
                1,
                24,
                0,
                len(padded),
                0,
                0,
                0,
                0,
            )
        )
        file.write(padded)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    return bgr, width, height


def save_png(output_path: str, width: int, height: int, bgr: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    row_stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(bgr[y * row_stride : (y + 1) * row_stride])

    with open(output_path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n")
        file.write(
            chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
            )
        )
        file.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        file.write(chunk(b"IEND", b""))


def main() -> None:
    root = tk.Tk()
    calc = Calculator(root)

    for char in "12+7=":
        if char == "=":
            calc.calculate()
        else:
            calc.append(char)

    root.update_idletasks()
    root.update()
    time.sleep(0.4)

    bgr, width, height = capture_window_bmp("파이썬 계산기", "calculator_demo.bmp")
    save_png("calculator_demo.png", width, height, bgr)
    print("saved:calculator_demo.png")

    root.destroy()


if __name__ == "__main__":
    main()
