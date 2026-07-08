import sys
import hashlib
import base64
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
)

# RSA Cryptographic Key Parameters (Private Key d, n - kept only in Keygen)
n = 124484595126548117481489410632012745818099415314085246803913294395814594355817893828886876474260975617030661874116414140863309392568758272381314926388952317527104692355122747277559442195925048622329862152643590701582746699287007318250273369063094606275229208675128862921767919126355453436035495589524808617817
e = 65537
d = 83237925563202337676027724075195119508685972471944759226712977203921252938960461164982844818271579008644241644376909234186977496698782748863908673027704464355051721334844121140486744747289281983729330908685757212727644658514860899557075770209955310219444726605904536273569475735662315873917424056377908737273

def get_hash_int(machine_id):
    mid_bytes = machine_id.strip().upper().encode('utf-8')
    h_hex = hashlib.sha256(mid_bytes).hexdigest()
    return int(h_hex, 16) % n

def generate_product_key(machine_id):
    try:
        h_int = get_hash_int(machine_id)
        # s = h^d mod n (generate digital signature)
        sig_int = pow(h_int, d, n)
        # Convert integer to bytes (128 bytes for 1024-bit key)
        sig_bytes = sig_int.to_bytes(128, byteorder='big')
        # Base64 encode to make a clean copy-pasteable key
        b64_str = base64.b64encode(sig_bytes).decode('utf-8').replace('=', '')
        return f"VST-KEY-{b64_str}"
    except Exception as ex:
        return f"Error generating key: {ex}"

DARK_STYLESHEET = """
QDialog {
    background-color: #0b0c10;
}
QWidget {
    color: #c5c6c7;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}
QLabel {
    font-weight: bold;
    color: #85929E;
}
QLineEdit, QTextEdit {
    background-color: #1f2833;
    border: 1px solid #2f3e46;
    border-radius: 6px;
    padding: 6px;
    color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #66fcf1;
}
QPushButton {
    background-color: #45a29e;
    border: 1px solid #66fcf1;
    border-radius: 6px;
    color: #0b0c10;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #66fcf1;
}
"""

class KeygenWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Vishal Steno Speech Studio - License Manager Keygen")
        self.setMinimumSize(500, 320)
        self.setStyleSheet(DARK_STYLESHEET)
        
        # Load window icon
        import os
        from PySide6.QtGui import QIcon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(500, 320)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QLabel("VISHAL STENO LICENSE KEYGEN MANAGER")
        title.setStyleSheet("font-weight: 800; font-size: 15px; color: #66fcf1; letter-spacing: 0.5px;")
        layout.addWidget(title)
        
        desc = QLabel("Paste the client's unique Machine ID (UUID) below to generate a cryptographically secure license key.")
        desc.setStyleSheet("color: #a1a1aa; font-weight: normal; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        mid_label = QLabel("Client Machine ID (UUID):")
        self.mid_input = QLineEdit()
        self.mid_input.setPlaceholderText("e.g. 4D11E74A-6BFD-EA11-80D7-089798C0559B")
        layout.addWidget(mid_label)
        layout.addWidget(self.mid_input)
        
        self.generate_btn = QPushButton("Generate Product Key")
        self.generate_btn.clicked.connect(self.on_generate)
        layout.addWidget(self.generate_btn)
        
        key_label = QLabel("Generated Product Key:")
        self.key_output = QTextEdit()
        self.key_output.setReadOnly(True)
        self.key_output.setPlaceholderText("Product key will appear here...")
        layout.addWidget(key_label)
        layout.addWidget(self.key_output)
        
        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy Key")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addStretch()
        btn_layout.addWidget(self.copy_btn)
        layout.addLayout(btn_layout)

    def on_generate(self):
        mid = self.mid_input.text().strip()
        if not mid:
            QMessageBox.warning(self, "Empty Input", "Please enter the client's Machine ID first.")
            return
        
        key = generate_product_key(mid)
        self.key_output.setText(key)
        self.copy_btn.setEnabled(True)

    def copy_to_clipboard(self):
        key = self.key_output.toPlainText().strip()
        if key:
            QApplication.clipboard().setText(key)
            self.copy_btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("Copy Key"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KeygenWindow()
    window.show()
    sys.exit(app.exec())
