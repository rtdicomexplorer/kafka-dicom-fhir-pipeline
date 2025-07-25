# dicom_sender.py
import os
import sys
from pydicom import dcmread
from pynetdicom import AE
from pynetdicom.presentation import StoragePresentationContexts
from dotenv import load_dotenv
load_dotenv(override=True)
STUDY_FOLDER =  "./study_folder/testdata" # r"C:\challenge_testdata\test"
DELAY_BETWEEN_GROUPS = 3  # seconds between studies

REMOTEAE_HOST= os.getenv("AEHOST", "localhost")
REMOTEAE_PORT=int(os.getenv("AEPORT", "11112"))


AE_TITLE = "MODALITY"

def send_dicom_file(filepath, host, port):
    ae = AE(ae_title=AE_TITLE)
    ae.requested_contexts = StoragePresentationContexts[:]

    assoc = ae.associate(host, port)

    if not assoc.is_established:
        print(f"❌ Association failed with {host}:{port}")
        return False

    try:
        ds = dcmread(filepath)
        sop_uid = getattr(ds, "SOPInstanceUID", "unknown")
        print(f"📤 Sending file: {os.path.basename(filepath)} (SOPInstanceUID={sop_uid})")
        status = assoc.send_c_store(ds)
        if status is None or status.Status!= 0x0000:
            print("❌ Failed to send file. Current status returned is {status.Status}")
        # elif status !=  0x0000:
        #     print(f"⚠️ Current staus returned is {status.Status}")        

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        
        assoc.release()
        return True

# If run directly from command line
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python dicom_sender.py /path/to/file.dcm")
    else:
        send_dicom_file(sys.argv[1])
