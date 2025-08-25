#!/usr/bin/env python3
"""
Script to copy web files from the old structure to the new structure
"""

import shutil
import os

# Source and destination paths
source_dir = "../ProfessorAI_GPT_with_sarvam_multilingual/static"
dest_dir = "web"

# Files to copy
files_to_copy = [
    "index.html",
    "upload.html", 
    "courses.html",
    "course.html"
]

# Create destination directory if it doesn't exist
os.makedirs(dest_dir, exist_ok=True)

# Copy each file
for filename in files_to_copy:
    source_path = os.path.join(source_dir, filename)
    dest_path = os.path.join(dest_dir, filename)
    
    if os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)
        print(f"✅ Copied {filename}")
    else:
        print(f"❌ Source file not found: {filename}")

print("Web files copy completed!")