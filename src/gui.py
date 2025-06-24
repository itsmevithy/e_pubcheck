from threading import Thread
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, Signal, QObject
import sys
import asyncio
import extraction as egz
import io
import os

ministries_list = []
user_domains = []
user_keywords = []

# Custom stream to capture print statements
class LogStream(io.StringIO):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def write(self, text):
        if text.strip():  # Only emit non-empty messages
            self.log_signal.emit(text.strip())
        return len(text)
    
    def flush(self):
        pass

# Signal emitter for thread-safe logging
class LogSignalEmitter(QObject):
    log_message = Signal(str)

# Global log signal emitter
log_emitter = LogSignalEmitter()

class LogWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title label
        title = QLabel("Logs")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Log display area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid #555;
            }
        """)
        
        # Clear button
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        
        layout.addWidget(title)
        layout.addWidget(self.log_display)
        layout.addWidget(clear_btn)
        self.setLayout(layout)
        
        # Connect to log signal
        from datetime import datetime
        self.today = datetime.now()
        log_emitter.log_message.connect(self.add_log_message)
        self.file_path = f"../files/logs/log{self.today.strftime('%Y%m%d')}.txt"
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.log_f = open(self.file_path, "a+")
        
    def add_log_message(self, message):
        """Add a log message to the display"""
        timestamp = self.today.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_display.append(formatted_message)
        self.log_f.write(formatted_message + "\n")
        
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Limit log entries to prevent memory issues (keep last 1000 lines)
        if self.log_display.document().blockCount() > 1000:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def clear_logs(self):
        """Clear all log messages"""
        self.log_display.clear()

class DomainEntries(QScrollArea):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items_list = items.copy()  # Keep track of items
        self._refresh_display()
        self.content.setLayout(self.layout)
        self.setWidget(self.content)
    
    def _create_item_row(self, item_text):
        """Create a row with item text and delete button"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        
        # Item label
        label = QLabel(item_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("padding: 5px;")
        
        # Delete button
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(25, 25)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        delete_btn.clicked.connect(lambda: self._delete_item(item_text))
        
        row_layout.addWidget(label)
        row_layout.addWidget(delete_btn)
        row_layout.setStretch(0, 1)  # Label takes most space
        
        return row_widget
    
    def _delete_item(self, item_text):
        """Remove item from list and refresh display"""
        if item_text in self.items_list:
            self.items_list.remove(item_text)
            self._refresh_display()
    
    def _refresh_display(self):
        """Clear and rebuild the display"""
        # Clear existing widgets
        for i in reversed(range(self.layout.count())):
            child = self.layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Add items with delete buttons
        for item in self.items_list:
            row_widget = self._create_item_row(item)
            self.layout.addWidget(row_widget)
        
    
    def get_items(self):
        """Return current list of items"""
        return self.items_list.copy()
    
    def add_item(self, item_text):
        """Add new item to the list"""
        if item_text and item_text not in self.items_list:
            self.items_list.append(item_text)
            self._refresh_display()
            return True
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        return False
    
    def refresh(self, items):
        """Update the entire list with new items"""
        self.items_list = items.copy()
        self._refresh_display()

class KeywordEntries(QScrollArea):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Store items as [text, boolean] pairs
        self.items_list = items
        self._refresh_display()
        self.content.setLayout(self.layout)
        self.setWidget(self.content)
    
    def _create_item_row(self, item_data):
        """Create a row with checkbox, item text and delete button"""
        item_text, is_checked = item_data
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        
        # Checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(is_checked)
        checkbox.setFixedSize(20, 20)
        checkbox.toggled.connect(lambda checked: self._toggle_item(item_text, checked))
        
        # Item label
        label = QLabel(item_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("padding: 5px;")
        
        # Delete button
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(25, 25)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        delete_btn.clicked.connect(lambda: self._delete_item(item_text))
        
        row_layout.addWidget(checkbox)
        row_layout.addWidget(label)
        row_layout.addWidget(delete_btn)
        row_layout.setStretch(1, 1)  # Label takes most space
        
        return row_widget
    
    def _toggle_item(self, item_text, checked):
        """Update the toggle state of an item"""
        for i, (text, _) in enumerate(self.items_list):
            if text == item_text:
                self.items_list[i][1] = checked
                break
    
    def _delete_item(self, item_text):
        """Remove item from list and refresh display"""
        self.items_list = [item for item in self.items_list if item[0] != item_text]
        self._refresh_display()
    
    def _refresh_display(self):
        """Clear and rebuild the display"""
        # Clear existing widgets
        for i in reversed(range(self.layout.count())):
            child = self.layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Add items with checkboxes and delete buttons
        for item_data in self.items_list:
            row_widget = self._create_item_row(item_data)
            self.layout.addWidget(row_widget)
    
    def get_items(self):
        """Return current list of items as [text, boolean] pairs"""
        return [item.copy() for item in self.items_list]
    
    def add_item(self, item_text, checked=False):
        """Add new item to the list with optional checked state"""
        if item_text and not any(text == item_text for text, _ in self.items_list):
            self.items_list.append([item_text, checked])
            self._refresh_display()
            return True
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        return False
    
    def refresh(self, items):
        """Update the entire list with new items (as simple strings, defaulting to unchecked)"""
        self.items_list = [[item, False] for item in items] if items else []
        self._refresh_display()

class ColumnSection(QWidget):
    def submit_action(self, content, items):
        if self.mode == "domains" and content not in ministries_list:
            QMessageBox.warning(self, "Warning", "Please select a valid ministry.")
            return
        if content != "":
            if self.mode == "keywords":
                # For keywords, add to KeywordEntries
                if self.frame.add_item(content):
                    self.combo.clear()
            else:
                # For domains, add to DomainEntries if not already in list
                if content not in [item for item in self.frame.get_items()]:
                    items.append(content)
                    self.frame.add_item(content)
    def __init__(self, label_text, frame_items, items=None):
        super().__init__()
        self.layout = QVBoxLayout()
        self.label = QLabel(label_text)
        self.label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.button = QPushButton("Add")
        if items is None:
            self.mode="keywords"
            self.combo = QLineEdit()
            self.combo.setPlaceholderText("Enter Keywords")
            self.combo.returnPressed.connect(lambda: self.submit_action(self.combo.text(), frame_items))
            self.button.clicked.connect(lambda: self.submit_action(self.combo.text(), frame_items))
            self.frame = KeywordEntries(frame_items)
        else:
            self.mode="domains"
            self.combo = QComboBox()
            self.combo.setEditable(True)
            self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.combo.addItems(["Select Ministry"] + items)
            self.combo.lineEdit().returnPressed.connect(lambda: self.submit_action(self.combo.currentText(), frame_items))
            self.button.clicked.connect(lambda: self.submit_action(self.combo.currentText(), frame_items))
            self.frame = DomainEntries(frame_items)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.combo)
        self.layout.addWidget(self.button)
        self.layout.addWidget(self.frame)
        self.setLayout(self.layout)

def start_action():
    """Handle start/cancel button clicks"""
    
    # Check if we're in cancel mode
    if window.start_button.text() == "Cancel":
        print("Extraction cancelled by user")
        egz.eve_sig.clear()  # Clear extraction signal
        # Stop any running timers (if they exist)
        if hasattr(window, '_status_timer') and window._status_timer.isActive():
            window._status_timer.stop()
        if hasattr(window, '_progress_popup') and window._progress_popup.isVisible():
            window._progress_popup.close()
        
        window.start_button.setText("Start")  # Reset button text
        window.start_button.setEnabled(True)
        return  # ✅ Exit early for cancel
    
    # Start extraction process
    window.start_button.setText("Cancel")
    print("Start button clicked - setting extraction signal")
    
    # Create progress popup
    progress_popup = QMessageBox(window)
    progress_popup.setText("Extraction in progress, please wait...")
    progress_popup.setStandardButtons(QMessageBox.StandardButton.Cancel)
    progress_popup.show()
    
    # Store references for cleanup
    window._progress_popup = progress_popup
    
    # Handle Cancel button click on popup
    def handle_popup_cancel():
        if progress_popup.clickedButton() == progress_popup.button(QMessageBox.StandardButton.Cancel):
            print("User cancelled extraction via popup")
            egz.eve_sig.clear()
            if hasattr(window, '_status_timer'):
                window._status_timer.stop()
            progress_popup.close()
            window.start_button.setText("Start")
            window.start_button.setEnabled(True)
    
    progress_popup.buttonClicked.connect(handle_popup_cancel)
    
    # Set extraction signal
    egz.eve_sig.set()
    egz.timeout_event.clear()
    egz.empty_domains.clear()
    
    print("Extraction signal set, starting extraction...")
    
    # Create timer to check extraction status non-blocking
    status_timer = QTimer(window)
    status_timer.timeout.connect(lambda: check_extraction_status(progress_popup, status_timer))
    status_timer.start(100)  # Check every 100ms
    
    # Store timer reference for cleanup
    window._status_timer = status_timer

def check_extraction_status(progress_popup, status_timer):
    """Non-blocking status checker for extraction progress"""
    
    # Helper function to cleanup timers and close progress popup
    def cleanup_and_close():
        status_timer.stop()
        if progress_popup and progress_popup.isVisible():
            progress_popup.close()
        # Clean up stored references
        if hasattr(window, '_status_timer'):
            delattr(window, '_status_timer')
        if hasattr(window, '_progress_popup'):
            delattr(window, '_progress_popup')
    
    # Check for timeout
    if egz.timeout_event.is_set():
        cleanup_and_close()
        
        error_popup = QMessageBox(window)
        error_popup.setText("Timeout occurred! Please try again.")
        error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("Timeout occurred during extraction!")
        error_popup.show()
        
        # Auto-close error popup after 3 seconds
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(error_popup, auto_close_timer))
        auto_close_timer.start(3000)
        return
    
    # Check for empty domains
    if egz.empty_domains.is_set():
        cleanup_and_close()
        egz.empty_domains.clear()
        
        error_popup = QMessageBox(window)
        error_popup.setText("No domains selected! Please select at least one domain.")
        error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("No domains selected during extraction!")
        error_popup.show()
        
        # Auto-close error popup after 3 seconds
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(error_popup, auto_close_timer))
        auto_close_timer.start(3000)
        return
    
    # Check if extraction is complete
    if not egz.eve_sig.is_set():
        cleanup_and_close()
        
        success_popup = QMessageBox(window)
        success_popup.setText(f"Extraction completed!\nTotal {egz.dwnld_count} files downloaded.\nFiles saved in ../files/ directory")
        success_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("Extraction completed!")
        success_popup.show()
        
        # Auto-close success popup after 5 seconds
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(success_popup, auto_close_timer))
        auto_close_timer.start(5000)

