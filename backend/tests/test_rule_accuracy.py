from app.stage_b.rule_accuracy import expected, grounded, lists_labels, scores


def test_expected_format_and_filler():
    e = expected("hey can you please summarize this", "Summarize the text in 3 bullet points.")
    assert e["B01"] and e["B03"] and not e["B06"]


def test_expected_needs_defect_in_degraded():
    # the degraded prompt already states a format: nothing for B03 to fix
    assert not expected("give the answer as JSON", "Return the answer as JSON.")["B03"]


def test_expected_language_and_length():
    e = expected("write a function that reverses a string", "Write a Python function that reverses a string.")
    assert e["B05"] and not e["B04"]
    assert expected("what is the capital of peru", "Answer in one sentence: what is the capital of Peru?")["B04"]


def test_lists_labels():
    assert lists_labels('Classify each as "string" or "percussion".')
    assert lists_labels("assign one label from the set {memoir, autobiography, biography}")
    assert lists_labels("Allowed labels: Small Cap, Large Cap.")
    assert not lists_labels("which instrument is string or percussion udu")


def test_grounded():
    assert grounded("Answer using only the provided text.")
    assert grounded("Based on the passage, who won?")
    assert not grounded("who won the match")


def test_expected_structure():
    assert expected("classify these as fruit or vegetable: apple, carrot, banana",
                    'Classify each as "fruit" or "vegetable".\n\nItems: apple, carrot, banana')["B07"]


def test_scores():
    s = scores([(True, True), (True, False), (False, True), (False, False)])
    assert (s["tp"], s["fp"], s["fn"], s["tn"]) == (1, 1, 1, 1)
    assert s["precision"] == s["recall"] == s["f1"] == 0.5
    assert scores([(False, False)])["precision"] is None
