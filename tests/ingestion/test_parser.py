from ingestion.parser import parse_contacts

HEADER = "phone,first_name,timezone,amount_due"


def test_parses_valid_rows_and_captures_metadata():
    text = HEADER + "\n+15551230001,Ann,America/New_York,12.50\n"
    result = parse_contacts(text)
    assert result.errors == []
    assert len(result.valid) == 1
    row = result.valid[0]
    assert row.phone == "+15551230001"
    assert row.timezone == "America/New_York"
    assert row.metadata == {"first_name": "Ann", "amount_due": "12.50"}


def test_skips_row_with_missing_phone():
    text = HEADER + "\n,Ann,America/New_York,12.50\n"
    result = parse_contacts(text)
    assert result.valid == []
    assert len(result.errors) == 1
    assert "phone" in result.errors[0].reason
    assert result.errors[0].line == 2


def test_skips_row_with_invalid_timezone():
    text = HEADER + "\n+15551230002,Bob,Mars/Olympus,5.00\n"
    result = parse_contacts(text)
    assert result.valid == []
    assert len(result.errors) == 1
    assert "timezone" in result.errors[0].reason


def test_raises_when_required_column_missing():
    import pytest

    text = "phone,first_name\n+15551230003,Cy\n"
    with pytest.raises(ValueError, match="timezone"):
        parse_contacts(text)


def test_mixed_valid_and_invalid_rows():
    text = (
        HEADER
        + "\n+15551230001,Ann,America/New_York,1.00"
        + "\n+15551230002,Bad,Nowhere/Nope,2.00"
        + "\n+15551230003,Cy,America/Chicago,3.00\n"
    )
    result = parse_contacts(text)
    assert len(result.valid) == 2
    assert len(result.errors) == 1
    assert {r.phone for r in result.valid} == {"+15551230001", "+15551230003"}
