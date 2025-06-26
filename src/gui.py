from threading import Thread
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDir, QUrl
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
import sys
import asyncio
import io
import os
import extraction as egz

def get_base_path():
    """Get the base path for files, accounting for PyInstaller bundle"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

ministries_list = []
user_domains = []
user_keywords = []

class LogStream(io.StringIO):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def write(self, text):
        if text.strip():
            self.log_signal.emit(text.strip())
        return len(text)
    
    def flush(self):
        pass

class LogSignalEmitter(QObject):
    log_message = Signal(str)
    progress_update = Signal(str, str, str)

# Global log signal emitter
log_emitter = LogSignalEmitter()

class PdfViewer(QMainWindow):
    def __init__(self, pdf_path):
        super().__init__()
        self.setWindowTitle(f"PDF Viewer - {os.path.basename(pdf_path)}")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add status label for debugging
        self.status_label = QLabel("Loading PDF...")
        layout.addWidget(self.status_label)

        self.pdf_view = QPdfView()
        layout.addWidget(self.pdf_view)

        self.document = QPdfDocument(self)
        self.pdf_view.setDocument(self.document)

        # Connect status change signal for debugging
        self.document.statusChanged.connect(self.on_status_changed)

        # Load PDF file
        if pdf_path and os.path.exists(pdf_path):
            try:
                print(f"Attempting to load PDF: {pdf_path}")
                self.document.load(pdf_path)
            except Exception as e:
                self.status_label.setText(f"Error loading PDF: {str(e)}")
                print(f"Error loading PDF: {e}")
                QMessageBox.warning(self, "Error", f"Failed to load PDF: {str(e)}")
        else:
            self.status_label.setText("PDF file not found")
            QMessageBox.warning(self, "Error", "PDF file not found or invalid path.")

    def on_status_changed(self, status):
        """Handle document status changes for debugging"""
        
        status_messages = {
            QPdfDocument.Status.Null: "No document loaded",
            QPdfDocument.Status.Loading: "Loading document...",
            QPdfDocument.Status.Ready: "Document ready",
            QPdfDocument.Status.Error: "Error loading document"
        }
        
        message = status_messages.get(status, f"Unknown status: {status}")
        self.status_label.setText(message)
        print(f"PDF Document Status: {message}")
        
        if status == QPdfDocument.Status.Ready:
            print(f"PDF loaded successfully. Page count: {self.document.pageCount()}")
            self.status_label.hide()  # Hide status label when PDF is ready
        elif status == QPdfDocument.Status.Error:
            error_msg = f"PDF loading error"
            print(error_msg)
            QMessageBox.warning(self, "PDF Error", error_msg)

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
        self.tree_view.setRootIndex(self.model.index(QDir.currentPath()))
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
                viewer = PdfViewer(path)
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
        
        from datetime import datetime
        self.today = datetime.now()
        log_emitter.log_message.connect(self.add_log_message)
        
        base_path = get_base_path()
        self.file_path = os.path.join(base_path, "files", "logs", f"log{self.today.strftime('%Y%m%d')}.txt")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.log_f = open(self.file_path, "a+")
        
    def add_log_message(self, message):
        """Add a log message to the display"""
        timestamp = self.today.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_display.append(formatted_message)
        self.log_f.write(formatted_message + "\n")
        
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
        delete_btn.setIcon(QApplication.instance().style().standardIcon(QStyle.SP_TrashIcon))
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
            'label': indicator
        }        
        return row_widget
    
    def _handle_blink(self):
        """Handle the blinking timer timeout"""
        if self.blinking_item and self.blinking_item in self.item_widgets:
            self.blink_state = not self.blink_state
            color = '#ffeb3b' if self.blink_state else 'transparent'
            label = self.item_widgets[self.blinking_item]['label']
            label.setStyleSheet(f"padding: 5px; background-color: {color}; border-radius: 3px;")
    
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
        if hasattr(self, 'blink_timer') and self.blink_timer.isActive():
            self.blink_timer.stop()
        self.blinking_item = None
        self.blink_state = False
        
        for item_text in self.item_widgets:
            self.update_item_color(item_text, 'default')
    
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
        """Clean up timers and resources"""
        if hasattr(self, 'blink_timer') and self.blink_timer.isActive():
            self.blink_timer.stop()
        self.blinking_item = None

class KeywordEntries(QScrollArea):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
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
        row_widget.setStyleSheet("""
            QWidget:hover {
                background-color: #2a5dd5;
            }
        """)
        
        checkbox = QCheckBox()
        checkbox.setChecked(is_checked)
        checkbox.setFixedSize(20, 20)
        checkbox.toggled.connect(lambda checked: self._toggle_item(item_text, checked))
        
        label = QLabel(item_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("padding: 5px;")
        
        delete_btn = QPushButton()
        delete_btn.setIcon(QApplication.instance().style().standardIcon(QStyle.SP_TrashIcon))
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
        
        row_layout.addWidget(checkbox)
        row_layout.addWidget(label)
        row_layout.addWidget(delete_btn)
        row_layout.setStretch(1, 1)
        
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
        for i in reversed(range(self.layout.count())):
            child = self.layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
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
        """Update the entire list with new items"""
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
    if window.start_button.text() == "Cancel":
        print("Extraction cancelled by user")
        egz.eve_sig.clear()
        if hasattr(window, '_status_timer') and window._status_timer.isActive():
            window._status_timer.stop()
        if hasattr(window, '_progress_popup') and window._progress_popup.isVisible():
            window._progress_popup.close()
        
        window.section1.frame.reset_all_colors()
        window.start_button.setText("Start")
        window.start_button.setEnabled(True)
        return
        
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
            egz.eve_sig.clear()
            if hasattr(window, '_status_timer'):
                window._status_timer.stop()
            progress_popup.close()
            window.section1.frame.reset_all_colors()
            window.start_button.setText("Start")
            window.start_button.setEnabled(True)
    
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
        
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(error_popup, auto_close_timer))
        auto_close_timer.start(3000)
        return
    
    if egz.empty_domains.is_set():
        cleanup_and_close()
        egz.empty_domains.clear()
        
        error_popup = QMessageBox(window)
        error_popup.setText("No domains selected! Please select at least one domain.")
        error_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("No domains selected during extraction!")
        error_popup.show()
        
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(error_popup, auto_close_timer))
        auto_close_timer.start(3000)
        return
        
    if not egz.eve_sig.is_set():
        cleanup_and_close()
        
        success_popup = QMessageBox(window)
        base_path = get_base_path()
        files_path = os.path.join(base_path, "files")
        success_popup.setText(f"Extraction completed!\nTotal {egz.dwnld_count} files downloaded.\nFiles saved in {files_path} directory")
        success_popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        print("Extraction completed!")
        success_popup.show()
        
        auto_close_timer = QTimer(window)
        auto_close_timer.timeout.connect(lambda: close_popup_and_enable(success_popup, auto_close_timer))
        auto_close_timer.start(5000)

def close_popup_and_enable(popup, timer):
    """Helper function to close popup and re-enable start button"""
    timer.stop()
    popup.close()
    window.start_button.setText("Start")
    window.start_button.setEnabled(True)
class HomePage(QWidget):
    def log_toggle(self):
        text = ["Show Logs", "Hide Logs"]
        self.log_tog.setText(text[self.log_tog.isChecked()])
        self.log_window.setVisible(self.log_tog.isChecked())
    def file_toggle(self):
        text = ["View files", "Close browser"]
        self.file_tog.setText(text[self.file_tog.isChecked()])
        self.file_browser.setVisible(self.file_tog.isChecked())
    
    def __init__(self, Domains, Ministries, Keywords):
        super().__init__()
        self.setWindowTitle("Homepage")
        self.setGeometry(100, 100, 1400, 600)
        
        global ministries_list
        ministries_list = Ministries
        self.section1 = ColumnSection("Domains", items=Ministries, frame_items=Domains)
        self.section2 = ColumnSection("Keywords", frame_items=Keywords)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(start_action)
        
        log_emitter.progress_update.connect(self.update_domain_color)
        
        self.file_browser = FileBrowser()
        self.file_browser.setVisible(False)

        self.log_window = LogWindow()
        self.log_window.setVisible(False)
        
        main_layout = QHBoxLayout()
        
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        
        # Create progress widget to replace sections during initialization
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        progress_label = QLabel("Initializing browser...")
        progress_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #666;")
        progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setFixedWidth(300)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        row_wrapper = QHBoxLayout()
        
        # Always add both to layout but control visibility
        row_wrapper.addWidget(self.section1)
        row_wrapper.addWidget(self.section2)
        row_wrapper.addWidget(self.progress_widget)
        
        if not egz.browser_ready.is_set():
            # Show progress widget instead of sections
            self.section1.setVisible(False)
            self.section2.setVisible(False)
            self.progress_widget.setVisible(True)
        else:
            # Show normal sections
            self.section1.setVisible(True)
            self.section2.setVisible(True)
            self.progress_widget.setVisible(False)
        
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

        controls_layout.addLayout(row_wrapper)
        controls_layout.addLayout(row_buttons)
        
        main_layout.addWidget(controls_widget, 2)
        main_layout.addWidget(self.file_browser, 1)
        main_layout.addWidget(self.log_window, 1)
        
        self.setLayout(main_layout)
    
    def update_domain_color(self, ministry_name, status, count):
        """Update the color of a domain entry based on extraction progress"""
        self.section1.frame.update_item_color(ministry_name, status, count)
    def closeEvent(self, event):
        """Handle window close event to ensure proper cleanup"""
        print("Closing application...")
        self.log_window.log_f.close()


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
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Starting browser initialization (egz)... Attempt {retry_count + 1}/{max_retries}")
                egz.browser_ready.clear()
                res = await egz.egz_extract_defaults()
                
                if res < 0:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print("Maximum retry attempts reached. Browser initialization failed.")
                        egz.browser_ready.set()
                        return
                    print(f"Browser initialization failed, retrying in 2 seconds... ({retry_count}/{max_retries})")
                    await asyncio.sleep(2)
                    continue
                
                print("Browser initialization successful!")
                break
                
            except Exception as e:
                retry_count += 1
                print(f"Browser initialization error (gui): {e}")
                if retry_count >= max_retries:
                    print("Maximum retry attempts reached. Browser initialization failed.")
                    egz.browser_ready.set()
                    return
                print(f"Retrying browser initialization in 2 seconds... ({retry_count}/{max_retries})")
                await asyncio.sleep(2)
                continue
        
        if retry_count < max_retries:
            try:
                while True:
                    if egz.eve_sig.is_set():
                        print("Processing extraction request...")
                        try:
                            domain_names = window.section1.frame.get_items()
                            keyword_data = window.section2.frame.get_items()
                            
                            domain_codes = []
                            for domain_name in domain_names:
                                for code, name in egz.valdict.items():
                                    if name == domain_name:
                                        domain_codes.append(code)
                                        break
                            
                            keywords = keyword_data
                            
                            print(f"Domain codes: {domain_codes}")
                            print(f"Keywords: {keywords}")
                            
                            if(await egz.extract_mids(domain_names, keyword_data) < 0):
                                continue
                            
                            print(f"Returned back from extract_mids, starting download...\nValue of eve_sig: {egz.eve_sig.is_set()}")
                            
                            if not egz.eve_sig.is_set():
                                print("Extraction was cancelled, stopping...")
                                continue
                                
                            print("Extraction completed successfully!\nNow downloading files...")
                            window.section1.frame.cleanup()
                            egz.egz_download()
                               
                        except Exception as e:
                            print(f"Error during extraction: {e}")
                        finally:
                            egz.eve_sig.clear()
                    
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("Extraction worker interrupted by user")
            except Exception as e:
                print(f"Error in extraction main loop: {e}")
        else:
            print("Browser initialization failed after all retry attempts. Extraction worker stopped.")

    try:
        print("Creating Qt application...")
        app = QApplication(sys.argv)
        
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
                except:
                    pass
        
        extraction_thread = Thread(target=run_async_worker, daemon=True)
        extraction_thread.start()
        
        print("Initializing browser in background...")
        window = HomePage([], [], Keywords=[])
        window.start_button.setEnabled(False)
        window.file_tog.setEnabled(False)
        window.setWindowTitle("DICV Monitor - Initializing...")
        window.show()
        
        def check_browser_ready():
            global window
            
            if hasattr(check_browser_ready, 'initialized') and check_browser_ready.initialized:
                return
            
            if not hasattr(check_browser_ready, 'timeout_counter'):
                check_browser_ready.timeout_counter = 0
            
            check_browser_ready.timeout_counter += 1
            max_timeout = 60
            
            if check_browser_ready.timeout_counter > max_timeout:
                print("Browser initialization timeout! Enabling UI with defaults.")
                check_browser_ready.initialized = True
                browser_timer.stop()
                # Switch from progress widget to sections
                window.progress_widget.setVisible(False)
                window.start_button.setVisible(False)
                window.file_tog.setVisible(False)
                window.setWindowTitle("DICV Monitor")
                window.start_button.setEnabled(True)
                window.file_tog.setEnabled(True)
                QMessageBox.warning(window, "Browser Initialization", 
                                  "Browser initialization timed out. Kindly close the application and try again.")
                return
                
            if egz.browser_ready.is_set():
                print("Browser initialization completed!")
                check_browser_ready.initialized = True
                browser_timer.stop()
                
                try:
                    ministries_list = list(egz.valdict.values()) if hasattr(egz, 'valdict') else []
                    print(f"Found {len(ministries_list)} ministries")
                    
                    if hasattr(egz, 'kwList'):
                        print(f"Keywords: {[i[0] for i in egz.kwList]}")
                    
                    if ministries_list and len(ministries_list) > 1:
                        default_domains = [egz.valdict[i] for i in egz.mList_input] if hasattr(egz, 'mList_input') else []
                        default_keywords = [i for i in egz.kwList] if hasattr(egz, 'kwList') else []
                        
                        new_window = HomePage(default_domains, ministries_list, Keywords=default_keywords)
                        new_window.setWindowTitle("DICV Monitor")
                        new_window.show()
                        window.close()
                        window = new_window
                    else:
                        print("WARNING: Insufficient ministries found! Using defaults.")
                        # Switch from progress widget to sections
                        window.progress_widget.setVisible(False)
                        window.section1.setVisible(True)
                        window.section2.setVisible(True)
                        window.setWindowTitle("DICV Monitor")
                        window.start_button.setEnabled(True)
                        window.file_tog.setEnabled(True)
                        QMessageBox.warning(window, "Browser Initialization", 
                                          "Browser initialized but ministry data is incomplete. Using defaults.")
                        
                except Exception as e:
                    print(f"Error updating window: {e}")
                    # Switch from progress widget to sections even on error
                    window.progress_widget.setVisible(False)
                    window.section1.setVisible(True)
                    window.section2.setVisible(True)
                    window.setWindowTitle("DICV Monitor")
                    window.start_button.setEnabled(True)
                    window.file_tog.setEnabled(True)
                    QMessageBox.warning(window, "Browser Initialization", 
                                      f"Error loading browser data: {e}\nUsing defaults.")
            else:
                dots = "." * (check_browser_ready.timeout_counter % 4)
                progress_text = f"Initializing browser{dots} ({check_browser_ready.timeout_counter}s)"
                window.setWindowTitle(f"DICV Monitor - {progress_text}")
        
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