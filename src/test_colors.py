#!/usr/bin/env python3
"""
Simple test script to verify the blinking logic in DomainEntries
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import QTimer
from gui import DomainEntries

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Blinking Logic")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create DomainEntries with some test data
        test_domains = ["Ministry of Electronics and Information Technology", 
                       "Ministry of Power", 
                       "Ministry of Steel"]
        
        self.domain_entries = DomainEntries(test_domains)
        layout.addWidget(self.domain_entries)
        
        # Test buttons
        button_layout = QHBoxLayout()
        
        extract_btn = QPushButton("Start Extracting (First Item)")
        extract_btn.clicked.connect(self.test_extracting)
        
        complete_btn = QPushButton("Mark Complete (First Item)")
        complete_btn.clicked.connect(self.test_complete)
        
        no_files_btn = QPushButton("Mark No Files (Second Item)")
        no_files_btn.clicked.connect(self.test_no_files)
        
        error_btn = QPushButton("Mark Error (Third Item)")
        error_btn.clicked.connect(self.test_error)
        
        reset_btn = QPushButton("Reset All Colors")
        reset_btn.clicked.connect(self.test_reset)
        
        button_layout.addWidget(extract_btn)
        button_layout.addWidget(complete_btn)
        button_layout.addWidget(no_files_btn)
        button_layout.addWidget(error_btn)
        button_layout.addWidget(reset_btn)
        
        layout.addLayout(button_layout)
        
    def test_extracting(self):
        """Test extracting status (should blink)"""
        items = self.domain_entries.get_items()
        if items:
            print(f"Setting {items[0]} to extracting (should blink)")
            self.domain_entries.update_item_color(items[0], 'extracting')
    
    def test_complete(self):
        """Test completed status (should be green)"""
        items = self.domain_entries.get_items()
        if items:
            print(f"Setting {items[0]} to completed (should be green)")
            self.domain_entries.update_item_color(items[0], 'completed')
    
    def test_no_files(self):
        """Test no files status (should be blue)"""
        items = self.domain_entries.get_items()
        if len(items) > 1:
            print(f"Setting {items[1]} to no_files (should be blue)")
            self.domain_entries.update_item_color(items[1], 'no_files')
    
    def test_error(self):
        """Test error status (should be red)"""
        items = self.domain_entries.get_items()
        if len(items) > 2:
            print(f"Setting {items[2]} to error (should be red)")
            self.domain_entries.update_item_color(items[2], 'error')
    
    def test_reset(self):
        """Test reset all colors"""
        print("Resetting all colors (should stop blinking)")
        self.domain_entries.reset_all_colors()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("Color Test Window opened!")
    print("Use the buttons to test different status colors.")
    print("The 'Start Extracting' button should make the first item blink yellow.")
    
    sys.exit(app.exec())
