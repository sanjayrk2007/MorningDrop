import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime

# Per-domain accent colors — warm wanderlust palette
DOMAIN_COLORS = {
    "india":               "#E8845A",   # terracotta sunset
    "tamilnadu":           "#5BAD8F",   # tropical jade
    "world in 60 seconds": "#7B9FC4",   # sky blue dusk
    "money":               "#C9A96E",   # golden sand
    "jobs":                "#C9A96E",   # golden sand
    "tech":                "#9B7EC8",   # lavender mist
    "ai":                  "#9B7EC8",   # lavender mist
    "sports":              "#D97070",   # coral blush
    "entertainment":       "#2A9D8F",   # deep teal
    "wtf":                 "#5BBDBA",   # aqua lagoon
}

def _get_accent(domain_name: str) -> str:
    """Return the accent color for a given domain name."""
    lower = domain_name.lower()
    for key, color in DOMAIN_COLORS.items():
        if key in lower:
            return color
    return "#6B7280"  # neutral grey fallback

def _markdown_to_html(text: str) -> str:
    """Minimal markdown-to-HTML converter (bold, italic, links, code, headings)."""
    try:
        import markdown
        return markdown.markdown(text, extensions=["nl2br"])
    except ImportError:
        # Fallback manual conversion
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" style="color:#60A5FA;">\1</a>', text)
        text = text.replace('\n', '<br>')
        return text

def _split_into_sections(briefing_content: str) -> list:
    """
    Splits the flat briefing text into per-domain sections.
    Looks for the --- separator pattern used by the LLM.
    Returns list of dicts: {domain, emoji, content}
    """
    # Split on the --- dividers the LLM outputs between stories
    raw_sections = re.split(r'\n---\n', briefing_content.strip())
    sections = []

    # Regex to match bracket headers like [🏅 SPORTS] or [🇮🇳 INDIA & WORLD]
    HEADER_RE = re.compile(r'\[(.+?)\s+([A-Z][A-Z &]+)\]')

    for chunk in raw_sections:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Try to extract domain header line like [🏅 SPORTS]
        header_match = HEADER_RE.search(chunk)
        if header_match:
            emoji_part = header_match.group(1).strip()
            domain_part = header_match.group(2).strip()
            accent = _get_accent(domain_part)

            # Remove ALL occurrences of [emoji DOMAIN] bracket patterns from the body
            clean_content = HEADER_RE.sub('', chunk).strip()

            sections.append({
                "domain": domain_part,
                "emoji": emoji_part,
                "accent": accent,
                "content": clean_content
            })
        else:
            # Orphan chunk (footer line, etc.) — treat as plain text
            sections.append({
                "domain": "",
                "emoji": "",
                "accent": "#C9A96E",
                "content": chunk
            })

    return sections

