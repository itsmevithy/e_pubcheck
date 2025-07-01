"""
PDF Viewer Module - Enhanced PDF viewing with full document display and navigation
"""

import os
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QComboBox, QMessageBox
from PySide6.QtCore import Qt, QPointF
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QKeySequence, QShortcut


class PdfViewer(QMainWindow):
    """Enhanced PDF viewer with full document display and comprehensive navigation"""
    
    def __init__(self, pdf_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.current_page = 0
        self.setup_ui()
        self.setup_shortcuts()
        self.load_pdf()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle(f"PDF Viewer - {os.path.basename(self.pdf_path)}")
        self.setGeometry(100, 100, 1000, 700)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Status label
        self.status_label = QLabel("Loading PDF...")
        layout.addWidget(self.status_label)

        # Create toolbar
        self.create_toolbar()

        # PDF View - Set to show full document
        self.pdf_view = QPdfView()
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)  # Show all pages
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)  # Fit to width by default
        layout.addWidget(self.pdf_view)

        # Document
        self.document = QPdfDocument(self)
        self.pdf_view.setDocument(self.document)

        # Connect signals
        self.document.statusChanged.connect(self.on_status_changed)
        self.pdf_view.pageNavigator().currentPageChanged.connect(self.on_current_page_changed)

    def create_toolbar(self):
        """Create navigation toolbar"""
        toolbar = self.addToolBar("Navigation")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Navigation actions
        self.first_page_action = toolbar.addAction("⇤ First")
        self.first_page_action.triggered.connect(self.go_to_first_page)
        self.first_page_action.setShortcut(QKeySequence("Home"))

        self.prev_page_action = toolbar.addAction("◀ Previous")
        self.prev_page_action.triggered.connect(self.go_to_previous_page)
        self.prev_page_action.setShortcut(QKeySequence("Left"))

        self.next_page_action = toolbar.addAction("Next ▶")
        self.next_page_action.triggered.connect(self.go_to_next_page)
        self.next_page_action.setShortcut(QKeySequence("Right"))

        self.last_page_action = toolbar.addAction("Last ⇥")
        self.last_page_action.triggered.connect(self.go_to_last_page)
        self.last_page_action.setShortcut(QKeySequence("End"))

        toolbar.addSeparator()

        # Page info and navigation
        page_widget = QWidget()
        page_layout = QHBoxLayout(page_widget)
        page_layout.setContentsMargins(5, 0, 5, 0)

        self.page_label = QLabel("Page: 0 / 0")
        page_layout.addWidget(self.page_label)

        page_layout.addWidget(QLabel("Go to:"))
        self.page_input = QLineEdit()
        self.page_input.setMaximumWidth(60)
        self.page_input.setPlaceholderText("Page")
        self.page_input.returnPressed.connect(self.go_to_page_from_input)
        page_layout.addWidget(self.page_input)

        toolbar.addWidget(page_widget)
        toolbar.addSeparator()

        # View mode selection
        view_mode_widget = QWidget()
        view_mode_layout = QHBoxLayout(view_mode_widget)
        view_mode_layout.setContentsMargins(5, 0, 5, 0)

        view_mode_layout.addWidget(QLabel("View:"))
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Single Page", "Continuous"])
        self.view_mode_combo.setCurrentText("Continuous")
        self.view_mode_combo.currentTextChanged.connect(self.change_view_mode)
        view_mode_layout.addWidget(self.view_mode_combo)

        toolbar.addWidget(view_mode_widget)
        toolbar.addSeparator()

        # Zoom controls
        self.zoom_out_action = toolbar.addAction("🔍- Zoom Out")
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))

        self.zoom_in_action = toolbar.addAction("🔍+ Zoom In")
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setShortcut(QKeySequence("Ctrl+="))

        self.fit_width_action = toolbar.addAction("⬌ Fit Width")
        self.fit_width_action.triggered.connect(self.fit_to_width)
        self.fit_width_action.setShortcut(QKeySequence("Ctrl+W"))

        self.fit_page_action = toolbar.addAction("⬜ Fit Page")
        self.fit_page_action.triggered.connect(self.fit_to_page)
        self.fit_page_action.setShortcut(QKeySequence("Ctrl+F"))

        # Initially disable navigation actions
        self.update_navigation_actions(False)

    def setup_shortcuts(self):
        """Setup additional keyboard shortcuts"""
        # Page navigation shortcuts
        QShortcut(QKeySequence("Up"), self, self.go_to_previous_page)
        QShortcut(QKeySequence("Down"), self, self.go_to_next_page)
        QShortcut(QKeySequence("Page_Up"), self, self.go_to_previous_page)
        QShortcut(QKeySequence("Page_Down"), self, self.go_to_next_page)
        
        # Additional zoom shortcuts
        QShortcut(QKeySequence("Ctrl+0"), self, self.reset_zoom)
        QShortcut(QKeySequence("="), self, self.zoom_in)
        QShortcut(QKeySequence("-"), self, self.zoom_out)

    def load_pdf(self):
        """Load the PDF document"""
        if self.pdf_path and os.path.exists(self.pdf_path):
            try:
                print(f"Loading PDF: {self.pdf_path}")
                self.document.load(self.pdf_path)
            except Exception as e:
                self.show_error(f"Error loading PDF: {str(e)}")
        else:
            self.show_error("PDF file not found or invalid path.")

    def on_status_changed(self, status):
        """Handle document status changes"""
        status_messages = {
            QPdfDocument.Status.Null: "No document loaded",
            QPdfDocument.Status.Loading: "Loading document...",
            QPdfDocument.Status.Ready: "Document ready",
            QPdfDocument.Status.Error: "Error loading document"
        }

        message = status_messages.get(status, f"Unknown status: {status}")
        self.status_label.setText(message)
        print(f"PDF Status: {message}")

        if status == QPdfDocument.Status.Ready:
            page_count = self.document.pageCount()
            print(f"PDF loaded successfully. Pages: {page_count}")
            self.status_label.hide()
            self.update_navigation_controls()
            self.update_navigation_actions(True)
        elif status == QPdfDocument.Status.Error:
            self.show_error("Failed to load PDF document")

    def on_current_page_changed(self, page_number):
        """Handle current page changes from the PDF view"""
        self.current_page = page_number
        self.update_navigation_controls()

    def update_navigation_controls(self):
        """Update navigation controls based on current page"""
        if self.document.status() == QPdfDocument.Status.Ready:
            page_count = self.document.pageCount()
            self.page_label.setText(f"Page: {self.current_page + 1} / {page_count}")

            # Update action states
            self.first_page_action.setEnabled(self.current_page > 0)
            self.prev_page_action.setEnabled(self.current_page > 0)
            self.next_page_action.setEnabled(self.current_page < page_count - 1)
            self.last_page_action.setEnabled(self.current_page < page_count - 1)

    def update_navigation_actions(self, enabled):
        """Enable or disable navigation actions"""
        actions = [
            self.first_page_action, self.prev_page_action,
            self.next_page_action, self.last_page_action,
            self.zoom_in_action, self.zoom_out_action,
            self.fit_width_action, self.fit_page_action
        ]
        for action in actions:
            action.setEnabled(enabled)

    def go_to_first_page(self):
        """Navigate to first page"""
        if self.document.status() == QPdfDocument.Status.Ready:
            self.pdf_view.pageNavigator().jump(0, QPointF(), self.pdf_view.zoomFactor())

    def go_to_previous_page(self):
        """Navigate to previous page"""
        if self.current_page > 0:
            self.pdf_view.pageNavigator().jump(self.current_page - 1, QPointF(), self.pdf_view.zoomFactor())

    def go_to_next_page(self):
        """Navigate to next page"""
        if self.document.status() == QPdfDocument.Status.Ready:
            page_count = self.document.pageCount()
            if self.current_page < page_count - 1:
                self.pdf_view.pageNavigator().jump(self.current_page + 1, QPointF(), self.pdf_view.zoomFactor())

    def go_to_last_page(self):
        """Navigate to last page"""
        if self.document.status() == QPdfDocument.Status.Ready:
            page_count = self.document.pageCount()
            if page_count > 0:
                self.pdf_view.pageNavigator().jump(page_count - 1, QPointF(), self.pdf_view.zoomFactor())

    def go_to_page_from_input(self):
        """Navigate to page specified in input field"""
        if self.document.status() != QPdfDocument.Status.Ready:
            return

        try:
            page_number = int(self.page_input.text())
            page_count = self.document.pageCount()

            if 1 <= page_number <= page_count:
                target_page = page_number - 1  # Convert to 0-based
                self.pdf_view.pageNavigator().jump(target_page, QPointF(), self.pdf_view.zoomFactor())
                self.page_input.clear()
            else:
                QMessageBox.warning(self, "Invalid Page", 
                                  f"Please enter a page number between 1 and {page_count}")
                self.page_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid page number")
            self.page_input.clear()

    def change_view_mode(self, mode_text):
        """Change the PDF view mode"""
        mode_map = {
            "Single Page": QPdfView.PageMode.SinglePage,
            "Continuous": QPdfView.PageMode.MultiPage
        }
        
        mode = mode_map.get(mode_text, QPdfView.PageMode.MultiPage)
        self.pdf_view.setPageMode(mode)
        
        # For continuous viewing, ensure proper layout
        if mode_text == "Continuous":
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def zoom_in(self):
        """Zoom in"""
        current_zoom = self.pdf_view.zoomFactor()
        self.pdf_view.setZoomFactor(min(current_zoom * 1.25, 5.0))

    def zoom_out(self):
        """Zoom out"""
        current_zoom = self.pdf_view.zoomFactor()
        self.pdf_view.setZoomFactor(max(current_zoom * 0.8, 0.1))

    def fit_to_width(self):
        """Fit to width"""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def fit_to_page(self):
        """Fit to page"""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)

    def reset_zoom(self):
        """Reset zoom to 100%"""
        self.pdf_view.setZoomFactor(1.0)

    def show_error(self, message):
        """Show error message"""
        self.status_label.setText(message)
        print(f"PDF Viewer Error: {message}")
        QMessageBox.warning(self, "PDF Viewer Error", message)

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Let shortcuts handle the events first
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel events"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl + wheel for zoom
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Default wheel behavior for scrolling
            super().wheelEvent(event)


def create_pdf_viewer(pdf_path):
    """Factory function to create a PDF viewer"""
    return PdfViewer(pdf_path)


if __name__ == "__main__":
    """Test the PDF viewer standalone"""
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Test with a sample PDF
    pdf_path = r"C:\Users\lordv\.tempbuild\dicv_mon\src\files\AIS\AIS-163_(Annexure_3)_(Date_of_hosting_on_ARAI_website___20th_June_2025).pdf"
    
    if os.path.exists(pdf_path):
        viewer = PdfViewer(pdf_path)
        viewer.show()
        sys.exit(app.exec())
    else:
        print("No test PDF file found")
