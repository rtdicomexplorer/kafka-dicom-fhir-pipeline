# batch_send_by_study.py
# the main script 
import os
import time
from collections import defaultdict
from pydicom import dcmread
from dicom_sender import send_dicom_file  # Import function

STUDY_FOLDER = "./study_folder"
DELAY_BETWEEN_GROUPS = 3  # seconds between studies


def group_dicoms_by_study(folder):
    study_map = defaultdict(list)

    for root, _, files in os.walk(folder):
        for f in files:
            if not f.lower().endswith(".dcm"):
                continue
            filepath = os.path.join(root, f)
            try:
                ds = dcmread(filepath, stop_before_pixels=True)
                study_uid = getattr(ds, "StudyInstanceUID", None)
                if study_uid:
                    study_map[study_uid].append(filepath)
            except Exception as e:
                print(f"⚠️ Could not read {f}: {e}")
    return study_map


def main():
    study_groups = group_dicoms_by_study(STUDY_FOLDER)
    print(f"📦 Found {len(study_groups)} unique studies.")

    for study_uid, files in study_groups.items():
        print(f"\n🧪 Sending Study UID: {study_uid} ({len(files)} files)")
        for f in files:
            send_dicom_file(f)
        print(f"✅ Finished sending study: {study_uid}")
        time.sleep(DELAY_BETWEEN_GROUPS)

if __name__ == "__main__":
    main()
