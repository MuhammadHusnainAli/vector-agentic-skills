# Prompt Questions for Each Bone

Use these to fill empty bones. Write causes as **conditions** ("tray has no dividers"), not solutions ("need dividers")
or blame ("packer careless").

| Bone | Prompts |
|------|---------|
| Man (people) | Was the person trained and certified for this task? Shift, overtime, new starter, agency staff? Is the task physically hard to do right (reach, visibility, force)? Are instructions understood (language, pictures)? |
| Machine | Tool wear, offsets, fixtures, clamping? Maintenance overdue? Machine changed, moved or repaired? Program revision? Vibration, temperature drift, coolant? |
| Method | Instruction exists, current, followed as written? Sequence, parameters, cycle time pressure? Recent process change? Packing, handling and transport method? |
| Material | Supplier, lot, heat number changed? Material spec, hardness, coating, dimensions of incoming parts? Storage and shelf life? Mixed lots? |
| Measurement | Gauge capable (Gage R&R)? Calibrated? Right method and frequency? Light, magnification, reference samples for visual checks? Data recorded correctly? |
| Environment | Temperature, humidity, dust, ESD, lighting, noise? Season, time of day? Floor condition, layout, congestion? |

## Variants

| Setting | Bones |
|---------|-------|
| Manufacturing (6M) | Man, Machine, Method, Material, Measurement, Environment (Mother Nature) |
| 8M | 6M + Management, Maintenance |
| Service (4S / 8P) | Surroundings, Suppliers, Systems, Skills; or Product, Price, Place, Promotion, People, Process, Physical evidence, Productivity |
| Software / IT | People, Process, Tools, Code, Data, Infrastructure, Requirements |

`fishbone.py` keeps any non-6M category as an extra bone, so these variants work as-is; FB001 only checks the six M.
