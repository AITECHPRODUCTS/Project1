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



def test_persisted_landing_renderer_has_no_remote_script_and_escapes_content():
    from backend.services.s4_s5_landing import render_workspace_landing_page

    html = render_workspace_landing_page(
        headline="<script>alert(1)</script>",
        subheadline="A safely escaped landing page",
        benefit_bullets=["Compare options", "<img src=x onerror=alert(1)>"],
        privacy_url="https://example.invalid/privacy",
        affiliate_disclosure="A clear disclosure",
        lead_magnet="Resource & guide",
        audience="Independent creators",
        workspace_token="opaque.signed-token",
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "cdn.tailwindcss.com" not in html
    assert 'name="workspace_token" value="opaque.signed-token"' in html
    assert 'name="consent" value="yes" required' in html
    assert 'name="resubscribe_confirmed" value="yes"' in html
    assert 'form action="/api/public/leads/capture" method="post"' in html
