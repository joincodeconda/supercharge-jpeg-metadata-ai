# Import necessary libraries
import os
import shutil
import sys
import requests
import piexif
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QProgressBar, QLabel, QFileDialog, QTextEdit
from PyQt5.QtCore import Qt

# Your API token for accessing the PhotoTag.ai service
api_token = "" # Replace with your API token

def fetch_existing_metadata(image_path):
    # Try to load and read the existing metadata from an image
    try:
        exif_data = piexif.load(image_path)  # Load the EXIF data of the image
        existing_title = ""
        existing_description = ""

        # Check and process the XPTitle from the EXIF data if it exists
        if piexif.ImageIFD.XPTitle in exif_data["0th"]:
            xp_title_tuple = exif_data["0th"][piexif.ImageIFD.XPTitle]
            xp_title_bytes = bytes(xp_title_tuple)  # Convert the tuple to bytes
            existing_title = xp_title_bytes.decode('utf-16le', errors='ignore').rstrip('\x00')  # Decode bytes to string

        # Check and process the ImageDescription from the EXIF data if it exists
        if piexif.ImageIFD.ImageDescription in exif_data["0th"]:
            image_description_bytes = exif_data["0th"][piexif.ImageIFD.ImageDescription]
            existing_description = image_description_bytes.decode('utf-8', errors='ignore').strip()  # Decode bytes to string

        # Print existing metadata for debugging
        print(f"Existing metadata read for image: {image_path} - Title: {existing_title}, Description: {existing_description}")
        return existing_title, existing_description
    except Exception as e:
        # If any error occurs, print the error message
        print(f"Error reading existing metadata: {str(e)}")
        return '', ''

def get_image_metadata(image_path):
    # Fetch existing metadata to use as context for the API request
    existing_title, existing_description = fetch_existing_metadata(image_path)
    custom_context = f"{existing_title} {existing_description}".strip()

    # Define the API request details
    url = "https://server.phototag.ai/api/keywords"
    headers = {"Authorization": f"Bearer {api_token}"}
    payload = {
        "language": "en",
        "maxKeywords": 40,
        "customContext": custom_context
    }

    # Make the API request with the image and context
    with open(image_path, 'rb') as img_file:
        files = {"file": img_file}
        response = requests.post(url, headers=headers, data=payload, files=files)

    # Process the API response
    if response.status_code == 200:
        data = response.json().get("data")
        if data:
            # Extract and print the fetched metadata
            title = data.get("title", "")
            description = data.get("description", "")
            keywords = data.get("keywords", [])
            print(f"Metadata fetched for image: {image_path}")
            print(f"Title: {title}")
            print(f"Description: {description}")
            print(f"Keywords: {keywords}")
            return title, description, keywords
    else:
        # Print error message if the API call fails
        print(f"Failed to fetch metadata. Check your API token. Status code: {response.status_code}")
    return None, None, []

def write_metadata_to_image(image_path, title, description, keywords):
    # Attempt to write the fetched metadata back into the image's EXIF data
    try:
        exif_dict = piexif.load(image_path)  # Load existing EXIF data
        # Prepare the metadata for insertion
        keywords_str = ', '.join(keywords)
        title_bytes = title.encode('utf-16le')
        description_bytes = description.encode('utf-8')
        keywords_bytes = keywords_str.encode('utf-16le')
        # Update the EXIF data with the new metadata
        exif_dict['0th'][piexif.ImageIFD.ImageDescription] = description_bytes
        exif_dict['0th'][piexif.ImageIFD.XPTitle] = title_bytes
        exif_dict['0th'][piexif.ImageIFD.XPKeywords] = keywords_bytes
        # Save the updated EXIF data back to the image
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        print(f"Metadata successfully written to the image: {image_path}")
        return True
    except Exception as e:
        # Print error message if writing metadata fails
        print(f"Failed to write metadata to the image: {str(e)}")
        return False

# GUI Application to process a folder of images
class ImageKeywordingTool(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Set up the application window
        self.setWindowTitle('Image Keywording Tool')
        self.resize(600, 400)
        layout = QVBoxLayout()

        # Status message box
        self.status_message = QTextEdit()
        self.status_message.setPlainText("Processing Not Started")
        self.status_message.setReadOnly(True)

        # Button to select the folder for processing
        self.select_folder_button = QPushButton('Select Folder')
        self.select_folder_button.clicked.connect(self.start_processing)

        # Progress bar to indicate processing progress
        self.progress_bar = QProgressBar()

        # Arrange the components in the application window
        layout.addWidget(self.status_message)
        layout.addWidget(self.select_folder_button)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def start_processing(self):
        # Handler for the 'Select Folder' button click
        selected_folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if selected_folder:
            self.status_message.setPlainText("Processing Running...")
            self.process_images_in_folder(selected_folder)
            self.status_message.append("Processing Completed")
            self.status_message.append("Close Window to Exit")

    def process_images_in_folder(self, folder_path):
        # Create 'ready' and 'failed' subfolders for processed images
        ready_folder = os.path.join(folder_path, "ready")
        failed_folder = os.path.join(folder_path, "failed")
        os.makedirs(ready_folder, exist_ok=True)
        os.makedirs(failed_folder, exist_ok=True)

        # Find all JPEG images in the selected folder
        images_to_process = [filename for filename in os.listdir(folder_path) if filename.lower().endswith(('.jpg', '.jpeg'))]
        total_images = len(images_to_process)
        processed_images = 0

        # Process each image in the folder
        for filename in images_to_process:
            image_path = os.path.join(folder_path, filename)
            # Fetch and update metadata for each image
            title, description, keywords = get_image_metadata(image_path)
            if title and keywords:
                success = write_metadata_to_image(image_path, title, description, keywords)
                # Move processed images to 'ready' or 'failed' folder
                if success:
                    shutil.move(image_path, os.path.join(ready_folder, filename))
                else:
                    shutil.move(image_path, os.path.join(failed_folder, filename))
            else:
                shutil.move(image_path, os.path.join(failed_folder, filename))

            # Update progress bar
            processed_images += 1
            progress = processed_images / total_images * 100
            self.progress_bar.setValue(int(round(progress)))
            QApplication.processEvents()  # Keep the GUI responsive

# Main function to run the application
def main():
    app = QApplication(sys.argv)
    ex = ImageKeywordingTool()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
