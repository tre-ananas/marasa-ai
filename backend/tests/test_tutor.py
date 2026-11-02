from app.tutor.notes import parse_notes
from app.tutor.rubric import DEFAULT_LEVEL, clamp_delta, index_of

def test_parse_notes_extracts_block() -> None:
    reply, notes = parse_notes(
        'Hello there.\n\n<marasa_notes>\n{"vocab": [{"term": "decision", "status": "useful"}],'
        ' "grammar": [], "level_delta": {"vocab": 1}, "next_step": "Keep going."}\n</marasa_notes>'
    )
    assert reply == "Hello there."
    assert notes.parsed is True
    assert notes.vocab[0].term == "decision"
    assert notes.level_delta["vocab"] == 1


def test_parse_notes_survives_malformed_json() -> None:
    reply, notes = parse_notes("Hi.\n\n<marasa_notes>\n{not json}\n</marasa_notes>")
    assert reply == "Hi."
    assert notes.parsed is False
    assert notes.vocab == []


def test_parse_notes_without_block() -> None:
    reply, notes = parse_notes("Just a reply")
    assert reply == "Just a reply"
    assert notes.parsed is False


def test_level_ladder_ordering_and_clamping() -> None:
    assert index_of("NL") < index_of("IM") < index_of("S")
    assert DEFAULT_LEVEL == "IM"
    assert clamp_delta("IM", 1) == "IH"
    assert clamp_delta("IM", -1) == "IL"
    assert clamp_delta("NL", -1) == "NL"
    assert clamp_delta("S", 1) == "S"
