const int kEmgPin = A0;
const unsigned long kSampleRateHz = 1000;
const unsigned long kSamplePeriodUs = 1000000UL / kSampleRateHz;

struct EmgConfig {
  float dcAlpha;
  float envelopeAlpha;
  float noiseAlpha;

  float thresholdMin;
  float thresholdScale;

  float freqSmoothingAlpha;
  unsigned long minPulseIntervalUs;
};

struct EmgFeatures {
  unsigned long tUs;
  int raw;
  float centered;
  float envelope;
  float threshold;
  bool isActive;
  float activationHz;
  float spectralPeakHz;
  float spectralPeakPower;
};

class GoertzelDetector {
public:
  GoertzelDetector() : targetHz(0.0f), coeff(0.0f), q1(0.0f), q2(0.0f), count(0) {}

  void configure(float sampleRateHz, float inTargetHz, int inWindowSamples) {
    targetHz = inTargetHz;
    windowSamples = inWindowSamples;
    float omega = 2.0f * 3.14159265f * (targetHz / sampleRateHz);
    coeff = 2.0f * (float)cos(omega);
    reset();
  }

  void reset() {
    q1 = 0.0f;
    q2 = 0.0f;
    count = 0;
  }

  void push(float x) {
    float q0 = coeff * q1 - q2 + x;
    q2 = q1;
    q1 = q0;
    count++;
  }

  bool ready() const { return count >= windowSamples; }

  float power() const {
    float p = q1 * q1 + q2 * q2 - coeff * q1 * q2;
    return p < 0.0f ? 0.0f : p;
  }

  float frequencyHz() const { return targetHz; }

private:
  float targetHz;
  float coeff;
  float q1;
  float q2;
  int windowSamples;
  int count;
};

class EmgProcessor {
public:
  EmgProcessor() :
    dcEstimate(512.0f),
    envelope(0.0f),
    noiseFloor(0.0f),
    wasAbove(false),
    lastCrossingUs(0),
    activationHz(0.0f),
    windowSamples(250),
    windowCount(0) {}

  void begin(const EmgConfig& cfg) {
    config = cfg;
    dcEstimate = 512.0f;
    envelope = 0.0f;
    noiseFloor = 0.0f;
    wasAbove = false;
    lastCrossingUs = 0;
    activationHz = 0.0f;
    windowCount = 0;

    detectors[0].configure((float)kSampleRateHz, 50.0f, windowSamples);
    detectors[1].configure((float)kSampleRateHz, 100.0f, windowSamples);
    detectors[2].configure((float)kSampleRateHz, 150.0f, windowSamples);
    detectors[3].configure((float)kSampleRateHz, 200.0f, windowSamples);
  }

  void calibrateDc(int raw0) {
    dcEstimate = (float)raw0;
  }

  EmgFeatures update(int raw, unsigned long nowUs) {
    dcEstimate += config.dcAlpha * ((float)raw - dcEstimate);
    float centered = (float)raw - dcEstimate;
    float rectified = centered < 0.0f ? -centered : centered;

    envelope += config.envelopeAlpha * (rectified - envelope);
    noiseFloor += config.noiseAlpha * (envelope - noiseFloor);

    float threshold = noiseFloor * config.thresholdScale;
    if (threshold < config.thresholdMin) threshold = config.thresholdMin;

    bool isAbove = envelope >= threshold;
    if (isAbove && !wasAbove) {
      if (lastCrossingUs != 0) {
        unsigned long dt = nowUs - lastCrossingUs;
        if (dt >= config.minPulseIntervalUs) {
          float instHz = 1000000.0f / (float)dt;
          activationHz += config.freqSmoothingAlpha * (instHz - activationHz);
          lastCrossingUs = nowUs;
        }
      } else {
        lastCrossingUs = nowUs;
      }
    }
    wasAbove = isAbove;

    for (int i = 0; i < kDetectorCount; i++) {
      detectors[i].push(centered);
    }
    windowCount++;

    float peakHz = 0.0f;
    float peakPower = 0.0f;
    if (windowCount >= windowSamples) {
      for (int i = 0; i < kDetectorCount; i++) {
        float p = detectors[i].power();
        if (p > peakPower) {
          peakPower = p;
          peakHz = detectors[i].frequencyHz();
        }
      }
      for (int i = 0; i < kDetectorCount; i++) detectors[i].reset();
      windowCount = 0;
    }

    EmgFeatures f;
    f.tUs = nowUs;
    f.raw = raw;
    f.centered = centered;
    f.envelope = envelope;
    f.threshold = threshold;
    f.isActive = isAbove;
    f.activationHz = activationHz;
    f.spectralPeakHz = peakHz;
    f.spectralPeakPower = peakPower;
    return f;
  }

private:
  static const int kDetectorCount = 4;

