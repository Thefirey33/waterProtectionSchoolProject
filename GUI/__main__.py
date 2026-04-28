from serial.tools import list_ports
import serial
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout, QPushButton, QCheckBox
from PySide6.QtCore import Qt
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from threading import Thread
from typing import LiteralString, Literal
import sys
import time
import json

# error flag when errors happen
ERROR_FLAG: LiteralString = "ERROR"
# when the arduino is ready for connection
CONNECT_READY: LiteralString = "connectready"
# when the connection has been established
CONNECT_OK: LiteralString = "connectok"
# the command to tell the board to connect
CONNECT_BOARD: LiteralString = "connectdev"
# This will change the state of the board to override the current switch.
BOARD_CHANGE_STATE: LiteralString = "boardchange"
# Is the current loop running?
is_running = True
# The Arduino Serial Connection to the board.
arduino_serial_connection: serial.Serial
# If the Arduino has passed the handshake test or not?
passed_handshake_test = True
# The flasher that shows if the current water flow is forcefully forced open.
FLASHER_TIMEOUT = 1
# The button of the very cool switch that toggles if the water is forcefully turned on or not.
TOGGLE_SWITCH_TEXT: LiteralString = "Zorla Suyu Aç/Kapat"

def change_board_state():
    """
        Change the state of the board that allows the water to be forcefully opened and closed manually.
    """
    status_gui.toggle_switch.setText("Komut gönderiliyor...")
    arduino_serial_connection.write(BOARD_CHANGE_STATE.encode())


class StatusGUI(QMainWindow):
    """
        The QLineSeries that keeps the information about the current values in the Chart.
    """
    series: QLineSeries

    """
        The amount of seconds passed in the current water detection session.
    """
    secondsPassed: int

    """
        The QValueAxis of the X Axis.
    """
    axis_x: QValueAxis

    """
        The QValueAxis of the Y Axis.
    """
    axis_y: QValueAxis

    """
        The series that shows the water limit.
    """
    water_limit_series: QLineSeries

    """
        The pen that draws the line limit.
    """
    red_pen: QPen

    """
        The QChart itself. Showing the water flow information.
    """
    chart: QChart

    """
        The Chart View that renders the chart itself.
    """
    chart_view: QChartView

    def create_chart(self):
        """
            This creates the chart that displays the water information.
        """

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
        self.red_pen.setStyle(Qt.PenStyle.DashDotDotLine)
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

    """
    This is the GUI that displays the current status of the board.

    Args:
        QMainWindow (class): The Qt Window Handler.
    """

    def __init__(self):
        super().__init__()

        self.container = QWidget()
        self.window_size = 100

        self.verticalLayout = QVBoxLayout()
        self.setWindowTitle("Durum")
        self.setMinimumSize(800, 600)

        self.currentWaterFlow = QLabel("Bilgi Yok!")
        self.currentWaterFlow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.currentWaterFlow.setStyleSheet("font-size: 20px;")
        self.verticalLayout.addWidget(self.currentWaterFlow)

        self.isWaterCut = QLabel("Bilgi Yok!")
        self.isWaterCut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.isWaterCut.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.verticalLayout.addWidget(self.isWaterCut)

        self.toggle_switch = QPushButton(TOGGLE_SWITCH_TEXT)
        self.toggle_switch.clicked.connect(change_board_state)
        self.toggle_switch.setCursor(Qt.PointingHandCursor)
        self.verticalLayout.addWidget(self.toggle_switch)

        self.container.setLayout(self.verticalLayout)
        self.create_chart()

        self.setCentralWidget(self.container)