def close_popup_and_enable(popup, timer):
    """Helper function to close popup and re-enable start button"""
    timer.stop()
    popup.close()
    window.start_button.setText("Start")  # Reset button text
    window.start_button.setEnabled(True)
class HomePage(QWidget):
    def log_toggle(self):
        text = ["Show Logs", "Hide Logs"]
        self.log_tog.setText(text[self.log_tog.isChecked()])
        self.log_window.setVisible(self.log_tog.isChecked())

    def __init__(self, Domains, Ministries, Keywords):
        super().__init__()
        self.setWindowTitle("Homepage")
        self.setGeometry(100, 100, 1400, 600)  # Increased width for log window
        
        # Create two column sections side by side
        global ministries_list
        ministries_list = Ministries
        self.section1 = ColumnSection("Domains", items=Ministries, frame_items=Domains)
        self.section2 = ColumnSection("Keywords", frame_items=Keywords)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(start_action)
        
        # Create log window
        self.log_window = LogWindow()
        self.log_window.setVisible(False)  # Initially hidden
        
        # Main layout - horizontal split between controls and logs
        main_layout = QHBoxLayout()
        
        # Left side - controls
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        
        # Row for domains and keywords
        row_wrapper = QHBoxLayout()
        row_wrapper.addWidget(self.section1)
        row_wrapper.addWidget(self.section2)
        
        self.log_tog = QPushButton("Show Logs")
        self.log_tog.setCheckable(True)
        self.log_tog.clicked.connect(self.log_toggle)
        
        row_buttons = QHBoxLayout()
        row_buttons.addWidget(self.start_button)
        row_buttons.addWidget(self.log_tog)

        controls_layout.addLayout(row_wrapper)
        controls_layout.addLayout(row_buttons)
        
        # Add controls and log window to main layout
        main_layout.addWidget(controls_widget, 2)  # Controls take 2/3 of space
        main_layout.addWidget(self.log_window, 1)   # Log window takes 1/3 of space
        
        self.setLayout(main_layout)
    def closeEvent(self, event):
        """Handle window close event to ensure proper cleanup"""
        print("Closing application...")
        self.log_window.log_f.close()


