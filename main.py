import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Schemedit")
    app.setOrganizationName("Bigocb")

    window = MainWindow()
    window.show()

    # Allow Ctrl+C in terminal to close gracefully instead of crashing
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # Qt doesn't process Python signals while in C++ event loop — pulse it
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(200)

    # If a .litematic path was passed as a CLI argument, open it on first event loop tick
    if len(sys.argv) > 1 and sys.argv[1].endswith(".litematic"):
        QTimer.singleShot(0, lambda: window._open_file_path(sys.argv[1]))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
