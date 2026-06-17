SINGLE_JUMP_MODES = {
    "Single Jump",
    "Box Drop",
    "Box Drop Jump",
    "Push Up",
    "Squat",
    "Deadlift",
    "Power Clean",
}


def filter_history_for_mode(history, mode_name):
    if mode_name in SINGLE_JUMP_MODES:
        return [j for j in history if j.get("formula_peak_power") is not None]
    if mode_name == "Contact Time":
        return [j for j in history if "contact_time" in j]
    if mode_name == "Jump Estimation":
        return [
            j for j in history
            if j.get("formula_peak_power") is None
            and "contact_time" not in j
            and not j.get("jump_count")
        ]
    if mode_name == "Continuous Jump":
        return [j for j in history if j.get("jump_count")]
    return history


def format_history_item(jump):
    if jump.get("jump_count"):
        return f"#{jump['_id']}: {jump['jump_count']}J Avg {jump.get('avg_height', 0):.1f}cm"
    if (jump.get("height_flight") or 0) > 0:
        return f"#{jump['_id']}: {jump['height_flight']:.1f}cm ({jump['flight_time']:.0f}ms)"
    if "contact_time" in jump:
        return f"#{jump['_id']}: CT {jump.get('contact_time', 0):.0f}ms"
    return f"#{jump['_id']}: Imp {jump.get('height_impulse', 0):.1f}cm"


def format_history_items(history):
    return [format_history_item(jump) for jump in history]


def parse_history_item_id(item):
    if not item:
        return None
    return int(item.split(":", 1)[0].replace("#", ""))
