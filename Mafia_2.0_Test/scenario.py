"""Preset game states for local CLI testing."""

# 7-player setup matching Mafia_2.0 role distribution at player count 7:
# Mafioso, Framer, Detective, Doctor, Escort, Medium, Executioner
SEVEN_PLAYER_SCENARIO = {
    "name": "seven_players",
    "description": "Standard 7-player test game",
    "players": [
        {"name": "Alice", "role": "Doctor"},
        {"name": "Bob", "role": "Detective"},
        {"name": "Charlie", "role": "Escort"},
        {"name": "Diana", "role": "Medium"},
        {"name": "Eve", "role": "Mafioso"},
        {"name": "Frank", "role": "Framer"},
        {"name": "Grace", "role": "Executioner"},
    ],
    # Executioner target (player number, 1-indexed)
    "executioner_target": 1,  # Alice
}

SCENARIOS = {
    "seven_players": SEVEN_PLAYER_SCENARIO,
}


def get_scenario(name: str = "seven_players") -> dict:
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS)
        raise ValueError(f"Unknown scenario '{name}'. Available: {available}")
    return SCENARIOS[name]
