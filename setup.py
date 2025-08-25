#!/usr/bin/env python3
"""
ProfAI Production Setup Script
Sets up the production environment and copies sample data
"""

import os
import shutil
from pathlib import Path

def setup_production_environment():
    """Set up the production environment"""
    print("🔧 Setting up ProfAI Production Environment...")
    
    # Get paths
    current_dir = Path(__file__).parent
    old_project_dir = current_dir.parent / "ProfessorAI_GPT_with_sarvam_multilingual"
    
    # Copy sample PDFs if they exist
    old_docs_dir = old_project_dir / "documents"
    new_docs_dir = current_dir / "data" / "documents"
    
    if old_docs_dir.exists():
        print("📄 Copying sample PDF documents...")
        for pdf_file in old_docs_dir.glob("*.pdf"):
            try:
                shutil.copy2(pdf_file, new_docs_dir)
                print(f"   ✅ Copied: {pdf_file.name}")
            except Exception as e:
                print(f"   ❌ Failed to copy {pdf_file.name}: {e}")
    else:
        print("📄 No sample documents found to copy")
    
    # Copy existing vector database if it exists
    old_chroma_dir = old_project_dir / "chroma_db_english"
    new_chroma_dir = current_dir / "data" / "vectorstore"
    
    if old_chroma_dir.exists():
        print("🗄️ Copying existing vector database...")
        try:
            # Copy the entire chroma database
            if new_chroma_dir.exists():
                shutil.rmtree(new_chroma_dir)
            shutil.copytree(old_chroma_dir, new_chroma_dir)
            print("   ✅ Vector database copied successfully")
        except Exception as e:
            print(f"   ❌ Failed to copy vector database: {e}")
    else:
        print("🗄️ No existing vector database found")
    
    # Copy existing courses if they exist
    old_storage_dir = old_project_dir / "src" / "storage"
    new_courses_dir = current_dir / "data" / "courses"
    
    if old_storage_dir.exists():
        print("📚 Copying existing course data...")
        for course_file in old_storage_dir.glob("*.json"):
            try:
                shutil.copy2(course_file, new_courses_dir)
                print(f"   ✅ Copied: {course_file.name}")
            except Exception as e:
                print(f"   ❌ Failed to copy {course_file.name}: {e}")
    else:
        print("📚 No existing course data found")
    
    print("\n✨ Setup complete!")
    print("📋 Next steps:")
    print("   1. Copy .env.example to .env and add your API keys")
    print("   2. Install dependencies: pip install -r requirements.txt")
    print("   3. Run the server: python run_server.py")
    print("   4. Access the application at: http://127.0.0.1:5001")

if __name__ == "__main__":
    setup_production_environment()