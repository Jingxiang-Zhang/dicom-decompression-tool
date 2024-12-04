import argparse
import logging
import os
import warnings

import pydicom
import SimpleITK as sitk
from pydicom.uid import ExplicitVRLittleEndian

warnings.filterwarnings(
    "ignore",
    message="End of file reached before delimiter",
    category=UserWarning
)


# Reference: https://www.dicomlibrary.com/dicom/transfer-syntax/
compressed_uids = [
    # JPEG compression
    "1.2.840.10008.1.2.4.50",  # JPEG Baseline (Process 1)
    "1.2.840.10008.1.2.4.51",  # JPEG Baseline (Processes 2 & 4)
    "1.2.840.10008.1.2.4.52",  # JPEG Extended (Processes 3 & 5) (Retired)
    "1.2.840.10008.1.2.4.53",  # JPEG Spectral Selection, Nonhierarchical (Processes 6 & 8) (Retired)
    "1.2.840.10008.1.2.4.54",  # JPEG Spectral Selection, Nonhierarchical (Processes 7 & 9) (Retired)
    "1.2.840.10008.1.2.4.55",  # JPEG Full Progression, Nonhierarchical (Processes 10 & 12) (Retired)
    "1.2.840.10008.1.2.4.56",  # JPEG Full Progression, Nonhierarchical (Processes 11 & 13) (Retired)
    "1.2.840.10008.1.2.4.57",  # JPEG Lossless, Nonhierarchical (Processes 14)
    "1.2.840.10008.1.2.4.58",  # JPEG Lossless, Nonhierarchical (Processes 15) (Retired)
    "1.2.840.10008.1.2.4.59",  # JPEG Extended, Hierarchical (Processes 16 & 18) (Retired)
    "1.2.840.10008.1.2.4.60",  # JPEG Extended, Hierarchical (Processes 17 & 19) (Retired)
    "1.2.840.10008.1.2.4.61",  # JPEG Spectral Selection, Hierarchical (Processes 20 & 22) (Retired)
    "1.2.840.10008.1.2.4.62",  # JPEG Spectral Selection, Hierarchical (Processes 21 & 23) (Retired)
    "1.2.840.10008.1.2.4.63",  # JPEG Full Progression, Hierarchical (Processes 24 & 26) (Retired)
    "1.2.840.10008.1.2.4.64",  # JPEG Full Progression, Hierarchical (Processes 25 & 27) (Retired)
    "1.2.840.10008.1.2.4.65",  # JPEG Lossless, Nonhierarchical (Process 28) (Retired)
    "1.2.840.10008.1.2.4.66",  # JPEG Lossless, Nonhierarchical (Process 29) (Retired)
    "1.2.840.10008.1.2.4.70",  # JPEG Lossless, Nonhierarchical, First-Order Prediction

    # JPEG-LS compression
    "1.2.840.10008.1.2.4.80",  # JPEG-LS Lossless Image Compression
    "1.2.840.10008.1.2.4.81",  # JPEG-LS Lossy (Near-Lossless) Image Compression

    # JPEG 2000 compression
    "1.2.840.10008.1.2.4.90",  # JPEG 2000 Image Compression (Lossless Only)
    "1.2.840.10008.1.2.4.91",  # JPEG 2000 Image Compression
    "1.2.840.10008.1.2.4.92",  # JPEG 2000 Part 2 Multicomponent Image Compression (Lossless Only)
    "1.2.840.10008.1.2.4.93",  # JPEG 2000 Part 2 Multicomponent Image Compression

    # JPIP
    "1.2.840.10008.1.2.4.94",  # JPIP Referenced
    "1.2.840.10008.1.2.4.95",  # JPIP Referenced Deflate

    # RLE compression
    "1.2.840.10008.1.2.5",     # RLE Lossless

    # MPEG compression
    "1.2.840.10008.1.2.4.100", # MPEG2 Main Profile Main Level
    "1.2.840.10008.1.2.4.102", # MPEG-4 AVC/H.264 High Profile / Level 4.1
    "1.2.840.10008.1.2.4.103", # MPEG-4 AVC/H.264 BD-compatible High Profile / Level 4.1

    # High-Throughput JPEG 2000
    "1.2.840.10008.1.2.4.201", # High-Throughput JPEG 2000 Image Compression (Lossless Only)
    "1.2.840.10008.1.2.4.202", # High-Throughput JPEG 2000 with RPCL Options Image Compression (Lossless Only)
    "1.2.840.10008.1.2.4.203"  # High-Throughput JPEG 2000 Image Compression
]

def setup_logger(verbose):
    """
    Configure logging level based on verbosity.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=log_level
    )


def is_compressed(file_path):
    """
    Check if the DICOM file is in a compressed format.
    """
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        return transfer_syntax in compressed_uids
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return False


def decompress_and_save_with_metadata(file_path, output_path, reference_metadata=None):
    """
    Decompress a DICOM file, ensure proper metadata for series consistency, 
    and save to the specified output path.
    """
    try:
        ds = pydicom.dcmread(file_path)
        image_array = sitk.GetArrayFromImage(sitk.ReadImage(file_path))
        ds.PixelData = image_array.tobytes()

        if image_array.dtype in ['uint16', 'int16']:
            ds[(0x7FE0, 0x0010)].VR = 'OW'
        else:
            ds[(0x7FE0, 0x0010)].VR = 'OB'

        if reference_metadata:
            ds.SeriesInstanceUID = reference_metadata.SeriesInstanceUID
            ds.StudyInstanceUID = reference_metadata.StudyInstanceUID
            ds.SeriesNumber = reference_metadata.SeriesNumber
            ds.ImageOrientationPatient = reference_metadata.ImageOrientationPatient
            ds.ImagePositionPatient = reference_metadata.ImagePositionPatient
        else:
            reference_metadata = ds

        if 'InstanceNumber' in ds:
            ds.InstanceNumber = int(ds.InstanceNumber)
        else:
            ds.InstanceNumber = 1

        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.save_as(output_path)
        logging.debug(f"Decompressed and saved file: {output_path}")

        return reference_metadata
    except Exception as e:
        logging.error(f"Failed to decompress file {file_path}: {e}")
        return None


def process_dicom_directory(input_dir, output_dir=None):
    """
    Iterate through all files in a directory, check for compression,
    and decompress files if necessary.
    """
    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.lower().endswith(".dcm"):
                if is_compressed(file_path):
                    logging.debug(f"Compressed file found: {file_path}")
                    
                    if output_dir:
                        relative_path = os.path.relpath(file_path, input_dir)
                        output_file_path = os.path.join(output_dir, relative_path)
                        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                    else:
                        output_file_path = file_path
                    
                    decompress_and_save_with_metadata(file_path, output_file_path)
                else:
                    logging.debug(f"File is already uncompressed: {file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decompress DICOM files in a directory.")
    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        required=True,
        help="Path of the DICOM folder",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default=None,
        help="Path to the output folder. If not provided, the output will overwrite the original file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output for debugging",
    )

    args = parser.parse_args()
    setup_logger(args.verbose)

    input_dir = args.input_dir
    output_dir = args.output_dir

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    process_dicom_directory(input_dir, output_dir)