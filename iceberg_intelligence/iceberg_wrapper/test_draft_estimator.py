from iceberg_wrapper.draft_estimator import (
    estimate_domed_draft,
    estimate_draft,
    estimate_tabular_draft,
    verify_domed_solution,
    verify_tabular_solution,
)


def test_tabular_30m_freeboard():
    result = estimate_tabular_draft(
        freeboard_m=30.0
    )

    assert result.status == "SUCCESS"
    assert result.shape_class == "TABULAR"

    print(
        f"Tabular draft for F=30 m: "
        f"{result.estimated_draft_m:.6f} m"
    )

    # Approximately 67.5 m.
    assert 67.0 < result.estimated_draft_m < 68.0

    assert verify_tabular_solution(
        freeboard_m=30.0,
        draft_m=result.estimated_draft_m,
    )


def test_domed_30m_freeboard():
    result = estimate_domed_draft(
        freeboard_m=30.0
    )

    assert result.status == "SUCCESS"
    assert result.shape_class == "DOMED"

    print(
        f"Domed draft for F=30 m: "
        f"{result.estimated_draft_m:.6f} m"
    )

    assert result.estimated_draft_m > 0

    assert verify_domed_solution(
        freeboard_m=30.0,
        draft_m=result.estimated_draft_m,
    )


def test_general_estimator_tabular():
    result = estimate_draft(
        freeboard_m=30.0,
        shape_class="TABULAR",
    )

    assert result.status == "SUCCESS"
    assert result.estimated_draft_m is not None


def test_general_estimator_domed():
    result = estimate_draft(
        freeboard_m=30.0,
        shape_class="DOMED",
    )

    assert result.status == "SUCCESS"
    assert result.estimated_draft_m is not None


def test_irregular_is_not_given_invented_formula():
    result = estimate_draft(
        freeboard_m=30.0,
        shape_class="IRREGULAR",
    )

    assert result.estimated_draft_m is None
    assert result.status == "UNSUPPORTED_SHAPE"


def test_unknown_shape():
    result = estimate_draft(
        freeboard_m=30.0,
        shape_class="UNKNOWN",
    )

    assert result.estimated_draft_m is None
    assert result.status == "INSUFFICIENT_DATA"


def test_invalid_freeboard():
    try:
        estimate_tabular_draft(
            freeboard_m=0.0
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for zero freeboard."
        )


def test_negative_freeboard():
    try:
        estimate_domed_draft(
            freeboard_m=-10.0
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for negative freeboard."
        )


if __name__ == "__main__":
    test_tabular_30m_freeboard()
    test_domed_30m_freeboard()
    test_general_estimator_tabular()
    test_general_estimator_domed()
    test_irregular_is_not_given_invented_formula()
    test_unknown_shape()
    test_invalid_freeboard()
    test_negative_freeboard()

    print("All draft estimator tests passed.")