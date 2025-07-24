def convert_dicom_date(dicom_date: str) -> str:
    """Convert DICOM YYYYMMDD string to FHIR YYYY-MM-DD format."""
    if dicom_date and len(dicom_date) == 8:
        return f"{dicom_date[:4]}-{dicom_date[4:6]}-{dicom_date[6:]}"
    return None
