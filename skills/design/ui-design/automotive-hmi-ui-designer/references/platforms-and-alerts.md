# Platforms, Alerts and Interruptions

## Android Automotive OS (AAOS) and Android Auto

- Driving-state UX restrictions: the system tells apps when restrictions apply (e.g. no keyboard, limited string lengths,
  limited list sizes, no video). Apps built with the Car App Library use templates that enforce them.
- Car App Library templates (navigation, POI, media, messaging, etc.) handle layout, sizing and driver-distraction rules;
  custom UI is restricted to specific app categories.
- Minimum touch target 76 x 76 dp; day/night themes required; respect the system's driving state.

## Apple CarPlay

- Apps use CarPlay templates (list, grid, map, now playing, information, point of interest...). The template set and list
  lengths are constrained by Apple, and the system adapts them to the car's display and input (touch, knob, touchpad).
- Siri handles voice input; messaging is via SiriKit and notifications, read aloud rather than shown as text.
- Next-generation CarPlay extends into the cluster for supported vehicles; design within Apple's system styling.

## Alert prioritisation

| Priority | Examples | Presentation |
|----------|----------|--------------|
| Imminent safety | Collision warning, lane departure, brake failure | Cluster/HUD + distinct sound + haptic (seat/wheel); interrupts everything |
| Safety-related, not immediate | Low tyre pressure, engine warning | Cluster indicator + chime; persistent until acknowledged or resolved |
| Navigation guidance | Next turn | Voice prompt + cluster/HUD graphic |
| Communication | Incoming call, message | Brief banner + sound; actions by steering wheel or voice; text not displayed while driving |
| Information | Song change, charging status | Unobtrusive, no sound |

- Higher priorities pre-empt lower ones; queue the rest.
- Urgent warnings are multimodal (visual + auditory + haptic) and never colour-only.
- Use standardised telltale symbols (ISO 2575) for vehicle warnings.

## Interruptions and resumption

- Every task must survive the driver looking away: no timeouts that discard state, no time-limited choices.
- When a higher-priority event interrupts (call, warning), return to the exact previous state afterwards.
- Partial input (destination being chosen by voice) resumes, not restarts.
- Lock-out transitions: if driving starts mid-task, switch to a simplified version or pause with a clear message
  ("Continue when parked") and keep the state.
