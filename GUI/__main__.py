from serial.tools import list_ports
import serial
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from threading import Thread
import sys
import json


class StatusGUI(QMainWindow):
    """This is the GUI that displays the current status of the board.

    Args:
        QMainWindow (class): The Qt Window Handler.
    """

    def __init__(self):
        super().__init__()

        self.container = QWidget()
        self.window_size = 100

        self.verticalLayout = QVBoxLayout()
        self.setWindowTitle("Durum")
        self.setFixedSize(800, 600)

        self.currentWaterFlow = QLabel("Şuankı Su Durumu: 0")
        self.isWaterCut = QLabel("Su Kesildi mi: false")

        self.verticalLayout.addWidget(self.currentWaterFlow)
        self.verticalLayout.addWidget(self.isWaterCut)

        self.container.setLayout(self.verticalLayout)

        self.series = QLineSeries()
        self.series.setName("Su Akma Hızı")
        self.series.append(0, 0)
        self.series.setPointsVisible(True)
        self.secondsPassed = 0

        self.axis_x = QValueAxis()
        self.axis_x.setTickCount(10)
        self.axis_x.setLabelFormat("%.1f")
        self.axis_x.setTitleText("Zaman")

        self.water_limit_series = QLineSeries()
        self.water_limit_series.setName("Limit")

        self.red_pen = QPen(QColor("red"))
        self.red_pen.setWidth(2)
        self.red_pen.setStyle(Qt.PenStyle.DashLine)
        self.water_limit_series.setPen(self.red_pen)
        self.axis_x.setRange(0, self.window_size)

        self.axis_y = QValueAxis()
        self.axis_y.setRange(0, 100)
        self.axis_y.setTitleText("Su Akışı")

        self.chart = QChart()
        self.chart.addSeries(self.water_limit_series)
        self.chart.addSeries(self.series)
        self.chart.createDefaultAxes()
        self.chart.setTitle("Su Kullanım Grafiği")

        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.axis_x)
        self.series.attachAxis(self.axis_y)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.verticalLayout.addWidget(self.chart_view)

        self.setCentralWidget(self.container)


arduino_serial_connection: serial.Serial


class HandshakingGUI(QMainWindow):
    """This is the GUI that shows the handshaking project.

    Args:
        QMainWindow (class): The Qt Window Handler.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Water Protection Dialer")
        self.setFixedSize(300, 100)

        self.statusLabel: QLabel = QLabel()

        self.statusLabel.setText("Bağlantı Oluşturuluyor...")
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.statusLabel)


app = QApplication(sys.argv)
handshakingGui = HandshakingGUI()
statusGui = StatusGUI()

is_running = True


def read_from_arduino_stream(arduino: serial.Serial):
    """Reads from the Arduino stream in the way the program accepts.

    Args:
        arduino (serial.Serial): The Arduino Serial Connection Itself.

    Returns:
        str: The read-ed line.
    """
    return arduino.readline().decode().strip()


def update_current_stats():
    while is_running:
        json_data = read_from_arduino_stream(arduino_serial_connection)
        decoded_json_data: dict = json.loads(json_data)

        print(f"Recieved Heartbeat: {json_data}")

        total_water_flow = float(decoded_json_data['averageFlow'])
        water_limit = float(decoded_json_data['waterLimit'])

        statusGui.currentWaterFlow.setText(f"Şuankı Su Durumu: {total_water_flow}")
        statusGui.isWaterCut.setText(f"Su Kesildi mi: {decoded_json_data['waterIsCut'] == 1 and 'EVET' or 'HAYIR'}")
        statusGui.series.append(statusGui.secondsPassed, total_water_flow)
        statusGui.secondsPassed += 1

        statusGui.water_limit_series.append(statusGui.secondsPassed, water_limit)

        if statusGui.secondsPassed > statusGui.window_size:
            statusGui.axis_x.setRange(statusGui.secondsPassed - statusGui.window_size, statusGui.secondsPassed)


passed_handshake_test = True


def handshake(arduino):
    """This is the main handshaker function.

    Args:
        arduino (serial.Serial): the Arduino serial communication line.
    """
    global passed_handshake_test

    timeout = 0
    try:
        while read_from_arduino_stream(arduino) != "connectready":
            timeout += 1

            if timeout > 5:
                handshakingGui.statusLabel.setText("Bağlantı Oluşturma Hatası!")

            if arduino.is_open:
                arduino.close()

            passed_handshake_test = False

    except UnicodeDecodeError:
        handshakingGui.statusLabel.setText("Unicode Çevirme Hatası")
        if arduino.is_open:
            arduino.close()

        passed_handshake_test = False


def attempt_to_connect():
    global statusGui
    global arduino_serial_connection

    """
        Attempt to connect to the Arduino board.
    """
    for device in list_ports.comports():
        if device.pid is not None:
            print(f"Found device at: {device.device}, attempting to handshake...")

            arduino = serial.Serial(port=device.device, timeout=5)
            handshakingGui.statusLabel.setText(f"{device.device} ile bağlantı oluşturuluyor...")

            handshake(arduino)

            if passed_handshake_test:
                handshakingGui.statusLabel.setText("Kart OK... Bağlanılıyor...")

                if arduino.is_open:
                    arduino.write("connectdev".encode())

                if arduino.readline().decode() == "connectok\r\n":
                    arduino_serial_connection = arduino

                    handshakingGui.hide()
                    statusGui.show()

                    stats_threads = Thread(target=update_current_stats)
                    stats_threads.start()


if __name__ == "__main__":
    statusGui.show()
    handshakingGui.show()

    connectionThread = Thread(target=attempt_to_connect)
    connectionThread.start()

    app.exec()
    is_running = False
