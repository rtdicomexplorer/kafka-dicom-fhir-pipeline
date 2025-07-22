import os
from pydicom import dcmread
from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import CTImageStorage, MRImageStorage

# Optional: Enable verbose DICOM logs
# debug_logger()

# Configuration
DICOM_FOLDER = "./study_folder"  # folder containing .dcm files
REMOTE_HOST = "localhost"
REMOTE_PORT = 11112
AE_TITLE = "MODALITY"






# Create Application Entity
ae = AE(ae_title=AE_TITLE)

# Add supported presentation contexts
ae.add_requested_context(CTImageStorage)
ae.add_requested_context(MRImageStorage)

# Establish association with receiver
assoc = ae.associate(REMOTE_HOST, REMOTE_PORT)

if assoc.is_established:
    print(f"📡 Association established with {REMOTE_HOST}:{REMOTE_PORT}")

    # Loop through all DICOM files in the folder
    for filename in os.listdir(DICOM_FOLDER):
        if filename.lower().endswith(".dcm"):
            filepath = os.path.join(DICOM_FOLDER, filename)
            try:
                ds = dcmread(filepath)

                print(f"📤 Sending file: {filename} (SOPInstanceUID={ds.SOPInstanceUID})")
                status = assoc.send_c_store(ds)

                if status:
                    print(f"✅ Sent: {filename} - Status: 0x{status.Status:04x}")
                else:
                    print(f"❌ Failed to send: {filename}")

            except Exception as e:
                print(f"⚠️ Error reading or sending file {filename}: {e}")

    assoc.release()
    print("🔌 Association released.")
else:
    print("❌ Could not establish association.")
