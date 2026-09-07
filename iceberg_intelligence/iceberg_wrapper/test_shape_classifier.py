from iceberg_wrapper.shape_classifier import (
    TABULAR_LF_THRESHOLD,
    classify_shape,
)


def test_clear_tabular():
    result = classify_shape(
        length_m=1000.0,
        width_m=300.0,
        freeboard_m=100.0,
    )

    assert result.shape_class == "TABULAR"
    assert result.ratio_lf == 10.0
    assert result.ratio_lf >= TABULAR_LF_THRESHOLD


def test_threshold_boundary():
    result = classify_shape(
        length_m=500.0,
        width_m=200.0,
        freeboard_m=100.0,
    )

    assert result.ratio_lf == 5.0
    assert result.shape_class == "TABULAR"


def test_below_threshold_is_not_rejected():
    result = classify_shape(
        length_m=400.0,
        width_m=200.0,
        freeboard_m=100.0,
    )

    # L/F = 4.
    #
    # The iceberg is NOT rejected.
    # We simply do not have enough morphology information to call it
    # DOMED or IRREGULAR.
    assert result.ratio_lf == 4.0
    assert result.shape_class == "UNKNOWN"


def test_missing_freeboard():
    result = classify_shape(
        length_m=1000.0,
        width_m=300.0,
        freeboard_m=None,
    )

    assert result.shape_class == "UNKNOWN"
    assert result.ratio_lf is None


def test_invalid_length():
    try:
        classify_shape(
            length_m=0.0,
            width_m=300.0,
            freeboard_m=50.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for zero length."
        )


def test_invalid_width():
    try:
        classify_shape(
            length_m=1000.0,
            width_m=-10.0,
            freeboard_m=50.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for negative width."
        )


def test_planform_information_is_preserved():
    result = classify_shape(
        length_m=1000.0,
        width_m=500.0,
        freeboard_m=100.0,
        area_m2=450000.0,
        perimeter_m=3000.0,
    )

    assert result.shape_class == "TABULAR"
    assert result.ratio_lf == 10.0
    assert result.ratio_lw == 2.0


if __name__ == "__main__":
    test_clear_tabular()
    test_threshold_boundary()
    test_below_threshold_is_not_rejected()
    test_missing_freeboard()
    test_invalid_length()
    test_invalid_width()
    test_planform_information_is_preserved()

    print("All shape classifier tests passed.")