  EmgConfig config;

  float dcEstimate;
  float envelope;
  float noiseFloor;

  bool wasAbove;
  unsigned long lastCrossingUs;
  float activationHz;

  int windowSamples;
  int windowCount;
  GoertzelDetector detectors[kDetectorCount];
};

struct EmgBus {
  typedef void (*Subscriber)(const EmgFeatures& f);

  void subscribe(Subscriber fn) {
    if (count >= kMaxSubscribers) return;
    subs[count++] = fn;
  }

  void publish(const EmgFeatures& f) const {
    for (int i = 0; i < count; i++) subs[i](f);
  }

private:
  static const int kMaxSubscribers = 6;
  Subscriber subs[kMaxSubscribers];
  int count = 0;
};

EmgConfig config = {
  0.01f,
  0.05f,
  0.0125f,
  8.0f,
  1.8f,
  0.2f,
  70000UL,
};

EmgProcessor processor;
EmgBus bus;

unsigned long nextSampleUs = 0;

void serialPlotterSubscriber(const EmgFeatures& f) {
  Serial.print(f.raw);
  Serial.print('\t');
  Serial.print(f.envelope, 2);
  Serial.print('\t');
  Serial.print(f.activationHz, 2);
  Serial.print('\t');
  Serial.print(f.spectralPeakHz, 0);
  Serial.print('\t');
  Serial.println(f.spectralPeakPower, 0);
}

bool tryApplyConfigLine(const String& line) {
  int eq = line.indexOf('=');
  if (eq <= 0) return false;
  String key = line.substring(0, eq);
  String val = line.substring(eq + 1);
  key.trim();
  val.trim();

  float f = val.toFloat();
  unsigned long u = (unsigned long)val.toInt();

  if (key == "thresholdScale") { config.thresholdScale = f; return true; }
  if (key == "thresholdMin") { config.thresholdMin = f; return true; }
  if (key == "dcAlpha") { config.dcAlpha = f; return true; }
  if (key == "envelopeAlpha") { config.envelopeAlpha = f; return true; }
  if (key == "noiseAlpha") { config.noiseAlpha = f; return true; }
  if (key == "freqAlpha") { config.freqSmoothingAlpha = f; return true; }
  if (key == "minPulseUs") { config.minPulseIntervalUs = u; return true; }

  return false;
}

void pollSerialConfig() {
  static String line;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (line.length() > 0) {
        bool applied = tryApplyConfigLine(line);
        if (applied) processor.begin(config);
      }
      line = "";
      continue;
    }
    if (line.length() < 80) line += c;
  }
}

void setup() {
  Serial.begin(115200);
  analogReference(DEFAULT);
  delay(200);
  processor.calibrateDc(analogRead(kEmgPin));
  processor.begin(config);
  bus.subscribe(serialPlotterSubscriber);
  nextSampleUs = micros();
}

void loop() {
  pollSerialConfig();

  unsigned long nowUs = micros();
  if ((long)(nowUs - nextSampleUs) < 0) return;
  nextSampleUs += kSamplePeriodUs;

  int raw = analogRead(kEmgPin);
  EmgFeatures f = processor.update(raw, nowUs);
  bus.publish(f);
}
