import struct
import unittest
from save_cipher import filename_checksum, save_filename


class SaveFilenameTests(unittest.TestCase):
    def test_preserves_slots(self):
        encrypted = bytes(range(32))
        for slot in (1, 2, 9, 10, 99):
            decoded = bytearray(0x180)
            struct.pack_into('<I', decoded, 0x178, slot)
            self.assertEqual(save_filename(encrypted, decoded),
                             f'STW000000{filename_checksum(encrypted):04x}{slot:02d}')

    def test_rejects_invalid_slot(self):
        for slot in (0, 100, 0xffffffff):
            decoded = bytearray(0x180)
            struct.pack_into('<I', decoded, 0x178, slot)
            with self.assertRaises(ValueError):
                save_filename(bytes(32), decoded)


if __name__ == '__main__':
    unittest.main()
