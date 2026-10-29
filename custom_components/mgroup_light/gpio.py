"""Read the legacy Raspberry Pi GPIO input registers without claiming a pin."""
import mmap
import os
import struct


def read_strompi2_signal() -> bool:
    """Read BCM21 via gpiomem; never export, drive, or reconfigure a GPIO."""
    descriptor = os.open('/dev/gpiomem', os.O_RDONLY | os.O_CLOEXEC)
    try:
        with mmap.mmap(descriptor, 4096, access=mmap.ACCESS_READ) as registers:
            function = (struct.unpack_from('<I', registers, 0x08)[0] >> 3) & 7
            if function != 0:
                raise OSError('GPIO 21 ist kein Eingang; der Pin wird nicht verändert')
            return bool(struct.unpack_from('<I', registers, 0x34)[0] & (1 << 21))
    finally:
        os.close(descriptor)
