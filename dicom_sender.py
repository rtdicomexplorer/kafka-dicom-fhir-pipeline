# dicom_sender.py
import os
import sys
from pydicom import dcmread
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, MRImageStorage

REMOTE_HOST = "localhost"
REMOTE_PORT = 11112
AE_TITLE = "MODALITY"

def send_dicom_file(filepath):
    ae = AE(ae_title=AE_TITLE)
    ae.add_requested_context(CTImageStorage)
    ae.add_requested_context(MRImageStorage)

    assoc = ae.associate(REMOTE_HOST, REMOTE_PORT)

    if not assoc.is_established:
        print(f"❌ Could not associate with {REMOTE_HOST}:{REMOTE_PORT}")
        return

    try:
        ds = dcmread(filepath)
        sop_uid = getattr(ds, "SOPInstanceUID", "unknown")
        print(f"📤 Sending file: {os.path.basename(filepath)} (SOPInstanceUID={sop_uid})")
        status = assoc.send_c_store(ds)
        if status:
            print(f"✅ Sent - Status: 0x{status.Status:04x}")
        else:
            print("❌ Failed to send file.")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        assoc.release()

# If run directly from command line
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python dicom_sender.py /path/to/file.dcm")
    else:
        send_dicom_file(sys.argv[1])
