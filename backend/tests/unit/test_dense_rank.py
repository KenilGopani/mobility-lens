from app.services.evaluation import dense_ranks


def test_dense_ranks() -> None:
    assert dense_ranks([66.0, 91.2, 66.0000000001, 40.0, None]) == [2, 1, 2, 3, None]
    assert dense_ranks([]) == []
    assert dense_ranks([None]) == [None]
