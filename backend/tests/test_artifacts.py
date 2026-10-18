from artifacts import parse_thread_text

NAMES = {"Priya Shah": "priya-shah", "Marcus Lee": "marcus-lee"}


def test_parse_thread_text():
    text = "Priya Shah: why is sync empty?\nMarcus Lee: two reasons:\n1. rev2\n2. modseq\nSomeone: +1"
    msgs = parse_thread_text(text, NAMES)
    assert [(m.person_id, m.name) for m in msgs] == [
        ("priya-shah", "Priya Shah"), ("marcus-lee", "Marcus Lee"), (None, "Someone")]
    assert msgs[1].text == "two reasons:\n1. rev2\n2. modseq"


def test_colons_inside_messages_are_kept():
    msgs = parse_thread_text("Priya Shah: note: this is fine", NAMES)
    assert msgs[0].text == "note: this is fine"
