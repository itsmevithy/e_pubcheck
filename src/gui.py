from threading import Thread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QFileSystemModel, QTreeView, QMessageBox, QScrollArea, QCheckBox, QComboBox, QCompleter, QProgressBar, QSplitter, QApplication
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDir
import sys
import asyncio
import io
import os
import datetime
import extraction as egz
import qtawesome as qta
import pdf_viewer as pv

def get_base_path():
    """Get the base path for files, accounting for PyInstaller bundle"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

class LogStream(io.StringIO):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def write(self, text):
        if text.strip():
            self.log_signal.emit(text.strip())
        return len(text)

class LogSignalEmitter(QObject):
    log_message = Signal(str)
    progress_update = Signal(str, str, str)

# Global log signal emitter
log_emitter = LogSignalEmitter()

class FileBrowser(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        self.path_Edit = QLineEdit()
        self.path_Edit.setPlaceholderText("Enter file path or URL")
        layout.addWidget(self.path_Edit)

        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(QDir.currentPath()+"/files"))
        layout.addWidget(self.tree_view)

        self.setLayout(layout)

        # Connect signals (e.g., tree_view selection changed, button clicks)
        self.tree_view.clicked.connect(self.update_path_bar)

    def update_path_bar(self, index):
        path = self.model.filePath(index)
        self.path_Edit.setText(path)
        
        if os.path.isfile(path) and path.lower().endswith('.pdf'):
            try:
                print(f"Opening PDF: {path}")
                viewer = pv.create_pdf_viewer(path)
                viewer.show()
                
                # Keep reference to prevent garbage collection
                if not hasattr(self, 'pdf_viewers'):
                    self.pdf_viewers = []
                self.pdf_viewers.append(viewer)
                
            except Exception as e:
                print(f"Error opening PDF viewer: {e}")
                QMessageBox.warning(self, "Error", f"Could not open PDF: {str(e)}")

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
        log_emitter.log_message.connect(self.add_log_message)
        
        base_path = get_base_path()
        self.file_path = os.path.join(base_path, "files", "logs", f"log{datetime.datetime.now().strftime('%Y%m%d')}.txt")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
    def add_log_message(self, message):
        """Add a log message to the display"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_display.append(formatted_message)
        with open(self.file_path, "a+") as log_f:
            log_f.write(formatted_message + "\n")
        
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
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
        self.items_list = items.copy()
        self.item_widgets = {}
        self.extraction_in_progress = False  # Track extraction state
        self._refresh_display()
        self.content.setLayout(self.layout)
        self.setWidget(self.content)
        
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(500)
        self.blink_timer.timeout.connect(self._handle_blink)
        self.blinking_item = None
        self.blink_state = False

    def _create_item_row(self, item_text):
        """Create a row with item text and delete button"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_widget.setStyleSheet("""
            QWidget:hover {
                background-color: #2a5dd5;                     
            }
        """)
        
        label = QLabel(item_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        indicator = QLabel()
        indicator.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        indicator.setFixedSize(50, 25)
        indicator.setStyleSheet("padding: 5px; background-color: transparent; border-radius: 12px;")
        
        delete_btn = QPushButton()
        delete_btn.setIcon(qta.icon('fa6s.trash-can'))
        delete_btn.setFixedSize(25, 25)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #969696;
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
        row_layout.addWidget(indicator)
        row_layout.addWidget(delete_btn)
        row_layout.setStretch(0, 1)
        
        self.item_widgets[item_text] = {
            'widget': row_widget,
            'label': indicator,
            'delete_btn': delete_btn
        }
        
        # If extraction is in progress, disable the delete button
        if self.extraction_in_progress:
            delete_btn.setEnabled(False)
            
        return row_widget
    
    def _handle_blink(self):
        """Handle the blinking timer timeout"""
        if self.blinking_item and self.blinking_item in self.item_widgets:
            self.blink_state = not self.blink_state
            color = '#ffeb3b' if self.blink_state else 'transparent'
            label = self.item_widgets[self.blinking_item]['label']
            label.setStyleSheet(f"padding: 5px; background-color: {color}; border-radius: 3px;")
    
    def disable_trash(self):
        """Disable the delete button for all items"""
        self.extraction_in_progress = True
        for item_text, widgets in self.item_widgets.items():
            widgets['delete_btn'].setEnabled(False)
            
    def enable_trash(self):
        """Enable the delete button for all items"""
        self.extraction_in_progress = False
        for item_text, widgets in self.item_widgets.items():
            widgets['delete_btn'].setEnabled(True)

    def update_item_color(self, item_text, status, count="-"):
        """Update the color of a specific item based on status"""
        if item_text not in self.item_widgets:
            return
            
        colors = {
            'default': 'transparent',
            'extracting': '#ffeb3b',
            'completed': '#4caf50',
            'error': '#f44336',
            'skipped': "#2a5dd5",
        }
        
        if status == 'extracting':
            if self.blink_timer.isActive():
                self.blink_timer.stop()
                self.blink_state = True
                self._handle_blink()
            
            self.blinking_item = item_text
            self.blink_state = True
            self.blink_timer.start()
            return
        else:
            if self.blinking_item == item_text:
                self.blink_timer.stop()
                self.blinking_item = None
                self.blink_state = False
                
        color = colors.get(status, colors['default'])
        label = self.item_widgets[item_text]['label']
        label.setStyleSheet(f"padding: 5px; background-color: {color}; border-radius: 3px;")
        label.setText(count)
    
    def reset_all_colors(self):
        """Reset all items to default color and stop any blinking"""
        # Use Qt's thread-safe way to stop timer
        if hasattr(self, 'blink_timer'):
            QTimer.singleShot(0, self._stop_blinking)
        
        for item_text in self.item_widgets:
            self.update_item_color(item_text, 'default')
        
        # Only enable trash if extraction is not in progress
        if not self.extraction_in_progress:
            self.enable_trash()
    
    def _stop_blinking(self):
        """Thread-safe method to stop blinking timer"""
        if hasattr(self, 'blink_timer') and self.blink_timer.isActive():
            self.blink_timer.stop()
        self.blinking_item = None
        self.blink_state = False
    
    def _delete_item(self, item_text):
        """Remove item from list and refresh display"""
        if item_text in self.items_list:
            self.items_list.remove(item_text)
            if item_text in self.item_widgets:
                del self.item_widgets[item_text]
            self._refresh_display()
    
    def _refresh_display(self):
        """Clear and rebuild the display"""
        for i in reversed(range(self.layout.count())):
            child = self.layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        self.item_widgets.clear()
        
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
    
    def cleanup(self):
        """Clean up timers and resources in a thread-safe way"""
        # Use Qt's thread-safe way to stop timer
        if hasattr(self, 'blink_timer'):
            QTimer.singleShot(0, self._stop_blinking)

class KeywordEntries(QScrollArea):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items_list = items
        self.widgets_list = {}
        self.extraction_in_progress = False  # Track extraction state
        self._refresh_display()
        self.content.setLayout(self.layout)
        self.setWidget(self.content)
    
    def _create_item_row(self, item_data):
        """Create a row with checkbox, item text and delete button"""
        item_text, is_checked = item_data
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_widget.setStyleSheet("""
            QWidget:hover {
                background-color: #2a5dd5;
            }
        """)
        
        checkbox = QCheckBox()
        checkbox.setToolTip("Check this item to perform case-sensitive keyword-matching")
        checkbox.setChecked(is_checked)
        checkbox.setFixedSize(20, 20)
        checkbox.toggled.connect(lambda checked: self._toggle_item(item_text, checked))
        
        label = QLabel(item_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("padding: 5px;")
        
        delete_btn = QPushButton()
        delete_btn.setIcon(qta.icon('fa6s.trash-can'))
        delete_btn.setFixedSize(25, 25)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #969696;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        delete_btn.clicked.connect(lambda: self._delete_item(item_text))
        
        # Store widget reference properly
        self.widgets_list[item_text] = {
            'widget': row_widget,
            'delete_btn': delete_btn
        }
        
        row_layout.addWidget(checkbox)
        row_layout.addWidget(label)
        row_layout.addWidget(delete_btn)
        row_layout.setStretch(1, 1)
        
        return row_widget
    
    def enable_trash(self):
        """Enable the delete button for all items"""
        self.extraction_in_progress = False
        for widget in self.widgets_list.values():
            widget['delete_btn'].setEnabled(True)
            
    def disable_trash(self):
        """Disable the delete button for all items"""
        self.extraction_in_progress = True
        for widget in self.widgets_list.values():
            widget['delete_btn'].setEnabled(False)

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
        for i in reversed(range(self.layout.count())):
            child = self.layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Clear the widgets list before rebuilding
        self.widgets_list.clear()
        
        for item_data in self.items_list:
            row_widget = self._create_item_row(item_data)
            self.layout.addWidget(row_widget)
            self.widgets_list[item_data[0]] = {
                'widget': row_widget,
                'delete_btn': row_widget.findChild(QPushButton)
            }
    
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
        """Update the entire list with new items"""
        self.items_list = [[item, False] for item in items] if items else []
        self._refresh_display()

class ColumnSection(QWidget):
    def submit_action(self, content, items):
        global ministries_list
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

def submit_action():
    """Handle start/cancel button clicks"""
    if window.start_button.text() == "Cancel":
        egz.eve_sig.clear()
        if hasattr(window, '_status_timer') and window._status_timer.isActive():
            window._status_timer.stop()
        if hasattr(window, '_progress_popup') and window._progress_popup.isVisible():
            window._progress_popup.close()
        
        window.section1.frame.reset_all_colors()
        window.section1.frame.enable_trash()
        window.section2.frame.enable_trash()
        window.start_button.setText("Start")
        window.start_button.setEnabled(True)
        return
    
    window.section1.frame.disable_trash()
    window.section2.frame.disable_trash()  # Also disable trash for keywords
    egz.eve_sig.set()
    window.start_button.setText("Cancel")
    print("Start button clicked - setting extraction signal")
    
    progress_popup = QMessageBox(window)
    progress_popup.setText("Extraction in progress, please wait...")
    progress_popup.setStandardButtons(QMessageBox.StandardButton.Cancel)
    progress_popup.show()
    
    window._progress_popup = progress_popup
    
    def handle_popup_cancel():
        if progress_popup.clickedButton() == progress_popup.button(QMessageBox.StandardButton.Cancel):
            print("User cancelled extraction via popup")
            submit_action()  # Call submit_action to handle cancellation
    
    progress_popup.buttonClicked.connect(handle_popup_cancel)
    
    egz.eve_sig.set()
    egz.timeout_event.clear()
    egz.empty_domains.clear()
    
    window.section1.frame.reset_all_colors()
    
    print("Extraction signal set, starting extraction...")
    
    status_timer = QTimer(window)
    status_timer.timeout.connect(lambda: check_extraction_status(progress_popup, status_timer))
    status_timer.start(100)
    
    window._status_timer = status_timer

def check_extraction_status(progress_popup, status_timer):
    """Non-blocking status checker for extraction progress"""
    
    def cleanup_and_close():
        status_timer.stop()
        if progress_popup and progress_popup.isVisible():
            progress_popup.close()
        if hasattr(window, '_status_timer'):
            delattr(window, '_status_timer')
        if hasattr(window, '_progress_popup'):
            delattr(window, '_progress_popup')
    
    if egz.timeout_event.is_set():
        cleanup_and_close()
        
        error_popup = QMessageBox(window)
        error_popup.setText("Timeout occurred! Please try again.")
        error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("Timeout occurred during extraction!")
        error_popup.show()
        return
    
    if egz.empty_domains.is_set():
        cleanup_and_close()
        egz.empty_domains.clear()
        
        error_popup = QMessageBox(window)
        error_popup.setText("No domains selected! Please select at least one domain.")
        error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("No domains selected during extraction!")
        error_popup.show()
        return
        
    if not egz.eve_sig.is_set():
        cleanup_and_close()
        
        success_popup = QMessageBox(window)
        base_path = get_base_path()
        files_path = os.path.join(base_path, "files")
        success_popup.setText(f"Extraction completed!\nTotal {egz.dwnld_count} files downloaded.\nFiles saved in {files_path} directory")
        success_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("Extraction completed!")
        submit_action()
        success_popup.show()

class HomePage(QWidget):
    def log_toggle(self):
        text = ["Show Logs", "Hide Logs"]
        self.log_tog.setText(text[self.log_tog.isChecked()])
        self.log_window.setVisible(self.log_tog.isChecked())
    def file_toggle(self):
        text = ["View files", "Close file browser"]
        self.file_tog.setText(text[self.file_tog.isChecked()])
        self.file_browser.setVisible(self.file_tog.isChecked())
    
    def __init__(self, domains, ministries, keywords):
        super().__init__()
        self.setWindowTitle("Homepage")
        #self.setGeometry(100, 100, 900, 600)
        
        global ministries_list
        ministries_list = ministries
        self.section1 = ColumnSection("Domains", items=ministries, frame_items=domains)
        self.section2 = ColumnSection("Keywords", frame_items=keywords)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(submit_action)
        
        log_emitter.progress_update.connect(self.update_domain_color)
        
        self.file_browser = FileBrowser()
        self.file_browser.setVisible(False)

        self.log_window = LogWindow()
        self.log_window.setVisible(False)
        
        # Create main layout to hold the splitter
        main_layout = QVBoxLayout()
        
        # Create progress widget to replace sections during initialization
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        progress_label = QLabel("Initializing web-driver")
        progress_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #666;")
        progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setFixedWidth(300)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        # Add status label for progress text
        self.status_label = QLabel("Preparing resources")
        self.status_label.setStyleSheet("font-size: 12px; color: #666; padding: 5px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.status_label)
        
        wid_show = egz.browser_ready.is_set()
        self.section1.setVisible(wid_show)
        self.section2.setVisible(wid_show)
        self.progress_widget.setVisible(not wid_show)
        
        self.file_tog = QPushButton("View files")
        self.file_tog.setCheckable(True)
        self.file_tog.clicked.connect(self.file_toggle)

        self.log_tog = QPushButton("Show Logs")
        self.log_tog.setCheckable(True)
        self.log_tog.clicked.connect(self.log_toggle)
        
        row_buttons = QHBoxLayout()
        row_buttons.addWidget(self.start_button)
        row_buttons.addWidget(self.file_tog)
        row_buttons.addWidget(self.log_tog)

        extras_splitter = QSplitter()
        extras_splitter.setOrientation(Qt.Orientation.Vertical)
        extras_splitter.addWidget(self.log_window)
        extras_splitter.addWidget(self.file_browser)
        
        row_wrapper = QSplitter()
        row_wrapper.setOrientation(Qt.Orientation.Horizontal)
        row_wrapper.addWidget(self.section1)
        row_wrapper.addWidget(self.section2)
        row_wrapper.addWidget(self.progress_widget)
        row_wrapper.addWidget(extras_splitter)
        row_wrapper.setSizes([200, 300, 300, 300])
        
        # Add splitter to main layout
        main_layout.addWidget(row_wrapper)
        main_layout.addLayout(row_buttons)
        
        self.setLayout(main_layout)
    
    def update_domain_color(self, ministry_name, status, count):
        """Update the color of a domain entry based on extraction progress"""
        self.section1.frame.update_item_color(ministry_name, status, count)
    def closeEvent(self, event):
        """Handle window close event to ensure proper cleanup"""
        print("Closing application...")


if __name__ == "__main__":
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
            print("Starting data initialization (gui)...")
            egz.browser_ready.clear()
            res = await egz.egz_extract_defaults()
            
            if res < 0:
                print("Data initialization failed!")
                egz.browser_ready.set()
            else:
                print("Data initialization successful!")
            while True:
                if not egz.eve_sig.is_set():
                    await asyncio.sleep(1)
                    continue 
                print("Processing extraction request...")
                domain_names = window.section1.frame.get_items()
                keyword_data = window.section2.frame.get_items()
                
                if(await egz.extract_mids(domain_names, keyword_data) < 0):
                    continue
                
                if not egz.eve_sig.is_set():
                    print("Extraction was cancelled, stopping...")
                    continue
                    
                print("Extraction completed successfully!\nNow downloading files...")
                window.section1.frame.cleanup()
                egz.egz_download()
                egz.eve_sig.clear()
        except KeyboardInterrupt:
            print("Extraction worker interrupted by user")
        except TimeoutError:
            print("Timeout occurred during extraction")
            egz.timeout_event.set()
        except Exception as e:
            print(f"Error during extraction: {e}")
        finally:
            egz.eve_sig.clear()

    try:
        print("Creating Qt application...")
        app = QApplication(sys.argv)
        error_msg = "Browser Initialization error"
        
        setup_logging()
        egz.set_log_emitter(log_emitter)
        
        def run_async_worker():
            """Wrapper to run async worker in its own event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(extraction_worker())
            except Exception as e:
                print(f"Error in async worker: {e}")
                egz.browser_ready.set()
            finally:
                try:
                    loop.close()
                except Exception as e:
                    print(f"Error closing loop: {e}")
        
        extraction_thread = Thread(target=run_async_worker, daemon=True)
        extraction_thread.start()
        
        print("Initializing browser in background...")
        window = HomePage([], [], keywords=[])
        window.start_button.setEnabled(False)
        window.file_tog.setEnabled(False)
        window.setWindowTitle("E-PubChecker - Initializing...")
        window.show()
        

        def fields_extraction():
            global window
            check_browser_ready.initialized = True
            browser_timer.stop()
            
            try:
                ministries_list = list(egz.valdict.values()) if hasattr(egz, 'valdict') else []
                print(f"Found {len(ministries_list)-2} ministries")
                
                if hasattr(egz, 'kwlist'):
                    print(f"Keywords: {[i[0] for i in egz.kwlist]}")
                
                if ministries_list and len(ministries_list) > 2:
                    print("Browser initialization completed!")
                    default_domains = [egz.valdict[i] for i in egz.mlist_input] if hasattr(egz, 'mlist_input') else []
                    default_keywords = [i for i in egz.kwlist] if hasattr(egz, 'kwlist') else []
                    
                    new_window = HomePage(default_domains, ministries_list, keywords=default_keywords)
                    new_window.setWindowTitle("E-PubChecker")
                    new_window.show()
                    window.close()
                    window = new_window
                else:
                    print("WARNING: Insufficient ministries found! Using defaults.")
                    # Switch from progress widget to sections
                    window.progress_widget.setVisible(False)
                    window.start_button.setVisible(False)
                    window.file_tog.setVisible(False)
                    window.log_tog.setVisible(False)
                    window.setWindowTitle("E-PubChecker")
                    QMessageBox.warning(window, error_msg, "Ministry data is incomplete. Kindly close the application and try again.")
                    app.quit()
                    
            except Exception as e:
                print(f"Error updating window: {e}")
                # Switch from progress widget to sections even on error
                window.progress_widget.setVisible(False)
                window.start_button.setVisible(False)
                window.file_tog.setVisible(False)
                window.log_tog.setVisible(False)
                window.setWindowTitle("E-PubChecker")
                QMessageBox.warning(window, error_msg, f"Error loading browser data: {e}\nKindly close the application and try again..")
                app.quit()

        def check_browser_ready():
            global window
            
            if hasattr(check_browser_ready, 'initialized') and check_browser_ready.initialized:
                return
            
            if not hasattr(check_browser_ready, 'timeout_counter'):
                check_browser_ready.timeout_counter = 0
            
            check_browser_ready.timeout_counter += 1
            max_timeout = 60
            
            if check_browser_ready.timeout_counter > max_timeout:
                print("Timeout initializing browser!.")
                check_browser_ready.initialized = True
                browser_timer.stop()
                # Switch from progress widget to sections
                window.progress_widget.setVisible(False)
                window.start_button.setVisible(False)
                window.file_tog.setVisible(False)
                window.log_tog.setVisible(False)
                window.setWindowTitle("E-PubChecker")
                QMessageBox.warning(window, error_msg, "Process timed out. Kindly close the application and try again.")
                app.quit()
                
            if egz.browser_ready.is_set():
                fields_extraction()
            else:
                dots = "." * (check_browser_ready.timeout_counter % 4)
                progress_text = f"Initializing {dots} ({check_browser_ready.timeout_counter}s)"
                window.setWindowTitle("E-PubChecker - Initializing...")
                
                # Update status label instead of window title for better alignment
                if hasattr(window, 'status_label'):
                    window.status_label.setText(progress_text)
        
        check_browser_ready.initialized = False
        check_browser_ready.timeout_counter = 0
        
        browser_timer = QTimer()
        browser_timer.timeout.connect(check_browser_ready)
        browser_timer.start(1000)
        
        print("Starting Qt event loop...")
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
        restore_logging()