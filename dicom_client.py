# dicom_client.py
from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import CTImageStorage
import os

# Optional: turn on debug logs
# debug_logger()

# Path to your DICOM file
DICOM_PATH = "sample_ct.dcm"

# Set up the application entity (modality)
ae = AE()
ae.add_requested_context(CTImageStorage)

# Define the PACS/server address and port (you'll simulate this next)
assoc = ae.associate('localhost', 11112)

if assoc.is_established:
    print("✅ Step 0: Association established with server")
    # Send the DICOM file
    from pydicom import dcmread
    ds = dcmread(DICOM_PATH)

    status = assoc.send_c_store(ds)
    print(f"📤 Step 1: Sending DICOM file {DICOM_PATH} via C-STORE...")
    if status:
        print(f"✅ Step 2: C-STORE request sent. Status: 0x{status.Status:04x}")
    else:
        print("❌ Step 2: Failed to send DICOM file")
    assoc.release()
    print("🔌 Step 3: Association released")
else:
    print("❌ Association rejected or aborted")
