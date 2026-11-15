from app.tutor.notes import parse_notes
from app.tutor.prompts import build_system_prompt
from app.tutor.rubric import DEFAULT_LEVEL, clamp_delta, index_of
from app.tutor.languages import LANGUAGES
from app.tutor.tones import TONES


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


def test_system_prompt_encourages_engagement_with_sensitive_topics() -> None:
    prompt = build_system_prompt(
        language=LANGUAGES["es"],
        tone=TONES["debate_partner"],
        level="IM",
        target_level="IM",
        topics=["immigration policy"],
        vocab_terms=[],
    )

    assert "CONVERSATION SCOPE" in prompt
    assert "Treat the learner's subjects as hypothetical" in prompt
    assert "controversial or sensitive topics" in prompt
    assert "Do not moralize" in prompt
    assert "do not provide real-world action" not in prompt
    assert "Never ask the learner to reveal personal secrets" in prompt
    assert "Follow the learner's energy and intent" in prompt
    assert "Do not mechanically end every turn with a question" in prompt
    assert "The learner's main goal is fluent" in prompt
    assert "redirect the conversation wherever they want" in prompt