class HandshakingGUI(QMainWindow):
    """
    This is the GUI that shows the handshaking project.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Bağlantı Oluşturuluyor")
        self.setFixedSize(300, 100)

        self.statusLabel: QLabel = QLabel()

        self.setWindowFlags(Qt.Dialog)

        self.statusLabel.setText("Bağlantı Oluşturuluyor...")
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.statusLabel)


app = QApplication(sys.argv)
handshaking_gui = HandshakingGUI()
status_gui = StatusGUI()


def read_from_arduino_stream(arduino: serial.Serial):
    """Reads from the Arduino stream in the way the program accepts.

    Args:
        arduino (serial.Serial): The Arduino Serial Connection Itself.

    Returns:
        str: The read-ed line.
    """
    try:
        return arduino.readline().decode().strip()
    except serial.SerialException:
        return ERROR_FLAG
    except UnicodeDecodeError:
        return ERROR_FLAG
    except RecursionError:
        return ERROR_FLAG


def update_current_stats():
    global is_running

    while is_running:
        status_gui.toggle_switch.setText(TOGGLE_SWITCH_TEXT)
        arduino_stream_data = read_from_arduino_stream(arduino_serial_connection)

        if arduino_stream_data == ERROR_FLAG or arduino_stream_data == CONNECT_READY:
            is_running = False

            app.shutdown()
            connectionThread.join()
            return

        decoded_json_data: dict = json.loads(arduino_stream_data)

        total_water_flow = float(decoded_json_data['averageFlow'])
        water_limit = float(decoded_json_data['waterLimit'])
        is_override = bool(decoded_json_data['override'])

        status_gui.currentWaterFlow.setText(f"Şuankı Su Durumu: {total_water_flow}")

        is_cut = decoded_json_data['waterIsCut'] == 1

        status_gui.isWaterCut.setText(f"Su Kesildi mi: {is_cut and 'Evet' or (is_override and 'Zorla Açık' or 'Hayır')}")
        flashing_warning = time.time() % FLASHER_TIMEOUT > FLASHER_TIMEOUT / 2.0 and 'green' or 'darkgreen'

        status_gui.isWaterCut.setStyleSheet(
            f"font-size: 40px; font-weight: bold; background-color: {is_cut and 'red' or (is_override and flashing_warning or 'green')}")
        status_gui.series.append(status_gui.secondsPassed, total_water_flow)
        status_gui.secondsPassed += 1

        status_gui.water_limit_series.append(status_gui.secondsPassed, water_limit)

        if status_gui.secondsPassed > status_gui.window_size:
            status_gui.axis_x.setRange(status_gui.secondsPassed - status_gui.window_size, status_gui.secondsPassed)


def attempt_reconnect(arduino):
    """
    Attempt to reconnect to the Arduino Board.
    Args:
        arduino: The Arduino Microcontroller Card.
    """

    global passed_handshake_test

    handshaking_gui.statusLabel.setText("Bağlantı Tekrar Oluşturulacak...\nEğer bu tekrar ederse, LÜTFEN arduino'u "
                                        "çıkar!")
    passed_handshake_test = False
    arduino.close()
    time.sleep(2)

    attempt_to_connect()


def start_connection_handshake(arduino):
    """
    This is the main handshaker function.

    Args:
        arduino (serial.Serial): the Arduino serial communication line.
    """
    global passed_handshake_test

    try:
        while not read_from_arduino_stream(arduino) == CONNECT_READY:
            attempt_reconnect(arduino)

        passed_handshake_test = True

    except UnicodeDecodeError:
        attempt_reconnect(arduino)


def attempt_to_connect():
    """
    Attempt to connect to the Arduino board.
    """

    global status_gui
    global arduino_serial_connection

    # Attempt to connect to the Arduino board.
    for device in list_ports.comports():
        if device.pid is not None:
            print(f"Found device at: {device.device}, attempting to handshake...")

            arduino_serial_connection = serial.Serial(port=device.device, timeout=5)
            handshaking_gui.statusLabel.setText(f"{device.device} ile bağlantı oluşturuluyor...")

            start_connection_handshake(arduino_serial_connection)

            if passed_handshake_test:
                handshaking_gui.statusLabel.setText("Bağlanma Sinyalı Gönderiliyor...")

                arduino_serial_connection.write(CONNECT_BOARD.encode())

                if read_from_arduino_stream(arduino_serial_connection).__contains__(CONNECT_OK):
                    handshaking_gui.hide()
                    status_gui.show()

                    stats_threads = Thread(target=update_current_stats)
                    stats_threads.start()


if __name__ == "__main__":
    status_gui.show()
    handshaking_gui.show()

    connectionThread = Thread(target=attempt_to_connect)
    connectionThread.start()

    app.exec()

    is_running = False