def _render_section_card(section: dict) -> str:
    """Renders a single domain section as a styled HTML card."""
    accent = section["accent"]
    emoji = section.get("emoji", "")
    domain = section.get("domain", "")
    content_html = _markdown_to_html(section["content"])

    # Special scoreboard highlight for the LIVE TOURNAMENT RADAR block in Sports
    if "LIVE TOURNAMENT RADAR" in section["content"] or "TOURNAMENT RADAR" in section["content"]:
        content_html = content_html.replace(
            "🏆 LIVE TOURNAMENT RADAR 🏆",
            f'<div style="font-size:12px;font-weight:700;letter-spacing:2px;color:#C9A96E;margin-bottom:10px;">🏆 LIVE TOURNAMENT RADAR 🏆</div>'
        )

    # Build the domain label pill (only when domain is known)
    label_html = ""
    if domain:
        label_html = f"""
        <div style="margin-bottom:14px;">
          <span style="
            display: inline-block;
            background: {accent}18;
            color: {accent};
            border: 1px solid {accent}40;
            border-radius: 20px;
            padding: 3px 12px;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            font-family: 'Plus Jakarta Sans', 'Space Grotesk', Georgia, sans-serif;
          ">{emoji} {domain}</span>
        </div>"""

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
      <tr>
        <td style="
          background: #FFFDF9;
          border-left: 4px solid {accent};
          border-radius: 14px;
          padding: 22px 26px;
          font-family: 'Plus Jakarta Sans', 'Space Grotesk', Georgia, sans-serif;
          box-shadow: 0 2px 12px rgba(180,140,100,0.08);
        ">
          {label_html}
          {content_html}
        </td>
      </tr>
    </table>
    """

def format_html_email(briefing_content: str) -> str:
    """
    Converts the flat text briefing into a premium dark-themed HTML email.
    Uses per-domain card sections with accent color borders.
    """
    today = datetime.date.today().strftime('%A, %B %d, %Y')
    sections = _split_into_sections(briefing_content)

    # Build the body cards
    cards_html = ""
    for section in sections:
        cards_html += _render_section_card(section)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Morning Drop</title>
  <!-- Plus Jakarta Sans + Space Grotesk via Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #FBF7F2;
      font-family: 'Plus Jakarta Sans', 'Space Grotesk', Georgia, sans-serif;
      color: #5C4F42;
      -webkit-font-smoothing: antialiased;
    }}
    a {{
      color: #C9845A;
      text-decoration: none;
      font-weight: 500;
    }}
    a:hover {{
      text-decoration: underline;
      color: #B06840;
    }}
    p {{
      margin: 0 0 12px 0;
      line-height: 1.8;
      font-size: 15px;
      color: #7A6A5A;
    }}
    h1, h2, h3 {{
      margin: 0 0 8px 0;
      color: #4A3B2E;
      font-family: 'Satoshi', 'DM Sans', Georgia, sans-serif;
    }}
    strong {{
      color: #4A3B2E;
      font-weight: 700;
    }}
    em {{
      color: #9E8E7E;
      font-style: italic;
    }}
    code {{
      background: #F0EAE0;
      padding: 2px 7px;
      border-radius: 5px;
      font-size: 13px;
      color: #9B7EC8;
      font-family: 'DM Mono', monospace;
    }}
    .wrapper {{
      max-width: 640px;
      margin: 0 auto;
      padding: 28px 16px;
    }}
    .hero {{
      background: linear-gradient(135deg, #FEF3C7 0%, #FCD34D 35%, #6366F1 100%);
      border-radius: 20px;
      padding: 40px 36px;
      margin-bottom: 28px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}
    .hero::before {{
      content: '';
      position: absolute;
      top: -30px; right: -30px;
      width: 160px; height: 160px;
      background: rgba(255,255,255,0.25);
      border-radius: 50%;
    }}
    .hero::after {{
      content: '';
      position: absolute;
      bottom: -20px; left: -20px;
      width: 100px; height: 100px;
      background: rgba(255,255,255,0.18);
      border-radius: 50%;
    }}
    .hero-title {{
      font-family: 'Space Grotesk', 'Plus Jakarta Sans', Georgia, sans-serif;
      font-size: 34px;
      font-weight: 900;
      color: #1E1B4B;
      margin: 0 0 6px 0;
      letter-spacing: -0.8px;
      position: relative;
    }}
    .hero-date {{
      font-size: 11px;
      color: #9A6F58;
      font-weight: 600;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin: 0 0 10px 0;
      position: relative;
    }}
    .hero-tagline {{
      font-size: 14px;
      color: #7A5040;
      margin-top: 4px;
      font-weight: 400;
      position: relative;
    }}
    .section-divider {{
      display: block;
      width: 48px;
      height: 3px;
      background: linear-gradient(90deg, #F59E0B, #6366F1);
      border-radius: 2px;
      margin: 14px auto 0 auto;
    }}
    .footer {{
      text-align: center;
      padding: 28px 0 12px 0;
      border-top: 1px solid #EDE4D8;
      margin-top: 4px;
    }}
    .footer p {{
      font-size: 13px;
      color: #B09A88;
      margin: 0;
      line-height: 1.7;
    }}
    .footer .emoji-footer {{
      font-size: 22px;
      display: block;
      margin-bottom: 8px;
    }}
    .footer .brand {{
      font-size: 11px;
      color: #C8B8A8;
      margin-top: 14px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
    }}
    /* Override markdown paragraph spacing inside cards */
    td p {{
      margin: 0 0 10px 0;
      font-size: 14.5px;
      line-height: 1.85;
      color: #7A6A5A;
    }}
    td h1, td h2, td h3 {{
      font-family: 'Plus Jakarta Sans', 'Space Grotesk', Georgia, sans-serif;
      font-size: 15.5px;
      font-weight: 700;
      color: #4A3B2E;
      margin: 0 0 10px 0;
    }}
    td ul, td ol {{
      margin: 0 0 10px 18px;
      padding: 0;
      color: #7A6A5A;
      font-size: 14px;
    }}
    td li {{
      margin-bottom: 5px;
      line-height: 1.8;
    }}
    td strong {{
      color: #4A3B2E;
      font-weight: 700;
    }}
    td a {{
      color: #C9845A;
      font-weight: 500;
    }}
    @media (max-width: 600px) {{
      .wrapper {{
        padding: 16px 10px;
      }}
      .hero {{
        padding: 30px 22px;
      }}
      .hero-title {{
        font-size: 27px;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">

    <!-- HERO HEADER -->
    <div class="hero">
      <p class="hero-date">{today}</p>
      <div class="hero-title">The Morning Drop 🌅</div>
      <p class="hero-tagline">Your world. Simplified. Every morning. ☕</p>
      <span class="section-divider"></span>
    </div>

    <!-- CONTENT CARDS -->
    {cards_html}

    <!-- FOOTER -->
    <div class="footer">
      <span class="emoji-footer">✨</span>
      <p>That's your morning drop. Go be the most informed person in the room.</p>
      <p style="margin-top:5px;">See you tomorrow — same time, same vibe. 🌸</p>
      <p class="brand">The Morning Drop &middot; Crafted with ❤️</p>
    </div>

  </div>
</body>
</html>"""

def send_email(sender_email: str, app_password: str, recipient_email: str, subject: str, content: str):
    """Sends the briefing email via Gmail SMTP."""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # Attach both plain text and HTML versions
    part1 = MIMEText(content, "plain")
    part2 = MIMEText(format_html_email(content), "html")

    msg.attach(part1)
    msg.attach(part2)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

    print(f"Email successfully sent to {recipient_email}")
