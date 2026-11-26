from gen_api_types import is_up_to_date


def test_crlf_is_not_drift():
    assert is_up_to_date("a\r\nb\r\n", "a\nb\n")


def test_real_change_is_drift():
    assert not is_up_to_date("a\nb\n", "a\nc\n")
