import struct
import sys

def convert_su_to_segy(input_file, output_file):
    print(f"Membaca {input_file} (Format SU)...")
    with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
        # 1. Tulis 3200-byte Text Header (Kosong / Spasi EBCDIC)
        f_out.write(b' ' * 3200) # Bisa ASCII spasi, banyak viewer modern mentoleransi ini
        
        # 2. Baca trace pertama untuk mendapatkan parameter
        trace_header = f_in.read(240)
        if not trace_header:
            print("File kosong!")
            return
            
        ns = struct.unpack('<h', trace_header[114:116])[0]
        dt = struct.unpack('<h', trace_header[116:118])[0]
        
        print(f"Terdeteksi ns={ns}, dt={dt} us")
        
        # 3. Buat 400-byte Binary Header
        bin_hdr = bytearray(400)
        struct.pack_into('>h', bin_hdr, 16, dt)    # dt pada byte 3217 (offset 16)
        struct.pack_into('>h', bin_hdr, 20, ns)    # ns pada byte 3221 (offset 20)
        struct.pack_into('>h', bin_hdr, 24, 5)     # Data Format (5 = IEEE Float)
        f_out.write(bin_hdr)

        # 4. Loop melalui semua trace dan ubah ke Big-Endian
        f_in.seek(0)
        trace_count = 0
        while True:
            hdr = f_in.read(240)
            if not hdr or len(hdr) < 240:
                break
                
            data = f_in.read(ns * 4)
            if len(data) < ns * 4:
                break
            
            # Ubah Trace Header ke Big-Endian: Unpack 120 (short) -> Pack 120 (>h)
            # Standar SEGY: hampir seluruh trace header berupa integer 2-byte atau 4-byte.
            # Agar simpel & aman, kita copy saja headernya secara utuh, namun update nilai ns & dt ke big-endian
            new_hdr = bytearray(hdr)
            
            # Perbaiki Endianness minimal untuk ns, dt, trace_num
            tracl = struct.unpack('<i', hdr[0:4])[0]
            struct.pack_into('>i', new_hdr, 0, tracl) # Trace sequence number
            struct.pack_into('>h', new_hdr, 114, ns)  # ns
            struct.pack_into('>h', new_hdr, 116, dt)  # dt
            
            f_out.write(new_hdr)
            
            # Ubah data dari Float Little-Endian (<f) ke Float Big-Endian (>f)
            floats = struct.unpack(f'<{ns}f', data)
            f_out.write(struct.pack(f'>{ns}f', *floats))
            
            trace_count += 1

        print(f"Selesai! {trace_count} trace berhasil dikonversi ke {output_file} (SEG-Y Standar)")

if __name__ == '__main__':
    # Pastikan file input SU Anda hasil dari docker yang valid (seperti perintah di atas)
    convert_su_to_segy('output/FFID_102.sgy', 'output/FFID_102_standard.sgy')
