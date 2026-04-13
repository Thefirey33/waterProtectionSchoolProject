from serial import tools
from serial.tools import list_ports
import serial
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
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
        
        self.verticalLayout = QVBoxLayout()
        self.setWindowTitle("Durum")
        
        self.currentWaterFlow = QLabel("Şuankı Su Durumu: 0")
        self.isWaterCut = QLabel("Su Kesildi mi: false")
        
        self.verticalLayout.addWidget(self.currentWaterFlow)
        self.verticalLayout.addWidget(self.isWaterCut)
        
        self.container.setLayout(self.verticalLayout)
        
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
        
        statusGui.currentWaterFlow.setText(f"Şuankı Su Durumu: {decoded_json_data['averageFlow']}")
        statusGui.isWaterCut.setText(f"Su Kesildi mi: {decoded_json_data['waterIsCut'] == 1 and "EVET" or "HAYIR"}")        

passed_handshake_test = True

def handshake(arduino):
    """This is the main handshaker function.

    Args:
        arduino (serial.Serial): the Arduino serial communication line.
    """
    global passed_handshake_test
    
    timeout = 0
    while read_from_arduino_stream(arduino) != "connectready":
        timeout += 1
                    
        if timeout > 5:
            handshakingGui.statusLabel.setText("Bağlantı Oluşturma Hatası!")
                        
        if arduino.is_open:
            arduino.close()
                        
        passed_handshake_test = False  

def attempt_to_connect():
    global arduino_serial_connection
    
    """
        Attempt to connect to the Arduino board.
    """
    for device in list_ports.comports():
        if device.pid != None:
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
                    
                    handshakingGui.destroy()
                    statusGui.show()
                    
                    stats_threads = Thread(target=update_current_stats)
                    stats_threads.start()
    print("Connected")
   

if __name__ == "__main__":
    handshakingGui.show()
    
    connectionThread = Thread(target=attempt_to_connect)
    connectionThread.start()
    
    app.exec()
    is_running = False