"""Daily totals, computed in Python from the per-meal estimates."""

# (key, label, unit, where the value lives in a meal dict)
NUTRIENTS = [
    ("calories", "Calories", "kcal", None),
    ("protein", "Protein", "g", "nutrients"),
    ("carbs", "Carbs", "g", "nutrients"),
    ("fat", "Fat", "g", "nutrients"),
    ("vitamin_c", "Vitamin C", "mg", "vitamins"),
    ("vitamin_d", "Vitamin D", "mcg", "vitamins"),
    ("iron", "Iron", "mg", "vitamins"),
]


def to_number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute_daily_totals(meals: list) -> dict:
    """Sum calories, macronutrients, vitamins and iron over all meals.

    Missing or non-numeric values count as 0. Totals are rounded to one decimal place.
    """
    totals = {key: 0.0 for key, _, _, _ in NUTRIENTS}
    for meal in meals:
        for key, _, _, group in NUTRIENTS:
            source = meal if group is None else (meal.get(group) or {})
            totals[key] += to_number(source.get(key))
    return {key: round(value, 1) for key, value in totals.items()}
