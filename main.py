import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Schemedit")
    app.setOrganizationName("Bigocb")

    window = MainWindow()
    window.show()

    # If a .litematic path was passed as a CLI argument, open it immediately
    if len(sys.argv) > 1 and sys.argv[1].endswith(".litematic"):
        window._open_file_path(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
