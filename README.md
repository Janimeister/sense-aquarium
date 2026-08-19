# 8x8 Generative Aquarium

A small Python 3 application for a Raspberry Pi 3B+ with a Sense HAT. It turns the
8x8 RGB LED matrix into a tiny artificial aquarium where fish move, breed,
mutate, sleep, hatch, and react to room conditions.

The aquarium is deliberately not realistic. Temperature, humidity, pressure,
pressure trend, and time of day are treated as creative inputs for a living pixel
ecosystem.

## Hardware

- Raspberry Pi 3B+
- Sense HAT mounted on top
- Sense HAT LED matrix, sensors, and joystick

The app also has a mock mode for development on a normal computer.

## Install

On Raspberry Pi OS:

```bash
sudo apt update
sudo apt install sense-hat python3-sense-hat
```

Or, if your Python environment uses pip:

```bash
python3 -m pip install sense-hat
```

No other heavy dependencies are required.

## Run

```bash
python3 main.py
```

For non-Pi development or testing without hardware:

```bash
python3 main.py --mock
```

Run a short smoke test and exit:

```bash
python3 main.py --mock --once
```

The aquarium saves state to `aquarium_state.json` by default, so fish, eggs,
algae, pressure history, climate history, and tank identity survive restarts.

## Controls

- Joystick middle press: cycle display mode
- Joystick middle hold: save and exit safely
- Joystick up/down: brightness up/down
- Joystick left/right: cycle aquarium view

Display modes:

1. Aquarium: animated fish simulation
2. Sensor: corrected temperature, humidity, pressure, and trend
3. Ecosystem: event, fish count, dominant species, tank identity
4. Debug: raw readings and calibration offsets

Aquarium views:

- Natural: species colors and patterns
- Thermal: temperature and energy emphasized
- Genetic: mutation level, age, and energy emphasized

### 8x8 LED legend

In the main Aquarium view, each pixel on the 8x8 grid has a meaning:

- Fish: one bright pixel per fish, using species colors in Natural view
- Large fish: a second dim tail pixel behind the fish
- Stormtail in falling pressure: blue-violet trail pixel behind the fish
- Eggs: amber/brown pixels
- Food: bright green pixels
- Algae: darker green pixels
- Bubbles: pale blue/cyan pixels
- Lightning or storm flash: white or purple streak pixels

The water/background color also changes to show tank conditions:

- Deep blue: normal water or night
- Blue-cyan: cold or high-pressure / crystal conditions
- Teal-green: plankton bloom or lush water
- Purple-indigo: low-pressure, abyss, or storm conditions
- Red-orange: heat stress or volcanic vent conditions

Extra event effects can appear on top of the background:

- Green sparkles: `plankton_bloom` or `breeding_bloom`
- Red-orange glow on the bottom row: `volcanic_vent`

In the non-aquarium display modes, the LEDs act as status icons before text scrolls:

- Sensor mode: left bar shows temperature, lower bar shows humidity, with blue for cooler water and red for hotter water
- Ecosystem mode: green bottom row represents the tank floor and the blue block highlights ecosystem status
- Debug mode: purple/teal X pattern indicates the raw sensor debug screen

After a long period without joystick input, brightness drops to a screensaver
level automatically.

## Calibration

The Sense HAT temperature and humidity readings can be distorted by heat from the
Raspberry Pi. Defaults live in `config.py`:

```python
TEMP_OFFSET_C = 9.6
HUMIDITY_OFFSET = 8.0
```

Runtime correction:

```python
corrected_temp = raw_temp - TEMP_OFFSET_C
corrected_humidity = clamp(raw_humidity + HUMIDITY_OFFSET, 0, 100)
```

You can also override them at launch:

```bash
python3 main.py --temp-offset 6.5 --humidity-offset 2.0
```

Other thresholds and timing values are also in `config.py`, including pressure
trend window, frame interval, save interval, population limits, brightness steps,
and sensor logging.

## Evolution Rules

Each animation tick updates fish energy, movement, food, algae, bubbles, and
event effects. Each evolution tick can breed fish, hatch eggs, mutate fish, and
retire very old or exhausted fish gently. Once per calendar day, fish and eggs
age, climate history is recorded, and the tank identity can evolve.

Temperature:

- Below 18 C: fish slow down, energy drains more slowly, bottom rows become more
  attractive, and blue/cyan mutations become more likely.
- 18-23 C: balanced movement, food, and breeding.
- 23-28 C: fish move faster, breeding improves, and warmer colors appear more
  often.
- Above 28 C: energy drains faster, movement gets chaotic, mutation chance rises,
  and red/orange fish are favored.