if __name__ == "__main__": # Signal when browser is initialized
    
    # Set up print capture for real-time logging
    log_stream = LogStream(log_emitter.log_message)
    
    def setup_logging():
        """Redirect stdout to capture print statements"""
        sys.stdout = log_stream
    
    def restore_logging():
        """Restore original stdout"""
        sys.stdout = sys.__stdout__
    
    async def extraction_worker():
        """Background thread that handles browser and extraction"""
        try:
            page = await egz.egz_extract_defaults()
            while True:
                if egz.eve_sig.is_set():
                    print("Processing extraction request...")
                    try:
                        # Get domain names and convert to codes
                        domain_names = window.section1.frame.get_items()
                        keyword_data = window.section2.frame.get_items()  # Returns [[text, boolean], ...]
                        
                        # Convert domain_names to domain_codes
                        domain_codes = []
                        for domain_name in domain_names:
                            for code, name in egz.valdict.items():
                                if name == domain_name:
                                    domain_codes.append(code)
                                    break
                        
                        # keyword_data is already in the format [[text, boolean], ...]
                        keywords = keyword_data
                        
                        print(f"Domain codes: {domain_codes}")
                        print(f"Keywords: {keywords}")
                        #if domain_codes and keywords:
                        #    print("Starting extraction...")
                        if(await egz.extract_mids(page, domain_names, keyword_data) < 0):
                            continue
                        
                        # Check if extraction was cancelled before proceeding
                        if not egz.eve_sig.is_set():
                            print("Extraction was cancelled, stopping...")
                            break
                            
                        print("Extraction completed successfully!\nNow downloading files...")
                        egz.egz_download()
                        egz.ais_download()
                            
                        egz.eve_sig.clear()  # Clear signal after extraction
                        '''
                        elif not domain_codes:
                            popup = QMessageBox()
                            popup.setText("No domains selected! Please select at least one domain.")
                            popup.exec()
                        else:
                            print("No domains or keywords selected!")
                         '''   
                    except Exception as e:
                        print(f"Error during extraction: {e}")
                    finally:
                        egz.eve_sig.clear()
                
                await asyncio.sleep(1)  # Check every second        
        except KeyboardInterrupt:
            print("Extraction worker interrupted by user")

        except Exception as e:
            print(f"Browser initialization error: {e}")
            egz.browser_ready.set()  # Set even on error to prevent hanging

    def run_async_worker():
        """Wrapper to run async worker in its own event loop"""
        asyncio.run(extraction_worker())
    
    try:
        app = None
        # Create Qt application first
        print("Creating Qt application...")
        app = QApplication(sys.argv)
        
        # Set up logging capture
        setup_logging()
        
        # Set up cross-module logging for extraction.py
        egz.set_log_emitter(log_emitter)
        
        # Start extraction worker in background with proper async handling
        extraction_thread = Thread(target=run_async_worker, daemon=True)
        extraction_thread.start()
        
        print("Initializing browser in background...")
        # Create window immediately, it will update when browser is ready
        window = HomePage([], [], Keywords=[])  # Start with empty lists
        window.start_button.setEnabled(False)  # Disable start button until browser is ready
        window.show()
          # Check browser readiness with timer (non-blocking)
        def check_browser_ready():
            global window
            if egz.browser_ready.is_set():
                print("Browser initialization completed!")
                
                # Update ministries and keywords now that browser is ready
                ministries_list = list(egz.valdict.values())
                print(f"Found {len(ministries_list)} ministries")
                print(f"Keywords: {[i[0] for i in egz.kwList]}")
                
                if ministries_list:
                    # Update the window with real data
                    new_window = HomePage([egz.valdict[i] for i in egz.mList_input], ministries_list, Keywords=[i for i in egz.kwList])
                    new_window.show()
                    window.close()  # Close the temporary window
                    window = new_window
                else:
                    print("WARNING: No ministries found! Browser may not be fully initialized.")
                
                browser_timer.stop()
            else:
                print("Still initializing browser...")
        
        # Timer to check browser readiness every second
        browser_timer = QTimer()
        browser_timer.timeout.connect(check_browser_ready)
        browser_timer.start(1000)  # Check every second
        
        print("Starting Qt event loop...")
        # Run Qt application (this blocks until app closes)
        sys.exit(app.exec())

    except KeyboardInterrupt:
        print("Interrupt received from user")
        if app:
            app.exit()        
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore logging on exit
        restore_logging()