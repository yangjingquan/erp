# Login page design QA

## Comparison target

- Source visual truth: `/var/folders/gd/133fk3b92tl_glzpvs2kxf9r0000gn/T/codex-clipboard-b0fab0bd-d817-4250-af15-34539d373c1b.png`
- Implementation screenshot: `/Users/yangjingquan/Documents/ERP/implementation-login.png`
- Route: `/login`
- State: light theme, default username/password values, account login tab selected, password masked
- Viewport: 2048 × 980 CSS px; implementation screenshot is 2048 × 980 px at 1x density
- Source normalization: source image is 2048 × 1016 px and includes 36 px of browser chrome; comparison uses the 2048 × 980 page-content region

## Evidence

Full-view comparison confirms the same two-column composition, 52.5% / 47.5% split, dark brand panel, light form panel, vertical positioning, form width, button hierarchy, and footer placement.

Focused regions were reviewed for the brand header, hero copy and feature cards, login tabs, username/password controls, primary CTA, security notice, support row, and footer metadata. No focused P0/P1/P2 mismatches remained after the final capture.

## Required fidelity surfaces

- Fonts and typography: Inter/system Chinese fallback, bold hero hierarchy, compact uppercase eyebrow labels, and small form metadata match the reference direction.
- Spacing and layout rhythm: shared viewport split and vertically centered right form align with the source; responsive rules collapse to a single-column login on narrow screens.
- Colors and visual tokens: `#292726` dark panel, `#fffaf4` light panel, warm rust primary, muted beige borders, and amber security notice are mapped to existing ERP theme tokens.
- Image quality and asset fidelity: the source contains no required raster imagery; icons use the existing Element Plus icon library and the decorative rings remain lightweight UI ornamentation.
- Copy and content: login title, helper text, account/password labels, security notice, support row, and footer metadata follow the screenshot while preserving the existing authentication flow.

## Primary interactions tested

- Username and password inputs render with existing v-model bindings.
- Password visibility control is present through the existing `show-password` behavior.
- Login CTA retains the original `auth.login` call and redirect behavior.
- Forgot-password and support actions provide informational feedback without changing authentication behavior.
- Browser console checked: no errors or warnings.

## Findings

No actionable P0/P1/P2 findings.

## Comparison history

- Initial implementation: replaced the single centered card with the split-screen composition and added the screenshot-aligned content regions.
- Final implementation: captured at the normalized 2048 × 980 viewport; no actionable P0/P1/P2 differences remained.

## Follow-up Polish

- P3: add real privacy-policy and terms links if those destinations become available.
- P3: connect the single sign-on tab when an SSO provider is configured.

final result: passed
