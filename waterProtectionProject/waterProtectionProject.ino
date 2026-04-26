/**
  If the tap is left on for a long time, after 10 seconds, a 3 second warning
  should be given to the USER. After 3 seconds, the water will be cut.
*/

constexpr int WATER_SENSOR_PIN{2};
constexpr float SPEED_OF_SENSING{200.0f};
constexpr int MAX_CONTAINER_SIZE{5};
constexpr int MAX_TIMEOUT_LONG{5};
constexpr int MAX_WATER_LEVEL{20};

#define ONE_VALUE_CALC SPEED_OF_SENSING / 1000

#include <Vector.h>

int averageValues[MAX_CONTAINER_SIZE];
Vector<int> averageStorage(averageValues);

/**
  This houses all of the information related to water related functions.
*/
class WaterSensorPropertiesManager {
public:
  int pulseCount{0};
  double waterCuttingCounter{0};
  float flowSpeed{0};
  unsigned long oldTime{0};

  /**
    This is where the information about the current state of the water levels
    are stored.
  */

  void printSerialInfo() {
    char buffer[256];
    char avegBuffer[256];
    dtostrf(this->getAverageOfItemsInStorage(), 6, 2, avegBuffer);

    sprintf(buffer, "{\"averageFlow\":\"%s\", \"waterIsCut\":%d, \"waterLimit\": %d}", avegBuffer, this->shouldCutWaterOutput(), MAX_WATER_LEVEL);
    Serial.println(buffer);
  }

  /**
    This will recieve the average of the water percentage in the current
    storage.
  */
  double getAverageOfItemsInStorage() {
    double averageOfItems = 0.0f;
    for (const int &i : averageStorage) {
      averageOfItems += i;
    }
    return averageOfItems / averageStorage.size();
  }

  /**
    If the water system should cut the current flowing water.
  */
  bool shouldCutWaterOutput() {
    auto currentAvgFlow = this->getAverageOfItemsInStorage();

    if (currentAvgFlow > MAX_WATER_LEVEL) {
      this->waterCuttingCounter += ONE_VALUE_CALC;
    } else {
      this->waterCuttingCounter =
          max(0, this->waterCuttingCounter - ONE_VALUE_CALC);
    }

    return this->waterCuttingCounter >= MAX_TIMEOUT_LONG;
  }

  /**
    This resets the timings of the water sensor system.
  */
  void resetTimings() {
    this->pulseCount = 0;
    this->oldTime = millis();
  }
};

WaterSensorPropertiesManager *waterSensorPropertiesManager;

void appendToPulseCounter() { waterSensorPropertiesManager->pulseCount++; }

/**
  Initialize all functions related to water sensing.
*/
void initializeWaterSensor() {
  pinMode(WATER_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(WATER_SENSOR_PIN), appendToPulseCounter,
                  RISING);

  waterSensorPropertiesManager = new WaterSensorPropertiesManager();
}

/**
  This is where all the functions related to the Arduino board are initialized.
*/
void setup() {
  Serial.begin(9600);
  Serial.println("connectready");
  initializeWaterSensor();

  // Wait for input from the pairing program.


  bool establishedConnection = false;

  while(Serial.available() == 0);
  
  while (!establishedConnection) {
    String connectionStr = Serial.readString();
    connectionStr.trim();
    if (connectionStr = "connectdev")
    {
      establishedConnection = true;
      Serial.println("connectok");
    }
  }
}

/**
  The looping function where the water average percentage is calculated.
*/
void loop() {
  detachInterrupt(digitalPinToInterrupt(WATER_SENSOR_PIN));
  waterSensorPropertiesManager->flowSpeed =
      ((SPEED_OF_SENSING / (millis() - waterSensorPropertiesManager->oldTime)) *
       waterSensorPropertiesManager->pulseCount);

  if (averageStorage.size() - 1 >= MAX_CONTAINER_SIZE - 1)
    averageStorage.remove(0);

  averageStorage.push_back(waterSensorPropertiesManager->flowSpeed);

  waterSensorPropertiesManager->resetTimings();
  waterSensorPropertiesManager->printSerialInfo();

  attachInterrupt(digitalPinToInterrupt(WATER_SENSOR_PIN), appendToPulseCounter,
                  RISING);
  delay(SPEED_OF_SENSING);
}
