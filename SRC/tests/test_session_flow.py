from Engine.edges import route_after_consolidate, route_after_probe, route_ingress


def test_route_ingress_prefers_end_requested():
    assert route_ingress({"end_requested": True, "phase": "PROBE"}) == "report_work"


def test_route_after_probe_prefers_report_when_end_requested():
    assert route_after_probe({"end_requested": True, "phase": "PROBE"}) == "report_work"


def test_route_after_probe_reveal_when_phase_is_reveal():
    assert route_after_probe({"phase": "REVEAL"}) == "reveal_work"


def test_route_after_consolidate_goes_report_when_needed():
    assert route_after_consolidate({"needs_report": True}) == "report_work"