Humidity:

- Below 35%: less food, fish conserve energy, and small fish have a survival
  advantage.
- 35-60%: balanced ecosystem.
- 60-75%: more food, algae growth, better breeding, and green mutations.
- Above 75%: swampy algae growth, glow/camouflage mutations, and noisy water.

Pressure:

- Pressure trend compares the current reading with one from roughly 30 minutes
  ago.
- High pressure calms the water, spreads fish out, lowers mutation chance, and
  favors clear pale species.
- Low pressure draws fish deeper and favors dark or glowing species.
- Falling pressure creates storm current, horizontal drift, zigzag motion,
  occasional lightning, and extra mutation pressure.
- Rising pressure creates recovery conditions, energy gain, and faster hatching.

Time of day:

- Morning, 06:00-09:00: feeding time, food pixels, egg hatching, energy gain.
- Day, 09:00-18:00: active swimming and exploration.
- Evening, 18:00-22:00: higher breeding chance and warmer tones.
- Night, 22:00-06:00: most fish slow down, glowing fish brighten, and low pressure
  can trigger abyss movement.
- Around midnight, once per day, the app runs a rare mutation roll and can create
  special deep-sea eggs.

Combined events override simpler events when conditions line up:

- `plankton_bloom`: warm and humid; more food, breeding, and green sparkles
- `evaporation_stress`: hot and dry; less food and higher energy pressure
- `crystal_freeze`: cold and high pressure; calm blue-white movement
- `deep_storm`: low pressure and humid; purple/blue flashes and storm mutations
- `abyss_migration`: falling pressure at night; glowing fish rise from the bottom
- `clear_sunrise`: rising pressure in the morning; energy boost and hatching
- `volcanic_vent`: hot and low pressure; red/orange pixels and ember mutations
- `breeding_bloom`: humid evening; egg spawning increases
- `crystal_clarity`: high pressure during the day; calm movement and fewer
  mutations

## Species

- Frostfin: cold trigger, blue/cyan, slow, bottom-preferring
- Sunscale: warm trigger, yellow/orange, fast, active during day
- Emberfish: hot trigger, red/orange, chaotic, high mutation chance
- Mossfin: humid trigger, green, hides near algae
- Bubblemouth: humid morning trigger, creates bubble pixels
- Abyssfish: low pressure trigger, dark purple/blue, bottom-preferring
- Lanternfish: low pressure night trigger, glowing yellow/blue, active at night
- Stormtail: falling pressure trigger, fast zigzag, may leave a trail
- Glassfin: high pressure trigger, pale blue/white, smooth and calm
- Crystal Ray: rare cold + high pressure + morning trigger, elegant and slow
- Thunder Fry: hatches from storm eggs during storms, tiny and fast
- Abyss Elder: rare evolution after surviving many nights, large and glowing

## Persistence

`aquarium_state.json` stores:

- fish list
- eggs
- algae map
- generation count
- last midnight event date
- pressure history
- climate history
- dominant species and tank identity

Pressure history is kept for about an hour, which is enough to calculate the
30-minute trend while keeping the state file small. Climate
history influences tank identities:

- Tropical Reef
- Arctic Tank
- Swamp Garden
- Abyss Zone
- Storm Aquarium
- Crystal Pond

## Optional Sensor CSV Log

By default, readings are appended to `sensor_log.csv` with corrected values,
pressure trend, current event, fish count, and tank identity. When the file
exceeds the size cap in `config.py` (`SENSOR_LOG_MAX_BYTES`, 5 MB by default),
it is rotated to `sensor_log.csv.1` and a fresh file is started.

Disable CSV logging:

```bash
python3 main.py --no-log
```

## systemd Service

Create `/etc/systemd/system/sense-aquarium.service`:

```ini
[Unit]
Description=8x8 Generative Aquarium
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=/home/pi/sense-aquarium
ExecStart=/usr/bin/python3 /home/pi/sense-aquarium/main.py
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sense-aquarium.service
sudo systemctl start sense-aquarium.service
```

Check logs:

```bash
journalctl -u sense-aquarium.service -f
```

## Files

- `main.py`: loop, scheduling, safe shutdown
- `aquarium.py`: ecosystem simulation, breeding, hatching, daily evolution
- `fish.py`: fish and egg data models, species profiles, mutation helpers
- `environment.py`: sensor correction, pressure trend, event mapping
- `display.py`: Sense HAT/mock display, rendering, joystick controls
- `storage.py`: JSON persistence and CSV logging
- `config.py`: calibration, thresholds, timing, brightness, limits
