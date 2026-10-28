from backend.services.s4_s5_landing import squeeze_page_builder


def test_squeeze_page_has_separate_optional_resubscribe_confirmation():
    html = squeeze_page_builder(
        headline="A practical resource",
        subheadline="Useful information for independent creators.",
        benefit_bullets=["A clear first step", "A useful checklist"],
        privacy_url="https://example.invalid/privacy",
        workspace_token="test-workspace-token",
    )
    assert 'name="consent" value="yes" required' in html
    assert 'name="resubscribe_confirmed" value="yes"' in html
    assert "If you previously unsubscribed, check this box to explicitly confirm" in html
    resubscribe_control = html.split('name="resubscribe_confirmed"', 1)[1].split("</label>", 1)[0]
    assert "required" not in resubscribe_control
