from nutrition import compute_daily_totals

BREAKFAST = {
    "foodName": "Oatmeal with banana",
    "servingSize": "1 bowl",
    "calories": 320,
    "nutrients": {"protein": 9.5, "carbs": 58, "fat": 6.2},
    "vitamins": {"vitamin_c": 10.3, "vitamin_d": 0, "iron": 2.1},
}
LUNCH = {
    "foodName": "Grilled salmon salad",
    "servingSize": "1 plate",
    "calories": 480.5,
    "nutrients": {"protein": 35, "carbs": 12.4, "fat": 30.1},
    "vitamins": {"vitamin_c": 25, "vitamin_d": 11.2, "iron": 1.9},
}


def test_totals_are_summed_in_python():
    assert compute_daily_totals([BREAKFAST, LUNCH]) == {
        "calories": 800.5,
        "protein": 44.5,
        "carbs": 70.4,
        "fat": 36.3,
        "vitamin_c": 35.3,
        "vitamin_d": 11.2,
        "iron": 4.0,
    }


def test_no_meals_gives_zero_totals():
    assert set(compute_daily_totals([]).values()) == {0.0}


def test_missing_or_non_numeric_values_count_as_zero():
    partial = {"foodName": "Apple", "calories": "95", "nutrients": {"carbs": None}, "vitamins": None}

    totals = compute_daily_totals([partial, BREAKFAST])

    assert totals["calories"] == 415.0
    assert totals["carbs"] == 58.0
    assert totals["vitamin_c"] == 10.3


def test_float_noise_is_rounded():
    meals = [{"calories": 0.1, "nutrients": {}, "vitamins": {}}] * 3
    assert compute_daily_totals(meals)["calories"] == 0.3
